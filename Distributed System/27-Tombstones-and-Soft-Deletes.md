# Tombstones and Soft Deletes in Distributed Systems

## 1. Problem Statement

In distributed systems with eventual consistency, **deleting data is one of the hardest problems to solve correctly**. The fundamental issue is that "absence of information" is indistinguishable from "information that hasn't arrived yet."

When you remove data from one replica, other replicas that still hold that data have no way to distinguish between:
- "This data was explicitly deleted" (should stay deleted)
- "This data exists but hasn't replicated to me yet" (should be restored)

This ambiguity leads to the **resurrection problem** — deleted data reappearing after anti-entropy synchronization.

```
┌─────────────────────────────────────────────────────────────────────┐
│                  THE FUNDAMENTAL TENSION                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   In a system that propagates PRESENCE of data via replication,     │
│   how do you propagate ABSENCE of data?                             │
│                                                                     │
│   Answer: You cannot use absence to represent deletion.             │
│           You must use PRESENCE of a deletion marker.               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. The Resurrection Problem

### Scenario

Consider a 3-node eventually consistent cluster storing key-value pairs:

```
Timeline of the Resurrection Problem
═════════════════════════════════════

t=0: All replicas consistent
┌──────────┐    ┌──────────┐    ┌──────────┐
│  Node A  │    │  Node B  │    │  Node C  │
│          │    │          │    │          │
│  K = V   │    │  K = V   │    │  K = V   │
│  (t=1)   │    │  (t=1)   │    │  (t=1)   │
└──────────┘    └──────────┘    └──────────┘

t=5: Client deletes K on Node A (simple removal)
┌──────────┐    ┌──────────┐    ┌──────────┐
│  Node A  │    │  Node B  │    │  Node C  │
│          │    │          │    │          │
│  (empty) │    │  K = V   │    │  K = V   │
│           │    │  (t=1)   │    │  (t=1)   │
└──────────┘    └──────────┘    └──────────┘
      │                                │
      │   DELETE succeeded locally     │
      │                                │

t=10: Anti-entropy/Gossip runs between Node C and Node A
┌──────────┐         ┌──────────┐
│  Node A  │◄────────│  Node C  │
│          │  "Hey,  │          │
│  (empty) │  you're │  K = V   │
│          │  missing│  (t=1)   │
│          │  K=V!"  │          │
└──────────┘         └──────────┘
      │
      ▼

t=10: K is RESURRECTED on Node A!
┌──────────┐    ┌──────────┐    ┌──────────┐
│  Node A  │    │  Node B  │    │  Node C  │
│          │    │          │    │          │
│  K = V   │    │  K = V   │    │  K = V   │
│  (t=1)   │    │  (t=1)   │    │  (t=1)   │
└──────────┘    └──────────┘    └──────────┘

  ╔═══════════════════════════════════════════════╗
  ║  DELETE IS LOST! Data resurrected on Node A.  ║
  ║  The system has NO MEMORY of the deletion.    ║
  ╚═══════════════════════════════════════════════╝
```

### Why This Happens

Anti-entropy protocols (Merkle trees, read-repair, hinted handoff) are designed to detect **missing data** and fill gaps. When Node A physically removes data, it looks identical to "Node A never received this write." The protocol dutifully "repairs" Node A by sending the data back.

### The Core Insight

> **Absence of data cannot represent a delete in an eventually consistent system.**
> You need a positive assertion — a piece of data that says "this key was deleted."

---

## 3. The Tombstone Solution

A **tombstone** is a special marker written in place of deleted data. It is a first-class record that participates in replication just like any other write.

### Tombstone Structure

```
┌─────────────────────────────────────────────┐
│              TOMBSTONE RECORD                │
├─────────────────────────────────────────────┤
│  key:        K                              │
│  type:       DELETE                         │
│  timestamp:  T_delete                       │
│  metadata:   {deleted_by, TTL, scope, ...}  │
│  value:      null / empty                   │
└─────────────────────────────────────────────┘
```

### How It Works

Instead of removing data, the system writes a tombstone that:
1. Supersedes the original value (delete timestamp > write timestamp)
2. Propagates to all replicas via normal replication channels
3. Wins conflict resolution against older writes (LWW — Last Write Wins)

### Tombstone Propagation

```
t=0: All replicas consistent
┌──────────┐    ┌──────────┐    ┌──────────┐
│  Node A  │    │  Node B  │    │  Node C  │
│  K = V   │    │  K = V   │    │  K = V   │
│  (t=1)   │    │  (t=1)   │    │  (t=1)   │
└──────────┘    └──────────┘    └──────────┘

t=5: Client issues DELETE K → Node A writes tombstone
┌──────────────┐    ┌──────────┐    ┌──────────┐
│   Node A     │    │  Node B  │    │  Node C  │
│              │    │          │    │          │
│  K = ⚰️ DEL  │    │  K = V   │    │  K = V   │
│  (t=5)       │    │  (t=1)   │    │  (t=1)   │
└──────────────┘    └──────────────────────────┘

t=8: Tombstone replicates to Node B via gossip
┌──────────────┐    ┌──────────────┐    ┌──────────┐
│   Node A     │    │   Node B     │    │  Node C  │
│              │    │              │    │          │
│  K = ⚰️ DEL  │───▶│  K = ⚰️ DEL  │    │  K = V   │
│  (t=5)       │    │  (t=5)       │    │  (t=1)   │
└──────────────┘    └──────────────┘    └──────────┘
                          │
                     B receives tombstone.
                     t=5 > t=1, so tombstone wins.
                     B marks K as deleted.

