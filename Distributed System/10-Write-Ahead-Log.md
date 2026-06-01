# Write-Ahead Log (WAL)

## 1. Problem Statement

Every database maintains state in memory (buffer pool) for performance. The fundamental problem:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    THE DURABILITY GAP                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   In-Memory State                    On-Disk State                  │
│   ┌──────────────┐                  ┌──────────────┐               │
│   │ Page A: v=42 │                  │ Page A: v=10 │               │
│   │ Page B: v=99 │   ← GAP →       │ Page B: v=50 │               │
│   │ Page C: v=7  │                  │ Page C: v=7  │               │
│   └──────────────┘                  └──────────────┘               │
│                                                                     │
│   If crash happens here, v=42 and v=99 are LOST                    │
│                                                                     │
│   Naive solution: fsync every page on every write                   │
│   Problem: Random I/O, ~100 IOPS on HDD = catastrophic performance │
└─────────────────────────────────────────────────────────────────────┘
```

**Why not just fsync every change?**

- A single transaction may modify dozens of 8KB/16KB pages scattered across disk
- Random writes to data files: ~100-200 IOPS on HDD, ~10K on SSD
- Each fsync forces a full disk rotation (HDD) or flash program/erase cycle
- A system doing 10,000 TPS would need 10,000+ random fsyncs/second — impossible

**The WAL insight**: Instead of writing modified pages immediately, write a compact description of the change to a sequential log. Sequential writes are 100-1000x faster than random writes.

---

## 2. Core Principle

**The WAL Protocol (Write-Ahead Logging Rule):**
> Before any modified data page is written to its permanent location in the database, the corresponding log record MUST be written to stable storage first.

This gives us:
1. **Durability** — committed changes survive crashes
2. **Atomicity** — uncommitted changes can be rolled back
3. **Performance** — sequential I/O instead of random I/O

### Write Path Overview

```
┌────────┐      ┌─────────────┐      ┌──────────┐      ┌───────────────┐
│ Client │─────▶│  WAL Write  │─────▶│  fsync   │─────▶│  Acknowledge  │
│        │      │  (append)   │      │  WAL     │      │  to Client    │
└────────┘      └─────────────┘      └──────────┘      └───────────────┘
                                                               │
                                                               │ (later, async)
                                                               ▼
                                                        ┌───────────────┐
                                                        │ Apply to Data │
                                                        │ Pages (Chkpt) │
                                                        └───────────────┘
```

**Key Properties:**

| Property | Description |
|----------|-------------|
| Append-only | Never modifies existing entries |
| Sequential I/O | Exploits disk/SSD write patterns |
| Ordered | LSN provides total ordering |
| Idempotent replay | Can safely replay entries multiple times |
| Minimal data | Only the delta, not entire pages |

### Why Sequential Writes are Fast

```
Random Writes (Data Pages):          Sequential Writes (WAL):
                                     
  ┌───┐                               ┌───┬───┬───┬───┬───┬───┐
  │ P3│  seek                          │ E1│ E2│ E3│ E4│ E5│ E6│──▶ append
  └───┘    ↗                           └───┴───┴───┴───┴───┴───┘
  ┌───┐  /                             
  │ P7│ ← seek back and forth          Single sequential stream
  └───┘  \                             No seeks required
  ┌───┐    ↘                           Disk head stays in place
  │ P1│  seek                          OS can use write-combining
  └───┘                                
                                       
  ~200 IOPS (HDD)                     ~50-200 MB/s sustained
  ~10K IOPS (SSD)                     ~1-3 GB/s (NVMe)
```

---

## 3. WAL Structure

### Log Segments

WAL is divided into fixed-size segment files for manageability:

```
pg_wal/ (PostgreSQL) or ib_logfile* (MySQL)
├── 000000010000000000000001   (16MB segment)
├── 000000010000000000000002   (16MB segment)
├── 000000010000000000000003   (16MB segment)  ← current write position
├── 000000010000000000000004   (pre-allocated, empty)
└── 000000010000000000000005   (pre-allocated, empty)

 Segment 1          Segment 2          Segment 3 (active)
┌──────────────┐   ┌──────────────┐   ┌──────────────────────────┐
│██████████████│   │██████████████│   │████████████░░░░░░░░░░░░░░│
│██████████████│   │██████████████│   │████████████░░░░░░░░░░░░░░│
│██████████████│   │██████████████│   │            ▲              │
└──────────────┘   └──────────────┘   └────────────│──────────────┘
  (full, can be      (full)              write     │
   recycled after                        position──┘
   checkpoint)
```

### Log Entry Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          WAL LOG ENTRY                                   │
├────────┬──────────┬──────┬────────┬───────────────┬──────────────┬─────┤
│  LSN   │  TxnID   │ Type │ PageID │ Before-Image  │ After-Image  │ CRC │
│(8 byte)│ (4 byte) │(1 B) │(6 byte)│  (variable)   │  (variable)  │(4 B)│
├────────┼──────────┼──────┼────────┼───────────────┼──────────────┼─────┤
│ 0x1A00 │  Txn#42  │ UPD  │ Pg#773 │ salary=50000  │ salary=75000 │ ... │
├────────┼──────────┼──────┼────────┼───────────────┼──────────────┼─────┤
│ 0x1A38 │  Txn#42  │ UPD  │ Pg#201 │ balance=1000  │ balance=950  │ ... │
├────────┼──────────┼──────┼────────┼───────────────┼──────────────┼─────┤
│ 0x1A70 │  Txn#42  │ CMT  │  N/A   │     N/A       │     N/A      │ ... │
├────────┼──────────┼──────┼────────┼───────────────┼──────────────┼─────┤
│ 0x1A78 │  Txn#43  │ INS  │ Pg#55  │     N/A       │ (new tuple)  │ ... │
└────────┴──────────┴──────┴────────┴───────────────┴──────────────┴─────┘

Entry Types:
  INS = Insert    UPD = Update    DEL = Delete
  CMT = Commit    ABT = Abort     CKP = Checkpoint
  CLR = Compensation Log Record (for undo operations)
```

### Log Sequence Number (LSN)

```
LSN = unique, monotonically increasing identifier for each log entry

┌────────────────────────────────────────────────────────────────┐
│                    LSN ENCODING                                  │
│                                                                  │
│  PostgreSQL: LSN = (segment_number, offset_within_segment)      │
│  Example: 0/16B3F80 = segment 0, offset 0x16B3F80              │
│                                                                  │
│  MySQL/InnoDB: LSN = byte offset from start of first log file   │
│  Example: LSN 234881024 = 234,881,024 bytes from beginning      │
│                                                                  │
│  Each data page stores the LSN of the last WAL entry that       │
│  modified it (PageLSN). This is how we know if a page is        │
│  "behind" the log during recovery.                              │
│                                                                  │
│  Data Page Header:                                               │
│  ┌─────────────────────────────────────────┐                    │
│  │ PageLSN: 0x1A38  │ Checksum │ ... data  │                    │
│  └─────────────────────────────────────────┘                    │
│                                                                  │
│  If WAL has entry LSN=0x1A70 for this page but PageLSN=0x1A38, │
│  the page is STALE and needs redo during recovery.              │
└────────────────────────────────────────────────────────────────┘
```

---

## 4. Write Path in Detail

### Complete Write Path

```
 Client                    Database Engine
   │                            │
   │  BEGIN; UPDATE salary=75K  │
   │───────────────────────────▶│
   │                            │
   │         ┌──────────────────┼─────────────────────────────────┐
   │         │ STEP 1: Acquire locks, read page into buffer pool  │
   │         │                  │                                  │
   │         │    Buffer Pool   │     Disk                         │
   │         │   ┌──────────┐  │   ┌──────────┐                  │
   │         │   │ Page 773 │◀─┼───│ Page 773 │ (if not cached)  │
   │         │   │ sal=50K  │  │   │ sal=50K  │                  │
   │         │   └──────────┘  │   └──────────┘                  │
   │         └──────────────────┼─────────────────────────────────┘
   │                            │
   │         ┌──────────────────┼─────────────────────────────────┐
   │         │ STEP 2: Write WAL entry to WAL buffer (memory)     │
   │         │                  │                                  │
   │         │   WAL Buffer (shared memory, ring buffer)          │
   │         │   ┌────┬────┬────┬────┬────┐                      │
   │         │   │prev│prev│ NEW│    │    │                      │
   │         │   │ent │ent │ ENT│    │    │                      │
   │         │   └────┴────┴────┴────┴────┘                      │
   │         │         LSN=0x1A00                                  │
   │         │         Txn#42, UPD, Pg773                         │
   │         │         before=50K, after=75K                      │
   │         └──────────────────┼─────────────────────────────────┘
   │                            │
   │         ┌──────────────────┼─────────────────────────────────┐
   │         │ STEP 3: Modify page IN MEMORY (dirty page)         │
   │         │                  │                                  │
   │         │    Buffer Pool   │                                  │
   │         │   ┌──────────┐  │                                  │
   │         │   │ Page 773 │  │  Page is now "dirty"             │
   │         │   │ sal=75K  │  │  PageLSN = 0x1A00               │
   │         │   │ DIRTY    │  │                                  │
   │         │   └──────────┘  │                                  │
   │         └──────────────────┼─────────────────────────────────┘
   │                            │
   │  COMMIT;                   │
   │───────────────────────────▶│
   │                            │
   │         ┌──────────────────┼─────────────────────────────────┐
   │         │ STEP 4: Write COMMIT record to WAL buffer          │
   │         │         WAL Buffer: [..., UPD, COMMIT]             │
   │         └──────────────────┼─────────────────────────────────┘
   │                            │
   │         ┌──────────────────┼─────────────────────────────────┐
   │         │ STEP 5: Flush WAL buffer to disk (fsync)           │
   │         │         *** THIS IS THE COMMIT POINT ***           │
   │         │                  │                                  │
   │         │   WAL Buffer ──fsync──▶ WAL on Disk               │
   │         │                  │      ┌────────────────┐         │
   │         │                  │      │ ...            │         │
   │         │                  │      │ LSN=0x1A00 UPD│         │
   │         │                  │      │ LSN=0x1A08 CMT│         │
   │         │                  │      └────────────────┘         │
   │         │                  │                                  │
   │         │   After this fsync, the transaction is DURABLE     │
   │         │   even if we crash before writing the data page    │
   │         └──────────────────┼─────────────────────────────────┘
   │                            │
   │◀───────────────────────────│  ACK: "COMMIT OK"
   │                            │
   │         ┌──────────────────┼─────────────────────────────────┐
   │         │ STEP 6: (LATER) Checkpoint / Background Writer     │
   │         │         Writes dirty pages to data files           │
   │         │                  │                                  │
   │         │    Buffer Pool   │     Disk (data files)           │
   │         │   ┌──────────┐  │   ┌──────────┐                  │
   │         │   │ Page 773 │──┼──▶│ Page 773 │                  │
   │         │   │ sal=75K  │  │   │ sal=75K  │  finally on disk │
   │         │   └──────────┘  │   └──────────┘                  │
   │         └──────────────────┼─────────────────────────────────┘
```