t=12: Tombstone replicates to Node C
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Node A     │    │   Node B     │    │   Node C     │
│              │    │              │    │              │
│  K = ⚰️ DEL  │    │  K = ⚰️ DEL  │    │  K = ⚰️ DEL  │
│  (t=5)       │    │  (t=5)       │    │  (t=5)       │
└──────────────┘    └──────────────┘    └──────────────┘

  ╔══════════════════════════════════════════════════════╗
  ║  All replicas agree: K is deleted.                  ║
  ║  Anti-entropy sees matching tombstones — no repair. ║
  ║  Resurrection is PREVENTED.                         ║
  ╚══════════════════════════════════════════════════════╝
```

### Conflict Resolution with Tombstones

```
┌─────────────────────────────────────────────────────────────┐
│              CONFLICT RESOLUTION RULES                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  When a node receives data for key K:                       │
│                                                             │
│  IF local_timestamp(K) < incoming_timestamp(K):             │
│      Accept incoming (whether write or tombstone)           │
│                                                             │
│  IF local_timestamp(K) > incoming_timestamp(K):             │
│      Reject incoming (local is newer)                       │
│                                                             │
│  IF local_timestamp(K) == incoming_timestamp(K):            │
│      Tiebreaker (e.g., node ID, value hash)                 │
│                                                             │
│  KEY INSIGHT: A tombstone at t=5 beats a write at t=1       │
│              but loses to a write at t=7 (re-creation)      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Tombstone Lifecycle

```
TOMBSTONE LIFECYCLE TIMELINE
════════════════════════════════════════════════════════════════════════════

│ Phase 1:     │ Phase 2:           │ Phase 3:        │ Phase 4:         │
│ WRITE        │ PROPAGATION        │ GRACE PERIOD    │ COMPACTION       │
│              │                    │                 │                  │
▼              ▼                    ▼                 ▼                  ▼
┌──┐     ┌──────────┐      ┌──────────────┐    ┌──────────────┐
│  │     │ Gossip / │      │  Wait for    │    │  Physically  │
│T │────▶│ Anti-    │─────▶│  gc_grace    │───▶│  Remove      │
│  │     │ Entropy  │      │  seconds     │    │  Tombstone   │
└──┘     └──────────┘      └──────────────┘    └──────────────┘
 │              │                    │                 │
 │              │                    │                 │
 t=0           t=0..hours          t=hours..days     t=gc_grace+
 │              │                    │                 │
 │              │                    │                 │
 ▼              ▼                    ▼                 ▼
Tombstone    All replicas       Ensures even      Disk space
written      should have        slow/offline      reclaimed.
locally.     received the       replicas got      Tombstone is
             tombstone by       the tombstone.    gone forever.
             now.

═══════════════════════════════════════════════════════════════════════════

DETAILED PHASE BREAKDOWN:

Phase 1 — WRITE (Immediate, local)
────────────────────────────────────
  • Client sends DELETE request
  • Coordinator writes tombstone to local commit log / memtable
  • Tombstone gets a timestamp (wall clock or logical)
  • Acknowledged to client (based on consistency level)

Phase 2 — PROPAGATION (Seconds to hours)
────────────────────────────────────
  • Replication factor determines initial writes (RF=3 → 3 nodes)
  • Gossip/anti-entropy spreads to remaining replicas
  • Hinted handoff delivers to temporarily-down nodes
  • Read-repair may also propagate tombstone on reads

Phase 3 — GRACE PERIOD (gc_grace_seconds)
────────────────────────────────────
  • Tombstone is kept even though it's "useless" locally
  • Purpose: safety buffer for offline/lagging replicas
  • Default: 10 days (864,000 seconds) in Cassandra
  • CRITICAL: All replicas MUST receive tombstone before this expires
  • Operations team must run repair within this window

Phase 4 — COMPACTION / GC (After grace period)
────────────────────────────────────
  • Compaction process identifies expired tombstones
  • Tombstone and underlying data physically removed from disk
  • Disk space is finally reclaimed
  • If a replica missed it → resurrection risk!
```

### State Machine

```
         ┌───────────────────────────────────────────┐
         │                                           │
         ▼                                           │
    ┌─────────┐     ┌────────────┐     ┌─────────┐  │
    │  ALIVE  │────▶│ TOMBSTONED │────▶│ PURGED  │  │
    │ (value) │     │  (marker)  │     │ (gone)  │  │
    └─────────┘     └────────────┘     └─────────┘  │
         ▲                                    │      │
         │          If replica missed         │      │
         │          tombstone before purge:   │      │
         │                                    │      │
         └────────────────────────────────────┘      │
              RESURRECTION!                          │
              (This is the bug)                      │
                                                     │
         New write (re-creation) ────────────────────┘
         (This is intentional)
```

---

## 5. Garbage Collection of Tombstones

### The Storage Problem

Tombstones consume storage. In a system with high delete throughput (e.g., TTL-heavy workloads), tombstones can accumulate to consume more space than live data.

### gc_grace_seconds