### The WAL Write Rule (Steal/No-Force)

```
┌──────────────────────────────────────────────────────────────────────┐
│                   BUFFER MANAGEMENT POLICIES                          │
├──────────────────┬───────────────────────────────────────────────────┤
│                  │  FORCE (write pages at commit)                     │
│                  │  YES                │  NO                          │
├──────────────────┼────────────────────┼──────────────────────────────┤
│ STEAL            │                    │                              │
│ (write dirty     │ YES: Steal/Force   │ YES: Steal/No-Force ◀━━━━━━━│
│ pages before     │   No WAL needed    │   *** ARIES / Most DBs ***  │
│ commit)          │   Terrible perf    │   Needs REDO + UNDO         │
│                  │                    │                              │
│                  │ NO: No-Steal/Force │ NO: No-Steal/No-Force       │
│                  │   Needs UNDO only  │   Needs REDO only           │
│                  │                    │   Limits buffer pool utility │
└──────────────────┴────────────────────┴──────────────────────────────┘

Steal/No-Force (what PostgreSQL, MySQL, Oracle all use):
  - STEAL: Can evict dirty pages from buffer pool before txn commits
    → Needs UNDO log (before-images) to rollback on crash
  - NO-FORCE: Don't have to flush data pages at commit time
    → Needs REDO log (after-images) to replay on crash
```

---

## 5. Recovery Process (ARIES Algorithm)

ARIES (Algorithm for Recovery and Isolation Exploiting Semantics) is the gold standard recovery algorithm used by virtually all modern databases.

### Overview

```
                         CRASH!
                           │
                           ▼
    ┌─────────────────────────────────────────────────────────┐
    │                   RECOVERY                               │
    │                                                          │
    │  ┌──────────┐     ┌──────────┐     ┌──────────┐        │
    │  │ ANALYSIS │────▶│   REDO   │────▶│   UNDO   │        │
    │  │  Phase   │     │  Phase   │     │  Phase   │        │
    │  └──────────┘     └──────────┘     └──────────┘        │
    │                                                          │
    │  "What happened?" "Redo history" "Undo losers"          │
    │                                                          │
    └─────────────────────────────────────────────────────────┘
```

### Phase 1: Analysis

```
┌──────────────────────────────────────────────────────────────────────┐
│                       ANALYSIS PHASE                                   │
│                                                                        │
│  Start from last checkpoint record in WAL, scan forward:              │
│                                                                        │
│  WAL:  ... │CKPT│ T1:UPD │ T2:UPD │ T1:CMT │ T3:UPD │ T2:UPD │CRASH│
│             ▲                                                    ▲    │
│             │                                                    │    │
│        last checkpoint                                      crash│    │
│                                                             point│    │
│  Build two tables:                                                    │
│                                                                        │
│  1. Transaction Table (active transactions at crash):                 │
│     ┌───────────┬────────────┬──────────────┐                         │
│     │  TxnID    │   Status   │  LastLSN     │                         │
│     ├───────────┼────────────┼──────────────┤                         │
│     │  T2       │  ACTIVE    │  0x1B20      │ ← needs UNDO           │
│     │  T3       │  ACTIVE    │  0x1B10      │ ← needs UNDO           │
│     └───────────┴────────────┴──────────────┘                         │
│     (T1 committed before crash, not in this table)                    │
│                                                                        │
│  2. Dirty Page Table (pages potentially not flushed):                 │
│     ┌───────────┬──────────────┐                                      │
│     │  PageID   │  RecLSN      │  (first LSN that dirtied this page) │
│     ├───────────┼──────────────┤                                      │
│     │  Pg#773   │  0x1A00      │                                      │
│     │  Pg#201   │  0x1A38      │                                      │
│     │  Pg#55    │  0x1B10      │                                      │
│     └───────────┴──────────────┘                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Phase 2: Redo

```
┌──────────────────────────────────────────────────────────────────────┐
│                         REDO PHASE                                     │
│                                                                        │
│  "Repeat history" — redo ALL changes from earliest RecLSN forward,   │
│  regardless of whether the transaction committed or not.              │
│                                                                        │
│  For each WAL entry with LSN >= min(RecLSN in Dirty Page Table):     │
│                                                                        │
│    IF page is in Dirty Page Table                                     │
│    AND entry's LSN >= RecLSN for that page                           │
│    AND page's on-disk PageLSN < entry's LSN                          │
│    THEN:                                                              │
│       Apply the after-image to the page                              │
│                                                                        │
│  WAL:  ─────────────────────────────────────────────────▶            │
│         │                                               │            │
│         ▼ start redo here (min RecLSN)                  ▼            │
│    ┌────┬────┬────┬────┬────┬────┬────┐                              │
│    │ E1 │ E2 │ E3 │ E4 │ E5 │ E6 │ E7 │                             │
│    │redo│redo│skip│redo│redo│skip│redo│                              │
│    └────┴────┴────┴────┴────┴────┴────┘                              │
│      │         │          │         │                                 │
│      │    (page already   │    (page already                         │
│      │     up to date)    │     up to date)                          │
│      ▼                    ▼                                           │
│    ┌──────┐           ┌──────┐                                       │
│    │Pg 773│           │Pg 55 │   Pages brought to crash-time state   │
│    └──────┘           └──────┘                                       │
│                                                                        │
│  After redo: database is in EXACT state it was at crash moment        │
│  (including uncommitted changes — those will be undone next)          │
└──────────────────────────────────────────────────────────────────────┘
```

### Phase 3: Undo

```
┌──────────────────────────────────────────────────────────────────────┐
│                         UNDO PHASE                                     │
│                                                                        │
│  Rollback all transactions that were active (uncommitted) at crash.  │
│  Walk backwards through WAL using prevLSN pointers.                  │
│                                                                        │
│  For each "loser" transaction (T2, T3 from analysis):                │
│    Follow its chain of log entries backwards                         │
│    Apply before-images to undo each change                           │
│    Write CLR (Compensation Log Record) for each undo                 │
│                                                                        │
│  WAL traversal for T2:                                                │
│                                                                        │
│    T2:UPD ◀──── T2:UPD ◀──── (start of T2)                          │
│    LSN=0x1B20   LSN=0x1A38                                           │
│       │            │                                                  │
│       │ undo       │ undo                                             │
│       ▼            ▼                                                  │
│    Write CLR    Write CLR                                             │
│    (restore     (restore                                              │
│    before-img)  before-img)                                           │
│                                                                        │
│  CLRs ensure that if we crash DURING recovery, we don't              │
│  re-undo already undone work. CLRs are never undone themselves.      │
│                                                                        │
│  After undo: database is in a CONSISTENT state                        │
│  All committed txns' effects are present                             │
│  All uncommitted txns' effects are removed                           │
└──────────────────────────────────────────────────────────────────────┘
```

### Checkpoint Mechanism

```
┌──────────────────────────────────────────────────────────────────────┐
│                       CHECKPOINTING                                   │
│                                                                        │
│  Purpose: Limit how far back recovery must scan                      │
│                                                                        │
│  Fuzzy Checkpoint (non-blocking, used by most modern DBs):           │
│                                                                        │
│  1. Write BEGIN_CHECKPOINT to WAL                                    │
│  2. Record current Transaction Table + Dirty Page Table              │
│  3. Write END_CHECKPOINT to WAL (with tables embedded)               │
│  4. Background: flush dirty pages whose RecLSN < checkpoint LSN     │
│  5. Update "master record" pointer to this checkpoint                │
│                                                                        │
│  Timeline:                                                            │
│  ──────────────────────────────────────────────────────────▶ time    │
│        │           │                    │              │               │
│        │CKPT       │                    │CKPT          │CRASH          │
│        │           │                    │              │               │
│        ▼           │                    ▼              │               │
│  Without checkpoints: must scan from here ─────────────┤               │
│  With checkpoint: only scan from here ─────────────────┤               │
│                                                                        │
│  Checkpoint frequency trade-off:                                      │
│    Frequent: shorter recovery, more I/O during normal operation       │
│    Infrequent: longer recovery, less I/O overhead                    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 6. Log Compaction / Truncation

### When Can Log Segments Be Deleted?

```
┌──────────────────────────────────────────────────────────────────────┐
│                  LOG SEGMENT LIFECYCLE                                 │
│                                                                        │
│  Segment 1    Segment 2    Segment 3    Segment 4    Segment 5       │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐        │
│  │████████│  │████████│  │████████│  │████░░░░│  │░░░░░░░░│        │
│  └────────┘  └────────┘  └────────┘  └────────┘  └────────┘        │
│       ▲            ▲           ▲           ▲                         │
│       │            │           │           └── write position         │
│       │            │           └── last checkpoint                    │
│       │            └── oldest replication slot                        │
│       └── CAN BE DELETED (or recycled)                               │
│                                                                        │
│  A segment is safe to delete when ALL of:                            │
│    1. All entries are before last successful checkpoint               │
│    2. All entries have been shipped to all replicas                   │
│    3. No active transaction references entries in it                  │
│    4. Not needed for point-in-time recovery (PITR) archive           │
│                                                                        │
│  min_required_LSN = min(                                              │
│      checkpoint_LSN,                                                  │
│      oldest_replication_slot_LSN,                                     │
│      oldest_active_txn_start_LSN,                                    │
│      archive_requirement_LSN                                          │
│  )                                                                    │
└──────────────────────────────────────────────────────────────────────┘
```

### Log Rotation Strategies

| Strategy | Description | Used By |
|----------|-------------|---------|
| **Circular** | Fixed number of files, overwrite oldest | MySQL InnoDB (ib_logfile0, ib_logfile1) |
| **Segmented + Archive** | New segments created, old ones archived then deleted | PostgreSQL (pg_wal + archive) |
| **Segmented + Recycle** | Old segment files renamed and reused as new | PostgreSQL (recycles segment files) |
| **Size-bounded** | Keep total WAL under max size, delete oldest | etcd (--max-wals flag) |

### Balancing Disk vs Recovery Time

```
More WAL retained:                    Less WAL retained:
  + Longer PITR window                  + Less disk usage
  + Replicas can fall further behind    + Simpler management
  + More "safety net"                   - Short PITR window
  - More disk consumption               - Replicas must re-sync if too far behind
  - Longer archive operations           - Less margin for error
```

---

## 7. Group Commit Optimization

### The Problem with Per-Transaction fsync

```
Without Group Commit:

  T1: write WAL → fsync (5ms) → ack
  T2:                            write WAL → fsync (5ms) → ack
  T3:                                                       write WAL → fsync (5ms) → ack

  Throughput: ~200 TPS (1000ms / 5ms per fsync)

With Group Commit:

  T1: write WAL ─┐
  T2: write WAL ─┼─ single fsync (5ms) → ack T1, T2, T3
  T3: write WAL ─┘

  Throughput: thousands of TPS (amortized fsync cost)
```

### How Group Commit Works