```
THE gc_grace_seconds WINDOW
═══════════════════════════════════════════════════════════════════════

                    gc_grace_seconds (default: 10 days)
              ◄─────────────────────────────────────────►
              │                                         │
──────────────┼─────────────────────────────────────────┼──────────────▶ time
              │                                         │
         Tombstone                                 Tombstone
         Written                                   Eligible for
                                                   Compaction/GC

SAFE SCENARIO: Node down for 3 days (within gc_grace)
═══════════════════════════════════════════════════════

Day 0          Day 3        Day 7                  Day 10
  │              │            │                      │
  ▼              ▼            ▼                      ▼
  ┌──┐      ┌────────┐   ┌────────┐            ┌────────┐
  │T │      │Node X  │   │Repair  │            │Compact │
  │  │      │comes   │   │runs    │            │removes │
  │  │      │back    │   │(safe!) │            │tombston│
  └──┘      └────────┘   └────────┘            └────────┘
  │              │            │                      │
  │              ▼            ▼                      │
  │         Receives      Confirmed:                 │
  │         tombstone     all replicas               │
  │         via anti-     have tombstone             ▼
  │         entropy                              Tombstone purged.
  │                                              Key truly gone.
  ▼
Tombstone
written


DANGEROUS SCENARIO: Node down longer than gc_grace
═══════════════════════════════════════════════════════

Day 0                                    Day 10         Day 15
  │                                        │              │
  ▼                                        ▼              ▼
  ┌──┐                                ┌────────┐    ┌─────────────┐
  │T │                                │Compact │    │  Node X     │
  │  │                                │removes │    │  comes back  │
  │  │                                │tombston│    │  with old K! │
  └──┘                                └────────┘    └─────────────┘
  │                                        │              │
  │    Node X is DOWN this entire time     │              │
  │◄──────────────────────────────────────►│              │
  │                                        │              ▼
  │                                        │         ┌──────────────┐
  │                                        │         │ RESURRECTION!│
  │                                        │         │ K reappears  │
  │                                        │         │ on cluster   │
  │                                        │         └──────────────┘
  │                                        │
  │                                   Tombstone is gone.
  │                                   No record that K
  │                                   was ever deleted.
  │
  ▼
Tombstone written.
Node X never received it.

  ╔═════════════════════════════════════════════════════════════════════╗
  ║  RULE: If a node is down longer than gc_grace_seconds,            ║
  ║        it MUST be rebuilt from scratch (bootstrap/replace).        ║
  ║        Do NOT just restart it — it will resurrect deleted data.    ║
  ╚═════════════════════════════════════════════════════════════════════╝
```

### Repair Requirements

```
REPAIR CADENCE vs gc_grace_seconds
═══════════════════════════════════

  gc_grace = 10 days

  Recommended repair interval = gc_grace / 2 = 5 days

  ├─────┤─────┤─────┤─────┤─────┤─────┤─────┤──▶ time (days)
  0     5    10    15    20    25    30    35

  R     R     R     R     R     R     R        ← Repair runs
        │     │
        │     └─ First tombstone eligible for GC
        │        (written at day 0, grace = 10 days)
        │
        └─ Repair ensures all replicas consistent
           BEFORE any tombstone is garbage collected

  KEY INVARIANT:
  ┌─────────────────────────────────────────────────────────────┐
  │  repair_interval < gc_grace_seconds                         │
  │                                                             │
  │  If repair_interval >= gc_grace_seconds, tombstones may be  │
  │  GC'd before all replicas have been repaired → resurrection │
  └─────────────────────────────────────────────────────────────┘
```

---

## 6. Tombstone Types

```
TOMBSTONE TYPE HIERARCHY
════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                     PARTITION TOMBSTONE                          │
│  Deletes entire partition (all rows under one partition key)     │
│  Scope: partition_key = X                                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                   RANGE TOMBSTONE                          │ │
│  │  Deletes a contiguous range of clustering keys             │ │
│  │  Scope: partition_key = X AND clustering >= A AND <= B     │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │              ROW TOMBSTONE                            │ │ │
│  │  │  Deletes one entire row (all columns)                │ │ │
│  │  │  Scope: partition_key = X AND clustering_key = Y     │ │ │
│  │  ├──────────────────────────────────────────────────────┤ │ │
│  │  │  ┌────────────────────────────────────────────────┐ │ │ │
│  │  │  │         CELL/COLUMN TOMBSTONE                  │ │ │ │
│  │  │  │  Deletes a single column value                 │ │ │ │
│  │  │  │  Scope: (partition, clustering, column_name)   │ │ │ │
│  │  │  └────────────────────────────────────────────────┘ │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 6.1 Cell/Column Tombstone

```
Before:
┌────────┬─────────┬──────────┬───────────┐
│  PK    │  name   │  email   │  phone    │
├────────┼─────────┼──────────┼───────────┤
│  U001  │  Alice  │ a@b.com  │ 555-1234  │
└────────┴─────────┴──────────┴───────────┘

After DELETE phone WHERE PK = U001:
┌────────┬─────────┬──────────┬───────────────┐
│  PK    │  name   │  email   │  phone        │
├────────┼─────────┼──────────┼───────────────┤
│  U001  │  Alice  │ a@b.com  │ ⚰️ (t=5)      │
└────────┴─────────┴──────────┴───────────────┘
```

### 6.2 Row Tombstone

```
After DELETE FROM users WHERE PK = U001:
┌────────┬─────────────────────────────────────┐
│  PK    │  ALL COLUMNS                        │
├────────┼─────────────────────────────────────┤
│  U001  │  ⚰️ ROW TOMBSTONE (t=5)             │
└────────┴─────────────────────────────────────┘
```

### 6.3 Range Tombstone

Efficiently deletes a range without individual row tombstones:

```
DELETE FROM events WHERE user_id = 'U001' AND event_time < '2024-01-01'

Stored as:
┌──────────────────────────────────────────────────────┐
│  Range Tombstone                                     │
│  partition:  user_id = 'U001'                        │
│  start:      (min clustering value)                  │
│  end:        event_time = '2024-01-01'               │
│  timestamp:  t=5                                     │
│                                                      │
│  Covers ALL rows in this range without               │
│  enumerating them individually.                      │
└──────────────────────────────────────────────────────┘