```
┌──────────────────────────────────────────────────────────────────────┐
│                    GROUP COMMIT MECHANISM                              │
│                                                                        │
│  Time ──────────────────────────────────────────────────────────▶    │
│                                                                        │
│  WAL Buffer:                                                          │
│    │ T1 │ T2 │ T3 │ T4 │ T5 │                                       │
│    └─────────────────────────┘                                        │
│              │                                                         │
│              ▼  (commit_delay window: e.g., 10μs-1ms)                │
│         Wait briefly for more transactions to join the group          │
│              │                                                         │
│              ▼                                                         │
│    ┌─────────────────────────┐                                        │
│    │   SINGLE fsync()        │  One disk flush for all 5 txns        │
│    └─────────────────────────┘                                        │
│              │                                                         │
│              ▼                                                         │
│    Notify T1, T2, T3, T4, T5: "committed"                            │
│                                                                        │
│  Trade-off:                                                           │
│    commit_delay=0: lowest latency per txn, lowest throughput          │
│    commit_delay=10ms: +10ms latency, 10-50x throughput improvement   │
└──────────────────────────────────────────────────────────────────────┘
```

### PostgreSQL Group Commit

- `commit_delay` — microseconds to wait for more txns before fsyncing (default: 0)
- `commit_siblings` — min concurrent txns before commit_delay kicks in (default: 5)
- Leader/follower model: first committer becomes "flush leader", others queue behind it
- Leader flushes once and wakes all followers

### MySQL/InnoDB Group Commit

Three-stage pipeline (FLUSH → SYNC → COMMIT):

```
Stage 1 (FLUSH):   Gather transactions, write to OS buffer
Stage 2 (SYNC):    Single fsync() for the entire group
Stage 3 (COMMIT):  Mark transactions as committed in memory

binlog_group_commit_sync_delay = 0-1000000 μs
binlog_group_commit_sync_no_delay_count = N (flush after N txns regardless)
```

---

## 8. WAL in Replication

### Physical Replication (WAL Shipping)

```
┌──────────────────────────────────────────────────────────────────────┐
│                PHYSICAL (WAL) REPLICATION                              │
│                                                                        │
│   Primary                              Replica                        │
│  ┌────────────────────┐              ┌────────────────────┐          │
│  │                    │              │                    │          │
│  │  ┌─────────────┐  │   WAL Ship   │  ┌─────────────┐  │          │
│  │  │   WAL       │──┼──────────────┼─▶│   WAL       │  │          │
│  │  │ (pg_wal/)   │  │  (streaming) │  │  (received) │  │          │
│  │  └──────┬──────┘  │              │  └──────┬──────┘  │          │
│  │         │         │              │         │ replay  │          │
│  │         ▼         │              │         ▼         │          │
│  │  ┌─────────────┐  │              │  ┌─────────────┐  │          │
│  │  │ Data Pages  │  │              │  │ Data Pages  │  │          │
│  │  └─────────────┘  │              │  └─────────────┘  │          │
│  │                    │              │                    │          │
│  └────────────────────┘              └────────────────────┘          │
│                                                                        │
│  Modes:                                                               │
│    Async:  Primary doesn't wait. Replica may lag.                    │
│    Sync:   Primary waits for replica to write WAL (durable).         │
│    Remote-apply: Primary waits for replica to replay WAL.            │
│                                                                        │
│  PostgreSQL Streaming Replication:                                    │
│    - WAL sender process on primary                                   │
│    - WAL receiver process on replica                                 │
│    - Streams WAL records as they're generated                        │
│    - Replication slots track consumer position                       │
│    - Hot standby: replica can serve read queries while replaying     │
└──────────────────────────────────────────────────────────────────────┘
```

### Logical Replication (MySQL Binlog)

```
┌──────────────────────────────────────────────────────────────────────┐
│               LOGICAL REPLICATION (MySQL Binlog)                       │
│                                                                        │
│  MySQL uses a separate "binary log" that records logical changes:    │
│                                                                        │
│  InnoDB Redo Log (physical WAL):                                     │
│    "Page 773, offset 42, write bytes 0x..."                          │
│    Used ONLY for crash recovery, not shipped to replicas             │
│                                                                        │
│  Binary Log (logical WAL):                                           │
│    "UPDATE employees SET salary=75000 WHERE id=42"  (statement)      │
│    or: "Row(id=42): salary 50000→75000"             (row-based)      │
│    Shipped to replicas for replication                                │
│                                                                        │
│  Flow:                                                                │
│    Client → InnoDB redo log → Binlog → Commit                        │
│                                    │                                  │
│                                    ├──▶ Replica 1 (SQL thread apply) │
│                                    └──▶ Replica 2                    │
│                                                                        │
│  Advantage of logical WAL for replication:                           │
│    - Version-independent (replicas can run different versions)       │
│    - Can replicate to different storage engines                      │
│    - Selective replication (filter by database/table)                │
│    - Can feed into external systems (CDC → Kafka, Debezium)         │
│                                                                        │
│  Disadvantage:                                                        │
│    - Non-deterministic functions (NOW(), RAND()) need special care   │
│    - Schema must be compatible                                       │
│    - Slower than physical replication for high-throughput             │
└──────────────────────────────────────────────────────────────────────┘
```

### Kafka's Commit Log as Distributed WAL

```
┌──────────────────────────────────────────────────────────────────────┐
│                  KAFKA COMMIT LOG                                      │
│                                                                        │
│  Kafka IS a distributed WAL. The log is the primary data structure.  │
│                                                                        │
│  Topic: "orders" Partition 0                                          │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐                 │
│  │  0  │  1  │  2  │  3  │  4  │  5  │  6  │  7  │ ← offsets       │
│  └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘                 │
│                                              ▲                        │
│                                              │ LEO (Log End Offset)   │
│                                                                        │
│  Replication:                                                         │
│    Leader (Broker 1): [0,1,2,3,4,5,6,7]                             │
│    Follower (Broker 2): [0,1,2,3,4,5,6]  ← ISR, slightly behind    │
│    Follower (Broker 3): [0,1,2,3,4,5,6]  ← ISR                     │
│                                                                        │
│    HW (High Watermark) = 6  (all ISR members have up to 6)          │
│    Consumers can only read up to HW                                  │
│                                                                        │
│  WAL properties in Kafka:                                            │
│    - Append-only (immutable once written)                            │
│    - Ordered within partition                                        │
│    - Durable (replicated across brokers)                             │
│    - Offset = LSN equivalent                                         │
│    - Log compaction = keep latest value per key                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 9. Real-World Implementations

### PostgreSQL WAL

```
Architecture:
  pg_wal/ directory (formerly pg_xlog/)
  Default segment size: 16MB (configurable at initdb with --wal-segsize)
  WAL level: minimal, replica, logical

Key parameters:
  wal_level = replica          # What to log
  max_wal_size = 1GB           # Trigger checkpoint when WAL reaches this
  min_wal_size = 80MB          # Always keep at least this much WAL
  wal_buffers = 16MB           # Shared memory for WAL before flush
  synchronous_commit = on      # Wait for WAL flush before ack
  full_page_writes = on        # Write full page on first modification after checkpoint
                                # (prevents torn pages)

Recovery: ARIES-style with some simplifications
  - No explicit UNDO phase (PostgreSQL uses MVCC, so old row versions exist in-place)
  - REDO only during recovery
  - "Full page images" (FPI) after checkpoint eliminate torn page problem

WAL record format:
  ┌────────────┬──────────┬────────────┬───────────────────────┐
  │ XLogRecord │ BlockRef │ BlockRef   │ Payload (after-image) │
  │ header     │ (page 1) │ (page 2)  │                       │
  └────────────┴──────────┴────────────┴───────────────────────┘
```

### MySQL/InnoDB Redo Log

```
Architecture:
  Fixed circular log files: ib_logfile0, ib_logfile1 (or innodb_redo/ in 8.0.30+)
  MySQL 8.0.30+: Dynamic redo log in #innodb_redo/ directory

  ib_logfile0          ib_logfile1
  ┌────────────────┐  ┌────────────────┐
  │ ████████████░░ │  │ ░░░░░░░░░░░░░░ │
  │        ▲    ▲  │  │                │
  │        │    │  │  │                │
  │    checkpoint  │  │                │
  │        write───┘  │                │
  └────────────────┘  └────────────────┘
       (circular — wraps around)

Key parameters:
  innodb_log_file_size = 1GB        # Size of each redo log file
  innodb_log_files_in_group = 2     # Number of redo log files
  innodb_flush_log_at_trx_commit:
    = 1: fsync on every commit (safest, slowest)
    = 2: write to OS buffer on commit, fsync every second
    = 0: write+fsync every second (fastest, up to 1s data loss)

Doublewrite Buffer:
  InnoDB pages are 16KB, but OS may write 4KB atomically.
  Torn page problem: crash during 16KB write → corrupted page.
  Solution: write pages to doublewrite buffer FIRST (sequential),
  then write to actual location. On recovery, check doublewrite buffer
  for clean copies of any torn pages.
```

### SQLite WAL Mode

```
Two modes:
  1. Rollback Journal (default before 3.7.0):
     - Copy original page to journal BEFORE modifying
     - On crash: copy journal pages back to restore original state
     - Write barrier: journal must be flushed before main DB modified

  2. WAL Mode (recommended for concurrency):
     - Append changes to WAL file (-wal)
     - Readers see consistent snapshot from main DB + WAL
     - Checkpoint: transfer WAL changes back to main DB

  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
  │  main.db     │    │  main.db-wal │    │ main.db-shm  │
  │  (original   │    │  (new changes│    │ (shared mem   │
  │   pages)     │    │   appended)  │    │  WAL index)  │
  └──────────────┘    └──────────────┘    └──────────────┘

  Readers: check WAL for latest version, fall back to main DB
  Writers: append to WAL (no blocking readers!)
  Checkpoint: merge WAL back into main DB (PASSIVE/FULL/RESTART/TRUNCATE)
```

### Apache Kafka

```
Kafka's entire storage IS a commit log:
  /var/kafka-logs/topic-partition/
  ├── 00000000000000000000.log      # Segment file (messages)
  ├── 00000000000000000000.index    # Offset → position index
  ├── 00000000000000000000.timeindex
  ├── 00000000000052345678.log      # Next segment
  └── ...

  Producer → Leader Broker → append to partition log → replicate to followers
  No separate "WAL + data" — the log IS the data.

  Durability: acks=all means all ISR brokers have the record before ack.
  Retention: time-based (7 days default) or size-based or compaction.
```

### etcd WAL

```
etcd uses WAL for Raft log persistence:
  /var/lib/etcd/member/
  ├── wal/
  │   ├── 0000000000000000-0000000000000000.wal
  │   └── 0000000000000001-0000000000001234.wal
  └── snap/
      └── 0000000000000002-0000000000005678.snap  (snapshot = checkpoint)

  Raft entry → WAL append → fsync → apply to BoltDB (state machine)
  Snapshots periodically taken to truncate WAL.
  --max-wals: max WAL files to keep (default: 5)
  --snapshot-count: entries between snapshots (default: 100,000)