Storage visualization:
┌───────────────────────────────────────────────────────────────┐
│  Partition: user_id = 'U001'                                  │
│                                                               │
│  ════════════════════════╗                                    │
│  ║  RANGE TOMBSTONE     ║                                    │
│  ║  (covers this range) ║                                    │
│  ════════════════════════╝                                    │
│  │                      │                                    │
│  event_time:            event_time:        event_time:        │
│  2023-01-01             2024-01-01         2024-06-15         │
│  [deleted]              [boundary]         [alive]            │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### 6.4 Partition Tombstone

```
DELETE FROM events WHERE user_id = 'U001'
-- Deletes ALL data under this partition key

Single tombstone record covers potentially millions of rows.
Very efficient for bulk deletion by partition key.
```

### 6.5 TTL-based Tombstone

```
INSERT INTO sessions (id, token) VALUES ('S1', 'abc') USING TTL 3600;

Timeline:
────────────────────────────────────────────────────────────────▶
│                      │                              │
t=0                  t=3600                        t=3600+gc_grace
│                      │                              │
Write with             TTL expires →                  Tombstone
TTL=3600s              Automatic tombstone            GC'd
                       created by system

Note: TTL expiry creates tombstones implicitly!
      High-TTL workloads = high tombstone generation rate
```

---

## 7. Performance Impact

### Read Path with Tombstones

```
READ REQUEST FOR KEY K
══════════════════════

Without tombstones (ideal):
┌──────────┐    ┌──────────┐    ┌──────────┐
│ SSTable1 │    │ SSTable2 │    │ SSTable3 │
│          │    │          │    │          │
│  K = V3  │    │  K = V2  │    │  K = V1  │
│  (t=30)  │    │  (t=20)  │    │  (t=10)  │
└──────────┘    └──────────┘    └──────────┘
      │
      └──▶ Return V3 (newest). Done quickly.


With tombstone accumulation (pathological):
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ SSTable1 │ │ SSTable2 │ │ SSTable3 │ │ SSTable4 │ │ SSTable5 │
│          │ │          │ │          │ │          │ │          │
│  K = ⚰️  │ │  K = ⚰️  │ │  K = ⚰️  │ │  K = ⚰️  │ │  K = V1  │
│  (t=50)  │ │  (t=40)  │ │  (t=30)  │ │  (t=20)  │ │  (t=10)  │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
      │            │            │            │            │
      └────────────┴────────────┴────────────┴────────────┘
                              │
                     Must scan ALL of these
                     to determine K is deleted.
                     Wasted I/O!

Range scan with many tombstones:
┌──────────────────────────────────────────────────────────────────┐
│  SELECT * FROM events WHERE user_id = 'U001' LIMIT 10           │
│                                                                  │
│  Scanning: ⚰️ ⚰️ ⚰️ ⚰️ ⚰️ ⚰️ ⚰️ ⚰️ ⚰️ ⚰️ ⚰️ ⚰️ ⚰️ ⚰️ V V V ⚰️ ⚰️ V ⚰️ ⚰️ V... │
│                                                                  │
│  To find 10 live rows, system may scan 100,000+ tombstones!     │
│  This causes timeouts and OOM errors.                           │
└──────────────────────────────────────────────────────────────────┘
```

### Tombstone Storm

```
TOMBSTONE STORM SCENARIO
═════════════════════════

Workload: 10M records inserted with TTL = 24h

Hour 0────────────────────────Hour 24───────────────────Hour 25
    │                             │                        │
    ▼                             ▼                        ▼
 10M inserts                  10M TTL expirations      Read timeouts!
 (spread over                 create 10M tombstones    tombstone_failure_
  24 hours)                   in a SHORT window        threshold exceeded

                              ┌─────────────────────┐
                              │  TOMBSTONE STORM!    │
                              │                     │
                              │  • Reads slow to    │
                              │    halt              │
                              │  • Compaction can't  │
                              │    keep up           │
                              │  • GC pressure       │
                              │  • Heap exhaustion   │
                              └─────────────────────┘
```

### Cassandra's Tombstone Thresholds

```
┌─────────────────────────────────────────────────────────────────┐
│  CASSANDRA TOMBSTONE SAFETY THRESHOLDS                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  tombstone_warn_threshold:     1000 (default)                   │
│    → Logs WARNING when read encounters >1000 tombstones         │
│                                                                 │
│  tombstone_failure_threshold:  100000 (default)                 │
│    → ABORTS read with TombstoneOverwhelmingException             │
│    → Prevents OOM from materializing millions of tombstones     │
│                                                                 │
│  Monitoring query:                                              │
│    nodetool tablestats <keyspace>.<table>                       │
│    → "Average tombstones per slice (last five minutes)"         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Performance Mitigation Strategies

| Strategy | Description | Trade-off |
|----------|-------------|-----------|
| Reduce gc_grace_seconds | Tombstones GC'd faster | Higher resurrection risk |
| Increase compaction frequency | Purge tombstones sooner | More I/O during compaction |
| Use TWCS (Time-Window Compaction) | Entire SSTables drop when all data expired | Only works for time-series |
| Avoid wide partitions with deletes | Fewer tombstones per read | May require schema redesign |
| Use TTL wisely | Avoid synchronized expiry | Stagger TTLs if possible |

---

## 8. Soft Delete Pattern (Application Level)

### Concept

Soft delete is an **application-level** pattern where records are marked as deleted but remain physically present in the database.

```
HARD DELETE vs SOFT DELETE vs TOMBSTONE
═══════════════════════════════════════

┌─────────────────┬────────────────────────┬─────────────────────────┐
│   HARD DELETE   │     SOFT DELETE         │   DISTRIBUTED TOMBSTONE │
├─────────────────┼────────────────────────┼─────────────────────────┤
│ Physical removal│ Application flag       │ System-level marker     │
│ Row gone        │ Row present, filtered  │ Marker for replication  │
│ Immediate       │ Reversible             │ Temporary (GC'd later)  │
│ Simple          │ Query overhead         │ Consistency guarantee   │
│ No undo         │ Undelete possible      │ Prevents resurrection   │
│                 │                        │                         │
│ DELETE FROM t   │ UPDATE t SET           │ Internal system writes  │
│ WHERE id=1     │ deleted_at=NOW()       │ {key, DELETE, timestamp} │
│                 │ WHERE id=1            │                         │
└─────────────────┴────────────────────────┴─────────────────────────┘
```

### Implementation

```sql
-- Schema
CREATE TABLE users (
    id          UUID PRIMARY KEY,
    name        TEXT,
    email       TEXT,
    created_at  TIMESTAMP,
    deleted_at  TIMESTAMP NULL,  -- NULL means active
    deleted_by  UUID NULL
);

-- "Delete" a user
UPDATE users SET deleted_at = NOW(), deleted_by = :actor_id WHERE id = :user_id;

-- Query active users (application MUST include this filter everywhere)
SELECT * FROM users WHERE deleted_at IS NULL;

-- Undelete
UPDATE users SET deleted_at = NULL, deleted_by = NULL WHERE id = :user_id;

-- Hard delete (periodic archival job)
-- Run weekly/monthly to actually remove old soft-deleted records
DELETE FROM users WHERE deleted_at < NOW() - INTERVAL '90 days';
```

### Soft Delete Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                             │
│                                                                 │
│  ┌─────────────┐   ┌──────────────────┐   ┌────────────────┐  │
│  │   API       │   │  Query Middleware │   │  Archival Job  │  │
│  │   Layer     │──▶│  (auto-filter     │   │  (periodic     │  │
│  │             │   │   deleted_at)     │   │   hard-delete) │  │
│  └─────────────┘   └──────────────────┘   └────────────────┘  │
│        │                    │                       │           │
│        │ DELETE /users/123  │ SELECT * FROM users   │ DELETE    │
│        │                    │ WHERE deleted_at      │ WHERE     │
│        ▼                    │ IS NULL               │ deleted_at│
│  ┌─────────────┐           │                       │ < 90d ago │
│  │ UPDATE SET  │           │                       │           │
│  │ deleted_at  │           │                       │           │
│  │ = NOW()     │           │                       │           │
│  └─────────────┘           │                       │           │
│                             ▼                       ▼           │
├─────────────────────────────────────────────────────────────────┤
│                    DATABASE LAYER                                │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  id   │ name  │ email     │ deleted_at         │ ...     │  │
│  ├───────┼───────┼───────────┼────────────────────┼─────────┤  │
│  │  U1   │ Alice │ a@b.com   │ NULL               │         │  │ ← Active
│  │  U2   │ Bob   │ b@c.com   │ 2024-03-15 10:00   │         │  │ ← Soft deleted
│  │  U3   │ Carol │ c@d.com   │ NULL               │         │  │ ← Active
│  └───────┴───────┴───────────┴────────────────────┴─────────┘  │
│                                                                 │
│  Index: CREATE INDEX idx_active ON users(id) WHERE              │
│         deleted_at IS NULL;  -- Partial index for performance   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Soft Delete Pitfalls

| Issue | Description |
|-------|-------------|
| Unique constraints | `email` must be unique — but deleted users still hold the email. Use partial unique index: `UNIQUE(email) WHERE deleted_at IS NULL` |
| Query leaks | Every query must filter `deleted_at IS NULL`. One missed filter = data leak. Use views or ORM scopes. |
| Storage growth | Table grows unbounded if archival job doesn't run |
| Foreign keys | Child records pointing to soft-deleted parents need careful handling |
| GDPR/compliance | Soft delete may NOT satisfy "right to erasure" — actual deletion required |

---

## 9. Real-World Implementations

### 9.1 Apache Cassandra

```
┌─────────────────────────────────────────────────────────────────┐
│  CASSANDRA TOMBSTONE IMPLEMENTATION                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Configuration (per-table):                                     │
│    gc_grace_seconds: 864000 (10 days)                           │
│    tombstone_warn_threshold: 1000                               │
│    tombstone_failure_threshold: 100000                          │
│                                                                 │
│  Tombstone types: cell, row, range, partition                   │
│                                                                 │
│  Compaction strategies:                                         │
│    STCS: Tombstones purged during size-tiered compaction        │
│    LCS:  More predictable tombstone cleanup                     │
│    TWCS: Entire SSTables dropped when window expires            │
│                                                                 │
│  Key command: nodetool repair (must run < gc_grace_seconds)     │
│                                                                 │
│  SSTable format stores tombstone as:                            │
│    local_deletion_time (int32) + marked_for_delete_at (int64)   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2 Amazon DynamoDB

```
┌─────────────────────────────────────────────────────────────────┐
│  DYNAMODB TTL & DELETION                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  • No explicit tombstone concept exposed to users               │
│  • TTL: Set expiration_time attribute (epoch seconds)           │
│  • Items deleted within 48 hours after TTL expiry               │
│  • Internally uses tombstones for cross-region replication      │
│  • Global Tables: deletion replicated as a delete marker        │
│  • Streams: TTL deletions appear as DELETE events               │
│                                                                 │
│  DynamoDB handles GC internally — no gc_grace to configure      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 9.3 Apache Kafka (Log Compaction)

```
KAFKA TOMBSTONE (NULL-VALUE MESSAGE)
════════════════════════════════════

Topic: user-events (compacted)

Before compaction:
┌─────┬───────┬─────────────────────────────────────────────┐
│ Off │ Key   │ Value                                       │
├─────┼───────┼─────────────────────────────────────────────┤
│  0  │ U001  │ {"name": "Alice", "email": "a@old.com"}    │
│  1  │ U002  │ {"name": "Bob", "email": "b@b.com"}        │
│  2  │ U001  │ {"name": "Alice", "email": "a@new.com"}    │
│  3  │ U001  │ null  ← TOMBSTONE                          │
│  4  │ U003  │ {"name": "Carol"}                          │
└─────┴───────┴─────────────────────────────────────────────┘

After compaction (with delete.retention.ms elapsed):
┌─────┬───────┬─────────────────────────────────────────────┐
│ Off │ Key   │ Value                                       │
├─────┼───────┼─────────────────────────────────────────────┤
│  1  │ U002  │ {"name": "Bob", "email": "b@b.com"}        │
│  4  │ U003  │ {"name": "Carol"}                          │
└─────┴───────┴─────────────────────────────────────────────┘

U001 completely removed (tombstone + all prior values).

Config:
  delete.retention.ms = 86400000 (24h, analogous to gc_grace)
  min.compaction.lag.ms = time before tombstone eligible for compaction
```

### 9.4 CouchDB

```
┌─────────────────────────────────────────────────────────────────┐
│  COUCHDB DELETION DOCUMENTS                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Deletion = new revision with {_deleted: true}                  │
│                                                                 │
│  Before: {"_id": "doc1", "_rev": "2-abc", "name": "Alice"}     │
│  After:  {"_id": "doc1", "_rev": "3-def", "_deleted": true}    │
│                                                                 │
│  • Deletion is just another document revision                   │
│  • Replicates like any other change                             │
│  • Compaction removes old revisions but keeps deletion stub     │
│  • _purge API for true physical removal (breaks replication)    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 9.5 HBase

```
┌─────────────────────────────────────────────────────────────────┐
│  HBASE DELETE MARKERS                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Types:                                                         │
│    Delete        — marks specific version of a cell             │
│    DeleteColumn  — marks all versions of a column               │
│    DeleteFamily  — marks all columns in a column family         │
│                                                                 │
│  Lifecycle:                                                     │
│    1. Delete marker written to MemStore                         │
│    2. Flushed to StoreFile (HFile)                              │
│    3. Major compaction: markers + masked data removed           │
│                                                                 │
│  Note: Minor compaction does NOT remove delete markers          │
│        Only major compaction physically reclaims space           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 9.6 Riak

```
┌─────────────────────────────────────────────────────────────────┐
│  RIAK TOMBSTONES                                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  delete_mode options:                                           │
│    • timeout (default 3s) — tombstone kept for N ms             │
│    • immediate — tombstone reaped immediately (dangerous!)      │
│    • keep — tombstone kept forever (safe but wastes space)      │
│                                                                 │
│  Problem: Riak's short default timeout → frequent resurrections │
│  Solution: Use 'keep' mode + periodic reap process              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 9.7 Git

```
┌─────────────────────────────────────────────────────────────────┐
│  GIT "DELETION"                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  • File deletion = new commit with file removed from tree       │
│  • Previous commits still reference the file (immutable DAG)    │
│  • Data never truly deleted from history (by design)            │
│  • git filter-branch / BFG for true history rewriting           │
│  • Distributed: all clones retain full history including        │
│    deleted files until GC + repack                              │
│                                                                 │
│  Conceptually similar: deletion is recorded as a positive       │
│  event (commit) rather than absence                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. CRDT Delete Problem

### The Challenge

CRDTs (Conflict-free Replicated Data Types) achieve convergence without coordination. But deletion is problematic because:
- Add operations can be represented by inserting elements
- Remove operations create the same "absence vs. not-yet-seen" ambiguity

### Observed-Remove Set (OR-Set)

```
OR-SET: SAFE DELETION IN CRDTs
═══════════════════════════════

Key idea: Tag each addition with a unique identifier.
          Remove operation specifies WHICH additions to remove.

Node A adds "apple":
  State_A = {("apple", tag_1)}

Node B adds "apple" concurrently:
  State_B = {("apple", tag_2)}

After merge:
  State = {("apple", tag_1), ("apple", tag_2)}

Node A removes "apple" (removes tag_1 specifically):
  State_A = {("apple", tag_2)}  ← tag_2 survives!

Final merged state:
  State = {("apple", tag_2)}  ← "apple" still present (B's add not removed)


┌────────────────────────────────────────────────────────────────┐
│                                                                │
│  Node A               Network              Node B             │
│  ──────               ───────              ──────             │
│                                                                │
│  add("x") → tag_a1                        add("x") → tag_b1  │
│  {(x,a1)}            ──merge──▶           {(x,b1)}           │
│                       ◀──merge──                              │
│  {(x,a1),(x,b1)}                          {(x,a1),(x,b1)}   │
│                                                                │
│  remove("x")                                                   │
│  = remove tags {a1, b1}                                        │
│  that I can currently see                                      │
│                                                                │
│  {}                   ──merge──▶           {}                  │
│                                                                │
│  SAFE: Both tags removed, both nodes agree x is gone.          │
│                                                                │
│  BUT: If B concurrently adds("x") → tag_b2 AFTER A's remove:  │
│  A sees {} + {(x,b2)} = {(x,b2)}  ← "x" is back (intended!)  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Tombstone GC in CRDTs: Causal Stability

```
CAUSAL STABILITY FOR TOMBSTONE GC
══════════════════════════════════

A tombstone is causally stable when ALL nodes have observed it
(and therefore no node can generate a concurrent operation that
would conflict with it).

  Node A         Node B         Node C
    │              │              │
    │ remove(x)    │              │
    │──────────────▶              │
    │              │──────────────▶
    │              │              │
    │◀─────ack─────│              │   Not yet stable
    │              │◀─────ack─────│   (need all acks)
    │◀────────────────────ack─────│
    │              │              │
    ▼              ▼              ▼
  Tombstone is now CAUSALLY STABLE
  → Can be garbage collected safely
  → No concurrent add can conflict

  Challenge: Determining causal stability requires knowing
  the state of ALL replicas → similar to gc_grace_seconds
  but with formal guarantees.
```

### CRDT Approaches to Deletion

| Approach | Mechanism | Trade-off |
|----------|-----------|-----------|
| OR-Set | Unique tags per add, remove specifies tags | Metadata grows with adds |
| Observed-Remove | Track causal context of removes | Complex vector clock management |
| Add-Wins Set | Concurrent add + remove → add wins | Cannot reliably delete |
| Remove-Wins Set | Concurrent add + remove → remove wins | Can lose concurrent adds |
| Delta-state with tombstones | Propagate deltas, GC stable tombstones | Requires stability detection |

---

## 11. Best Practices and Anti-Patterns

### Best Practices

```
┌─────────────────────────────────────────────────────────────────┐
│  ✓  BEST PRACTICES                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. DESIGN FOR DELETION FROM DAY ONE                            │
│     • Choose data models that minimize delete operations        │
│     • Time-series: use TTL + TWCS, not explicit deletes         │
│     • Queue-like patterns: use dedicated queue, not DB deletes  │
│                                                                 │
│  2. RUN REPAIR WITHIN gc_grace_seconds                          │
│     • Automate with cron/scheduler                              │
│     • Alert if repair hasn't run in gc_grace/2                  │
│     • After any extended outage, repair before resuming traffic │
│                                                                 │
│  3. MONITOR TOMBSTONE METRICS                                   │
│     • Track tombstones-per-read (warn > 1000)                   │
│     • Monitor SSTable tombstone ratio                           │
│     • Alert on tombstone_warn_threshold breaches                │
│                                                                 │
│  4. USE APPROPRIATE COMPACTION STRATEGY                         │
│     • TWCS for time-series with TTL                             │
│     • LCS for read-heavy with occasional deletes               │
│     • STCS generally worst for tombstone-heavy workloads        │
│                                                                 │
│  5. PREFER OVERWRITES TO DELETES                                │
│     • Instead of delete + re-insert, update in place            │
│     • Use status fields instead of physical deletion            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Anti-Patterns

```
┌─────────────────────────────────────────────────────────────────┐
│  ✗  ANTI-PATTERNS                                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. QUEUE-ON-TOP-OF-CASSANDRA                                   │
│     Pattern: INSERT → process → DELETE → repeat                 │
│     Problem: Creates tombstone for every processed message      │
│     Fix: Use Kafka/SQS for queues, not Cassandra                │
│                                                                 │
│  2. SYNCHRONIZED TTL EXPIRY                                     │
│     Pattern: All records expire at midnight (same TTL start)    │
│     Problem: Millions of tombstones created simultaneously      │
│     Fix: Add random jitter to TTL values                        │
│                                                                 │
│  3. DELETING FROM WIDE PARTITIONS                               │
│     Pattern: 1M rows per partition, delete 999K of them         │
│     Problem: Reads scan 999K tombstones to find 1K live rows    │
│     Fix: Redesign schema, use bucketing, or use range deletes   │
│                                                                 │
│  4. REDUCING gc_grace_seconds WITHOUT REPAIR                    │
│     Pattern: Set gc_grace=1h to reduce tombstone buildup        │
│     Problem: Any node down >1h → resurrection                   │
│     Fix: Only reduce gc_grace if repair runs more frequently    │
│                                                                 │
│  5. NEVER RUNNING MAJOR COMPACTION (HBase)                      │
│     Pattern: Only minor compactions run                         │
│     Problem: Delete markers accumulate forever                  │
│     Fix: Schedule periodic major compactions during low traffic │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 12. Architect's Guide: Designing Delete Operations

### Decision Framework

```
DELETION STRATEGY DECISION TREE
════════════════════════════════

                    ┌──────────────────────┐
                    │  Need to delete data │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │ Is this a distributed │
              No    │ system with replicas? │    Yes
           ┌────────┤                      ├────────┐
           │        └──────────────────────┘        │
           ▼                                        ▼
   ┌───────────────┐                    ┌───────────────────┐
   │ Simple DELETE  │                    │ Must use tombstone │
   │ is fine       │                    │ or equivalent      │
   └───────────────┘                    └─────────┬─────────┘
                                                  │
                                       ┌──────────▼──────────┐
                                       │ What's the workload?│
                                       └──────────┬──────────┘
                                                  │
                    ┌─────────────┬───────────────┼──────────────┐
                    ▼             ▼               ▼              ▼
            ┌────────────┐ ┌──────────┐  ┌────────────┐  ┌──────────┐
            │ Time-series│ │ Explicit │  │ Infrequent │  │ Need     │
            │ data with  │ │ user     │  │ admin      │  │ undo/    │
            │ natural    │ │ deletes  │  │ deletes    │  │ audit    │
            │ expiry     │ │ (social  │  │            │  │ trail    │
            │            │ │ media)   │  │            │  │          │
            └─────┬──────┘ └────┬─────┘  └─────┬──────┘  └────┬─────┘
                  │             │              │              │
                  ▼             ▼              ▼              ▼
            ┌──────────┐ ┌──────────┐  ┌────────────┐  ┌──────────┐
            │ USE TTL  │ │ Tombstone│  │ Standard   │  │ SOFT     │
            │ + TWCS   │ │ + careful│  │ tombstone  │  │ DELETE   │
            │          │ │ schema   │  │ (defaults  │  │ pattern  │
            │ No manual│ │ design   │  │ are fine)  │  │          │
            │ deletes  │ │          │  │            │  │ +periodic│
            │ needed   │ │ Minimize │  │            │  │ hard-del │
            └──────────┘ │ wide-row │  └────────────┘  └──────────┘
                         │ deletes  │
                         └──────────┘
```

### System Design Checklist

```
┌─────────────────────────────────────────────────────────────────┐
│  ARCHITECT'S DELETION CHECKLIST                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  □ What is the expected delete-to-write ratio?                  │
│    • < 1%: Standard tombstones, default gc_grace                │
│    • 1-10%: Monitor tombstone accumulation, tune compaction     │
│    • > 10%: Redesign data model (consider append-only)          │
│                                                                 │
│  □ What is the maximum tolerable replica downtime?              │
│    • This determines your gc_grace_seconds                      │
│    • gc_grace must be > max expected downtime                   │
│    • Shorter gc_grace = faster cleanup but higher risk          │
│                                                                 │
│  □ Is "undelete" required?                                      │
│    • Yes → Soft delete at application layer                     │
│    • No → System tombstones sufficient                          │
│                                                                 │
│  □ Are there compliance requirements (GDPR, HIPAA)?             │
│    • "Right to erasure" may require physical deletion           │
│    • Tombstones technically still reference the key             │
│    • May need crypto-shredding (delete encryption key)          │
│                                                                 │
│  □ What is the read pattern after deletion?                     │
│    • Range scans over deleted ranges → range tombstones         │
│    • Point reads of deleted keys → minimal impact               │
│    • Full table scans → tombstone ratio critical                │
│                                                                 │
│  □ Is there a natural time-based access pattern?                │
│    • Yes → TTL + time-window compaction (best option)           │
│    • No → Explicit deletes with repair discipline               │
│                                                                 │
│  □ What happens if data resurrects?                             │
│    • Annoyance (social media: deleted post reappears)           │
│    • Compliance violation (GDPR: deleted data returns)          │
│    • Correctness bug (financial: reversed transaction returns)  │
│    • Severity determines how conservative gc_grace must be      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Compaction and Tombstone Cleanup

```
COMPACTION CLEANING TOMBSTONES (SSTable-based systems)
══════════════════════════════════════════════════════

Before Compaction:
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  SSTable-1 (oldest)        SSTable-2          SSTable-3 (newest)│
│  ┌───────────────────┐    ┌──────────────┐   ┌──────────────┐  │
│  │ K1 = "hello" t=1  │    │ K1 = ⚰️  t=5 │   │ K3 = "x" t=8 │  │
│  │ K2 = "world" t=2  │    │ K2 = "!" t=6 │   │ K4 = ⚰️  t=9 │  │
│  │ K3 = "foo"   t=3  │    │ K4 = "y" t=7 │   │              │  │
│  └───────────────────┘    └──────────────┘   └──────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Compaction merges SSTables, applying tombstones:

Step 1: Merge all entries for each key, keep newest
Step 2: If tombstone age > gc_grace_seconds, drop key entirely
Step 3: If tombstone age < gc_grace_seconds, keep tombstone

After Compaction (assuming K1 tombstone past gc_grace, K4 not):
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  SSTable-new (merged)                                           │
│  ┌──────────────────────────┐                                   │
│  │ K2 = "!"     t=6         │  ← K2 latest value kept          │
│  │ K3 = "x"     t=8         │  ← K3 latest value kept          │
│  │ K4 = ⚰️       t=9         │  ← Tombstone retained (too new)  │
│  └──────────────────────────┘                                   │
│                                                                 │
│  K1: GONE (tombstone + data purged, gc_grace elapsed)           │
│  K4: Tombstone kept (gc_grace not yet elapsed)                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

  IMPORTANT: Compaction can only drop a tombstone if:
    1. Tombstone age > gc_grace_seconds
    2. ALL SSTables containing data for that key are included
       in this compaction (otherwise older data could survive)
```

---

## Summary

| Concept | Purpose | Key Insight |
|---------|---------|-------------|
| Tombstone | Prevent resurrection | Absence cannot represent deletion |
| gc_grace_seconds | Safety window for propagation | Must exceed max replica downtime |
| Repair | Ensure all replicas consistent | Must run within gc_grace window |
| Soft delete | Application-level reversible deletion | Orthogonal to distributed tombstones |
| Range tombstone | Efficient bulk deletion | Single marker covers key range |
| TTL tombstone | Automatic expiry-based deletion | Can cause tombstone storms |
| CRDT deletion | Conflict-free distributed deletion | Requires unique tags (OR-Set) |

> **The fundamental lesson**: In distributed systems, you cannot destroy information to represent destruction of information. You must create information (a tombstone) that represents the intent to destroy.