```

### RocksDB / LevelDB WAL

```
Write path:
  Put(key, value) → WAL append → memtable insert → ack

  WAL files: /db/000123.log
  Each memtable has a corresponding WAL file.
  When memtable is flushed to SST file, its WAL is deleted.

  Options:
    WriteOptions::sync = true     # fsync every write (slow but safe)
    WriteOptions::sync = false    # OS buffered (default, faster)
    manual_wal_flush = true       # Application controls flush timing

  WAL record format:
  ┌──────────┬────────┬──────┬─────────┐
  │ checksum │ length │ type │ payload │
  │  (4B)    │  (2B)  │ (1B) │  (var)  │
  └──────────┴────────┴──────┴─────────┘
  Types: FULL, FIRST, MIDDLE, LAST (for records spanning blocks)
```

### CockroachDB

```
CockroachDB uses Raft consensus where the Raft log serves as WAL:

  Client → SQL → DistSQL → Raft proposal → Raft log (WAL) → Apply to Pebble (RocksDB fork)

  Each Range (shard) has its own Raft group.
  Raft log entries = WAL entries for that range's state machine.
  Pebble (storage engine) also has its own WAL for the local KV store.

  Two levels of WAL:
    1. Raft log: distributed consensus WAL (replicated across nodes)
    2. Pebble WAL: local storage engine WAL (per-node crash recovery)
```

---

## 10. Performance Considerations

### Sequential vs Random Write Performance

```
┌──────────────────────────────────────────────────────────────────────┐
│                    I/O PERFORMANCE COMPARISON                          │
│                                                                        │
│  Device          Sequential Write    Random Write (4KB)   Ratio      │
│  ─────────────────────────────────────────────────────────────────    │
│  HDD (7200rpm)   100-200 MB/s        0.5-1 MB/s          100-200x   │
│  SATA SSD        400-550 MB/s        50-100 MB/s         5-10x      │
│  NVMe SSD        2-7 GB/s            200-800 MB/s        5-10x      │
│  Intel Optane     2.5 GB/s           500 MB/s-2 GB/s     2-5x       │
│                                                                        │
│  WAL impact: On HDD, WAL gives 100x improvement                     │
│              On NVMe, benefit is smaller but still significant        │
│              (batching + fewer fsyncs still matter on NVMe)           │
└──────────────────────────────────────────────────────────────────────┘
```

### fsync Strategies

| Strategy | Durability | Performance | Use Case |
|----------|-----------|-------------|----------|
| fsync every commit | Highest (zero data loss) | Lowest | Financial systems |
| Group commit (batched fsync) | High (sub-ms window) | High | Most OLTP |
| Periodic fsync (e.g., every 1s) | Moderate (up to 1s loss) | Highest | Logging, analytics |
| No fsync (OS decides) | Lowest | Maximum | Ephemeral data, caches |

### Direct I/O vs Buffered I/O for WAL

```
Buffered I/O (default):
  App → OS Page Cache → Disk
  + OS can batch writes
  + Read-ahead benefits
  - Double buffering (WAL buffer + page cache) wastes RAM
  - fsync flushes entire page cache for that file (expensive)

Direct I/O (O_DIRECT):
  App → Disk (bypasses page cache)
  + No double buffering
  + Predictable fsync latency (only your data)
  + WAL buffer in user space is sufficient
  - Must align writes to block boundaries
  - No OS write coalescing

  PostgreSQL: Uses buffered I/O for WAL (relies on OS for efficiency)
  MySQL/InnoDB: innodb_flush_method=O_DIRECT (direct I/O for data files)
  RocksDB: use_direct_io_for_flush_and_compaction option
```

### NVMe/SSD Considerations

- **Write amplification**: SSD writes in large blocks (128KB-4MB). Writing 4KB still erases/programs a full block internally.
- **WAL on separate device**: Dedicated NVMe for WAL eliminates contention with data file reads.
- **Parallel I/O**: NVMe supports 64K I/O queues × 64K depth. WAL is inherently serial, but group commit amortizes this.
- **Power-loss protection**: Enterprise NVMe with capacitor-backed cache ensures fsync is truly durable. Consumer SSDs may lie about fsync completion.

---

## 11. WAL vs Event Sourcing

```
┌──────────────────────────────────────────────────────────────────────┐
│                  WAL vs EVENT SOURCING                                 │
├────────────────────────┬─────────────────────────────────────────────┤
│       Aspect           │   WAL                │  Event Sourcing      │
├────────────────────────┼──────────────────────┼──────────────────────┤
│ Purpose                │ Crash recovery &     │ Primary source of    │
│                        │ durability           │ truth for business   │
│                        │                      │ state                │
├────────────────────────┼──────────────────────┼──────────────────────┤
│ Visibility             │ Infrastructure-level │ Application-level    │
│                        │ (hidden from app)    │ (explicit in domain) │
├────────────────────────┼──────────────────────┼──────────────────────┤
│ Retention              │ Truncated after      │ Kept forever         │
│                        │ checkpoint           │ (the log IS state)   │
├────────────────────────┼──────────────────────┼──────────────────────┤
│ Granularity            │ Physical (page-level │ Logical (domain      │
│                        │ byte changes)        │ events: OrderPlaced) │
├────────────────────────┼──────────────────────┼──────────────────────┤
│ Replay                 │ Reconstruct pages    │ Reconstruct business │
│                        │ to crash state       │ entity to any point  │
├────────────────────────┼──────────────────────┼──────────────────────┤
│ Consumers              │ Recovery subsystem   │ Projections, sagas,  │
│                        │ only                 │ other services       │
├────────────────────────┼──────────────────────┼──────────────────────┤
│ Schema                 │ Binary, internal     │ Versioned, evolvable │
│                        │ format               │ contracts            │
├────────────────────────┼──────────────────────┼──────────────────────┤
│ Compaction             │ Delete after ckpt    │ Snapshotting (keep   │
│                        │                      │ events too)          │
├────────────────────────┼──────────────────────┼──────────────────────┤
│ Examples               │ pg_wal, ib_logfile   │ EventStoreDB, Axon,  │
│                        │ RocksDB .log         │ Kafka (as event log) │
└────────────────────────┴──────────────────────┴──────────────────────┘

Key Insight: WAL is a MEANS (for durability), Event Sourcing is an
ARCHITECTURE PATTERN (for the entire system's state management).
You can use both: Event store backed by a database that uses WAL internally.
```

---

## 12. Architect's Guide

### WAL Configuration Tuning

```
┌──────────────────────────────────────────────────────────────────────┐
│                 CONFIGURATION DECISION TREE                            │
│                                                                        │
│  What's your durability requirement?                                  │
│  ├── Zero data loss → fsync every commit (synchronous_commit=on)     │
│  ├── Sub-second loss OK → group commit with delay                    │
│  └── Multi-second loss OK → periodic flush (innodb_flush=2)          │
│                                                                        │
│  What's your write throughput?                                        │
│  ├── < 1K TPS → default settings are fine                            │
│  ├── 1K-50K TPS → group commit, dedicated WAL disk                   │
│  └── > 50K TPS → group commit + large WAL buffers + NVMe            │
│                                                                        │
│  What's your recovery time objective (RTO)?                           │
│  ├── < 10s → aggressive checkpointing (every 30s-1min)              │
│  ├── < 60s → moderate checkpointing (every 5min)                    │
│  └── < 5min → infrequent checkpointing (every 15-30min)            │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Metrics to Monitor

| Metric | What It Tells You | Alert Threshold |
|--------|-------------------|-----------------|
| WAL write rate (MB/s) | Write load on WAL | >80% of disk bandwidth |
| WAL disk usage | Segment accumulation | Approaching disk capacity |
| Checkpoint duration | I/O spike intensity | >50% of checkpoint interval |
| Checkpoint frequency | Recovery window | Too infrequent = long recovery |
| Replication lag (bytes) | Replica falling behind | >1GB or growing |
| fsync latency (p99) | Disk/controller health | >50ms (HDD), >5ms (SSD) |
| WAL buffer full waits | Buffer too small | Any occurrence |
| Oldest active transaction | Long-running txn blocking truncation | >10 min |

### Capacity Planning

```
WAL disk size estimation:
  WAL generation rate = (rows_modified/sec) × (avg_WAL_bytes_per_row)

  PostgreSQL rule of thumb:
    ~200-500 bytes per row modification in WAL
    At 10,000 modifications/sec:
      10,000 × 300 bytes = 3 MB/s = 180 MB/min = ~10 GB/hour

  Required WAL space:
    = WAL_generation_rate × max(checkpoint_interval, replication_lag_allowance)
    = 3 MB/s × 300s (5-min checkpoint) = 900 MB minimum
    + 2x safety margin = ~2 GB

  For PITR/archiving:
    = WAL_generation_rate × PITR_window
    = 3 MB/s × 86400s (24h) = 259 GB for 24h PITR
```

### Production Checklist

```
□ WAL on separate physical device from data (eliminates I/O contention)
□ Enterprise-grade storage with power-loss protection
□ Monitoring for WAL growth, fsync latency, checkpoint duration
□ Automated alerting on replication lag exceeding threshold
□ Regular PITR restore testing (backup is useless if restore doesn't work)
□ WAL archiving configured and verified for point-in-time recovery
□ Checkpoint tuning: balance between recovery time and I/O overhead
□ Connection pooling to enable effective group commit
□ Tested crash recovery procedure with documented RTO
□ Log segment size tuned for workload (larger = fewer file operations)
```

### Common Failure Modes

| Failure | Cause | Mitigation |
|---------|-------|------------|
| WAL disk full | Replication slot preventing truncation | Monitor + alert on WAL size, drop stale slots |
| Torn WAL write | Power loss mid-write | CRC per record, skip incomplete final record |
| WAL corruption | Bit rot, firmware bug | Checksums, WAL archive on separate storage |
| Slow recovery | Infrequent checkpoints + large WAL | Tune checkpoint_completion_target, increase frequency |
| Performance cliff | WAL and data on same disk | Separate disks or use NVMe with sufficient bandwidth |

---

## Summary

```
┌──────────────────────────────────────────────────────────────────────┐
│                    WAL IN ONE PICTURE                                  │
│                                                                        │
│    Client                                                             │
│      │                                                                │
│      ▼                                                                │
│  ┌────────┐   1. append    ┌────────────────────────────┐            │
│  │ Engine │──────────────▶ │ WAL (sequential, durable)  │            │
│  └────────┘                └──────────────┬─────────────┘            │
│      │                                    │                           │
│      │ 2. ack client                      │ 3. ship to replicas      │
│      │    (after fsync)                   │                           │
│      │                                    ▼                           │
│      │                            ┌──────────────┐                   │
│      │ 4. checkpoint              │   Replicas   │                   │
│      │    (background)            └──────────────┘                   │
│      ▼                                                                │
│  ┌────────────┐                                                       │
│  │ Data Files │  (eventually consistent with WAL)                    │
│  └────────────┘                                                       │
│                                                                        │
│  On crash: replay WAL from last checkpoint → consistent state        │
└──────────────────────────────────────────────────────────────────────┘

The WAL is arguably the single most important data structure in
database engineering. It transforms the intractable problem of
random durable writes into the tractable problem of sequential
durable writes, enabling modern databases to achieve both high
performance AND strong durability guarantees.
```
