# Sloppy Quorum

## 1. Problem Statement

Strict quorum requires that writes succeed on a majority (or configured subset) of **designated replicas** for a given key. During network partitions or node failures, if too many designated replicas are unreachable, the system **rejects writes entirely** — even though other healthy nodes exist in the cluster that could temporarily accept data.

This creates an availability gap: the system has capacity and healthy nodes, but the rigid assignment of replicas to specific nodes causes unnecessary write failures.

**Core Question**: Can we redirect writes to non-designated but healthy nodes during failures, and reconcile later?

---

## 2. Strict Quorum Recap

For a key K with replication factor N=3:
- Designated replica set: {N1, N2, N3}
- Write quorum W=2: must successfully write to at least 2 of {N1, N2, N3}
- Read quorum R=2: must successfully read from at least 2 of {N1, N2, N3}
- Guarantee: R + W > N ensures overlap → at least one node has latest write

### Failure Scenario

If 2 of the 3 designated nodes are down, W=2 cannot be satisfied → **write is rejected**.

```
                    STRICT QUORUM: WRITE REJECTED
                    ═════════════════════════════

    Client writes Key K (W=2 required from {N1, N2, N3})

         Client
           │
           ▼
    ┌─────────────┐
    │ Coordinator │
    └─────────────┘
       │     │     │
       ▼     ▼     ▼
    ┌────┐ ┌────┐ ┌────┐
    │ N1 │ │ N2 │ │ N3 │    ← Designated replicas for K
    │ ✓  │ │ ✗  │ │ ✗  │
    └────┘ └────┘ └────┘
     alive   DOWN   DOWN

    ┌────┐ ┌────┐ ┌────┐
    │ N4 │ │ N5 │ │ N6 │    ← Other healthy nodes (NOT used)
    │idle│ │idle│ │idle│
    └────┘ └────┘ └────┘

    Result: W=2 NOT satisfied (only 1 of 3 designated nodes alive)
            ╔═══════════════════════════╗
            ║  WRITE REJECTED (503)     ║
            ║  Despite 4 healthy nodes! ║
            ╚═══════════════════════════╝
```

This is the fundamental limitation: strict quorum couples availability to the health of **specific** nodes rather than overall cluster health.

---

## 3. Sloppy Quorum Definition

A **sloppy quorum** relaxes the constraint: writes can succeed on **any W healthy nodes** in the cluster, not just the designated replicas.

**Key Properties**:
1. The system still prefers designated replicas when available
2. When designated replicas are unreachable, writes spill over to non-designated healthy nodes
3. Non-designated nodes act as **temporary custodians** — they hold data on behalf of the intended replica
4. A mechanism called **hinted handoff** ensures data eventually migrates to the correct designated node

### Sloppy Quorum Accepting Writes During Failure

```
                  SLOPPY QUORUM: WRITE ACCEPTED
                  ═════════════════════════════

    Client writes Key K (W=2, sloppy quorum)

         Client
           │
           ▼
    ┌─────────────┐
    │ Coordinator │
    └─────────────┘
       │     │     │          │
       ▼     ▼     ▼          ▼
    ┌────┐ ┌────┐ ┌────┐   ┌────┐
    │ N1 │ │ N2 │ │ N3 │   │ N4 │   ← N4 is temporary holder
    │ ✓  │ │ ✗  │ │ ✗  │   │ ✓  │
    └────┘ └────┘ └────┘   └────┘
     alive   DOWN   DOWN    alive
                            (holds hint
                             for N2)

    Result: W=2 satisfied (N1 + N4)
            ╔═══════════════════════════╗
            ║  WRITE ACCEPTED (200)     ║
            ║  Data safe on 2 nodes     ║
            ╚═══════════════════════════╝

    N4's hint record:
    ┌─────────────────────────────────┐
    │ Key: K                          │
    │ Value: <data>                   │
    │ Intended for: N2                │
    │ Timestamp: 2024-01-15T10:30:00Z │
    └─────────────────────────────────┘
```

### Comparison Table

| Property              | Strict Quorum        | Sloppy Quorum              |
|-----------------------|----------------------|----------------------------|
| Write target          | Designated replicas  | Any healthy node           |
| Availability          | Limited by replicas  | Limited by cluster health  |
| Consistency guarantee | R+W>N → overlap      | No overlap guarantee       |
| Failure tolerance     | Can tolerate N-W     | Can tolerate up to N-1     |
| Complexity            | Simple               | Requires hinted handoff    |

---

## 4. How It Works with Consistent Hashing

In systems like Dynamo, keys are mapped to a hash ring. The designated replicas for a key are the next N distinct nodes clockwise from the key's hash position.

### Normal Operation

```
            CONSISTENT HASH RING — NORMAL OPERATION
            ════════════════════════════════════════

                         N1
                        ╱    ╲
                   N6 ╱        ╲ N2
                    │    Hash     │
                    │    Ring     │
                   N5 ╲        ╱ N3
                        ╲    ╱
                         N4

    Key K hashes to position between N6 and N1.
    Designated replicas (N=3): walk clockwise → N1, N2, N3

    Preference List for K: [N1, N2, N3, N4, N5, N6]
                            ├─────────┤  ├────────┤
                            designated    fallback candidates
```

### During Failure — Sloppy Quorum on the Ring

```
        CONSISTENT HASH RING — N2 AND N3 DOWN
        ═══════════════════════════════════════

                         N1 ✓
                        ╱    ╲
                   N6 ╱        ╲ N2 ✗ (DOWN)
                    │    Hash     │
                    │    Ring     │
                   N5 ╲        ╱ N3 ✗ (DOWN)
                        ╲    ╱
                         N4 ✓

    Key K hashes to position between N6 and N1.
    Walk clockwise for replicas:
      1. N1 → alive → WRITE ✓
      2. N2 → DOWN  → skip
      3. N3 → DOWN  → skip
      4. N4 → alive → WRITE ✓ (temporary holder, hint for N2)
      5. N5 → (would be used if W=3)

    ┌──────────────────────────────────────────────┐
    │  Write path: K → N1 (designated, permanent)  │
    │              K → N4 (temporary, hint → N2)   │
    │                                              │
    │  W=2 satisfied. Write succeeds.              │
    └──────────────────────────────────────────────┘
```

### The Hint Data Structure

Each hint stored on a temporary node contains:

```
┌─────────────────────────────────────────────────────────┐
│                    HINT RECORD                           │
├─────────────────────────────────────────────────────────┤
│ target_node:    N2                                       │
│ partition_key:  K                                        │
│ value:          <serialized data>                        │
│ vector_clock:   {N1: 3, N4: 1}                          │
│ timestamp:      1705312200                               │
│ ttl:            3600 (expire hint if not delivered)      │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Why R + W > N No Longer Guarantees Consistency

In strict quorum, R + W > N guarantees that reads and writes overlap on at least one node, ensuring the latest write is always visible. Sloppy quorum **breaks this invariant**.

### The Inconsistency Window

```
    WHY R + W > N FAILS WITH SLOPPY QUORUM
    ═══════════════════════════════════════

    Setup: N=3, W=2, R=2, Designated replicas = {N1, N2, N3}

    ─── Timeline ──────────────────────────────────────────────────

    T1: N2 and N3 go DOWN
        ┌────┐ ┌────┐ ┌────┐ ┌────┐
        │ N1 │ │ N2 │ │ N3 │ │ N4 │
        │ UP │ │DOWN│ │DOWN│ │ UP │
        └────┘ └────┘ └────┘ └────┘

    T2: Client A writes K=42 (sloppy quorum, W=2)
        Write goes to: N1 ✓, N4 ✓ (hint for N2)
        ┌────┐ ┌────┐ ┌────┐ ┌────┐
        │ N1 │ │ N2 │ │ N3 │ │ N4 │
        │K=42│ │DOWN│ │DOWN│ │K=42│  ← hint
        └────┘ └────┘ └────┘ └────┘

    T3: Network heals. N2 and N3 come back UP.
        (Hinted handoff has NOT yet run)
        ┌────┐ ┌────┐ ┌────┐ ┌────┐
        │ N1 │ │ N2 │ │ N3 │ │ N4 │
        │K=42│ │K=? │ │K=? │ │K=42│  ← hint still here
        └────┘ └────┘ └────┘ └────┘
                stale   stale

    T4: Client B reads K (strict read, R=2 from designated {N1,N2,N3})
        Reads from: N2 (stale/empty) and N3 (stale/empty)
        ┌────┐ ┌────┐ ┌────┐ ┌────┐
        │ N1 │ │ N2 │ │ N3 │ │ N4 │
        │    │ │READ│ │READ│ │    │
        └────┘ └────┘ └────┘ └────┘

        ╔══════════════════════════════════════════════╗
        ║  Client B reads STALE data!                  ║
        ║  The write K=42 exists only on N1 and N4.    ║
        ║  R=2 read hit N2+N3 → missed the write.     ║
        ║                                              ║
        ║  R+W=4 > N=3, yet consistency is violated!   ║
        ╚══════════════════════════════════════════════╝

    T5: Hinted handoff runs: N4 → sends K=42 to N2
        NOW consistency is restored.
```

### Why This Happens

```
    STRICT QUORUM                    SLOPPY QUORUM
    ─────────────                    ─────────────
    Write set ⊆ {N1,N2,N3}          Write set ⊆ {ANY nodes}
    Read set  ⊆ {N1,N2,N3}          Read set  ⊆ {N1,N2,N3}
         │                                │
         ▼                                ▼
    Overlap GUARANTEED               Overlap NOT guaranteed
    (pigeonhole principle)           (different universes)
```

The "sloppy" in sloppy quorum refers to this relaxation: **we accept writes on a larger set than we read from**, so the quorum intersection property no longer holds.

---

## 6. Integration with Hinted Handoff

Hinted handoff is the **reconciliation mechanism** that makes sloppy quorum eventually consistent.

### Lifecycle of a Hinted Write

```
    HINTED HANDOFF LIFECYCLE
    ════════════════════════

    Phase 1: WRITE (during failure)
    ┌──────────┐         ┌──────────┐
    │  Client  │────────▶│    N4    │  N2 is down, N4 accepts
    └──────────┘         │  ┌────┐  │  write with hint
                         │  │HINT│  │
                         │  │→N2 │  │
                         │  └────┘  │
                         └──────────┘

    Phase 2: MONITOR (periodic health checks)
    ┌──────────┐         ┌──────────┐
    │    N4    │─ ─ ─ ?──│    N2    │  N4 periodically checks
    │  ┌────┐  │         │  (DOWN)  │  if N2 is alive
    │  │HINT│  │         └──────────┘
    │  └────┘  │
    └──────────┘

    Phase 3: REPLAY (target recovered)
    ┌──────────┐         ┌──────────┐
    │    N4    │════════▶│    N2    │  N2 is back! N4 sends
    │  ┌────┐  │  data   │  ┌────┐  │  the hinted data
    │  │HINT│──┼─────────┼─▶│ K  │  │
    │  └────┘  │         │  └────┘  │
    └──────────┘         └──────────┘

    Phase 4: CLEANUP (hint deleted)
    ┌──────────┐         ┌──────────┐
    │    N4    │  ACK ◀──│    N2    │  N2 acknowledges,
    │  (empty) │         │  ┌────┐  │  N4 deletes hint
    │          │         │  │ K  │  │
    └──────────┘         │  └────┘  │
                         └──────────┘
```

### Edge Cases and Failure Modes

**What if the temporary holder (N4) also crashes before handoff?**

```
    DOUBLE FAILURE: DATA LOSS RISK
    ══════════════════════════════

    T1: N2 down, write goes to N4 (hint for N2)
    T2: N4 crashes before hinted handoff completes
    T3: N2 recovers — but never receives the data

    ┌────┐    ┌────┐    ┌────┐    ┌────┐
    │ N1 │    │ N2 │    │ N3 │    │ N4 │
    │K=42│    │    │    │    │    │    │  ← hint LOST
    │    │    │back│    │back│    │DEAD│
    └────┘    └────┘    └────┘    └────┘

    Only N1 has K=42. If N1 also fails → DATA LOST.
```

**Mitigations**:
- Set W > 1 for the sloppy write (write to multiple fallback nodes)
- Use persistent hint storage (WAL on disk)
- Set TTL on hints — if not delivered within TTL, trigger anti-entropy repair
- Complement with periodic Merkle-tree-based anti-entropy sync

---

## 7. Preference List

The **preference list** is an ordered list of nodes that can hold replicas for a given key. It extends beyond the N designated replicas to include fallback candidates.

```
    PREFERENCE LIST FOR KEY K
    ═════════════════════════

    Position on ring determines the list:

    ┌─────────────────────────────────────────────────────────┐
    │  Preference List (ordered by ring position, clockwise)  │
    ├─────────────────────────────────────────────────────────┤
    │  Position 1: N1  ─┐                                     │
    │  Position 2: N2   ├── Top N (designated replicas)       │
    │  Position 3: N3  ─┘                                     │
    │  Position 4: N4  ─┐                                     │
    │  Position 5: N5   ├── Fallback nodes (for sloppy Q)    │
    │  Position 6: N6  ─┘                                     │
    └─────────────────────────────────────────────────────────┘

    Write algorithm:
    ┌─────────────────────────────────────────────────────┐
    │  for node in preference_list:                        │
    │      if node.is_healthy():                           │
    │          write(node, key, value)                     │
    │          successful_writes++                         │
    │          if node not in top_N:                       │
    │              mark_as_hint(node, intended=top_N[i])   │
    │      if successful_writes >= W:                      │
    │          return SUCCESS                              │
    │  return FAILURE                                      │
    └─────────────────────────────────────────────────────┘
```

### DynamoDB's Design

Amazon's Dynamo paper specifies that the preference list is **longer than N** specifically to accommodate sloppy quorum. The list skips virtual nodes that map to the same physical machine to ensure replicas land on distinct physical hosts.

```
    DYNAMO PREFERENCE LIST WITH VIRTUAL NODES
    ══════════════════════════════════════════

    Physical nodes: A, B, C, D, E
    Virtual nodes on ring: A1, B1, C1, A2, D1, B2, E1, C2, D2, E2

    Key K hashes between E1 and C2.
    Walk clockwise: C2, D2, E2, A1, B1, C1, A2, D1, B2, E1

    But C2 and C1 are same physical node C!
    Skip duplicates:

    Preference list (distinct physical): [C, D, E, A, B]
                                          ├─────┤  ├──┤
                                          N=3      fallback
```

---

## 8. Real-World Implementations

### Amazon DynamoDB (Dynamo Paper, 2007)

The original design that popularized sloppy quorum.

| Aspect | Detail |
|--------|--------|
| Quorum | Configurable N, R, W per table |
| Default | N=3, R=2, W=2 |
| Sloppy quorum | Always on for internal Dynamo |
| Hinted handoff | Hints stored with TTL, periodic delivery attempts |
| Conflict resolution | Vector clocks + application-level reconciliation |
| Anti-entropy | Merkle trees for background sync |

### Apache Cassandra

Cassandra offers **both** strict and sloppy quorum via consistency levels:

```
    CASSANDRA CONSISTENCY LEVELS
    ════════════════════════════

    ┌─────────────────┬──────────────────────────────────────┐
    │ Consistency     │ Behavior                             │
    │ Level           │                                      │
    ├─────────────────┼──────────────────────────────────────┤
    │ ONE             │ Sloppy — any 1 node (may use hints)  │
    │ TWO             │ Sloppy — any 2 nodes                 │
    │ QUORUM          │ Strict — majority of designated      │
    │ LOCAL_QUORUM    │ Strict — majority in local DC        │
    │ ALL             │ Strict — all designated replicas     │
    │ ANY             │ Most sloppy — even coordinator hint  │
    └─────────────────┴──────────────────────────────────────┘

    CL=ANY is the extreme: coordinator itself can store a hint
    and return success. Maximum availability, minimum durability.
```

### Riak

- N, R, W configurable per bucket
- Sloppy quorum is the **default** behavior
- `pw` and `pr` parameters enforce "primary" (designated) writes/reads for stricter behavior
- Uses dotted version vectors for conflict detection

### Voldemort (LinkedIn)

- Direct Dynamo clone in Java
- Sloppy quorum with configurable parameters
- Hinted handoff with periodic sweeper threads
- Used internally at LinkedIn for profile data, activity feeds

---

## 9. Trade-off Analysis

### Benefits

```
    ┌─────────────────────────────────────────────────┐
    │           AVAILABILITY IMPROVEMENT               │
    ├─────────────────────────────────────────────────┤
    │                                                  │
    │  Strict (N=3, W=2):                             │
    │    Tolerates 1 failure   → 2 of 3 must be up    │
    │                                                  │
    │  Sloppy (N=3, W=2, cluster=6):                  │
    │    Tolerates up to 4 failures → any 2 of 6      │
    │                                                  │
    │  Write availability:                             │
    │    Strict:  P(success) = 1 - P(≥2 of 3 down)   │
    │    Sloppy:  P(success) = 1 - P(≥5 of 6 down)   │
    │                                                  │
    │  For 1% per-node failure rate:                   │
    │    Strict:  ~99.97% availability                 │
    │    Sloppy:  ~99.9999985% availability            │
    └─────────────────────────────────────────────────┘
```

### Costs

| Cost | Description |
|------|-------------|
| Consistency gap | Reads may miss recent writes during handoff window |
| Operational complexity | Hint queues, monitoring, TTL management |
| Storage overhead | Temporary nodes store data they don't "own" |
| Cascading load | Failures cause load redistribution to fallback nodes |
| Data loss risk | Double failures can lose hinted data |

### Decision Framework

```
    WHEN TO USE STRICT vs SLOPPY QUORUM
    ════════════════════════════════════

    Use STRICT quorum when:
    ┌─────────────────────────────────────────────┐
    │ • Strong consistency is required (banking)   │
    │ • Read-after-write guarantee needed          │
    │ • Conflict resolution is expensive           │
    │ • Data loss is unacceptable                  │
    │ • Regulatory compliance (ACID required)      │
    └─────────────────────────────────────────────┘

    Use SLOPPY quorum when:
    ┌─────────────────────────────────────────────┐
    │ • Availability > consistency (shopping cart) │
    │ • Writes must never be rejected              │
    │ • Eventual consistency is acceptable         │
    │ • System handles conflicts via CRDT/merge    │
    │ • SLA mandates 99.99%+ write availability    │
    └─────────────────────────────────────────────┘
```

---

## 10. Architect's Guide

### Choosing Your Quorum Strategy

```
    DECISION TREE
    ═════════════

    Can your application tolerate stale reads?
        │
        ├── NO → Use STRICT quorum (R+W > N)
        │         │
        │         └── Can you tolerate write failures during partitions?
        │               ├── YES → Pure strict quorum
        │               └── NO  → You have conflicting requirements.
        │                         Consider: consensus (Raft/Paxos)
        │
        └── YES → How important is write availability?
                    │
                    ├── Critical (SLA 99.99%+) → SLOPPY quorum
                    │     + hinted handoff
                    │     + anti-entropy repair
                    │     + read repair
                    │
                    └── Nice-to-have → Strict quorum with
                                       client-side retry + backoff
```

### SLA Implications

| SLA Target | Recommended Approach |
|------------|---------------------|
| 99.9% (8.7h downtime/yr) | Strict quorum with N=3, W=2 |
| 99.99% (52min downtime/yr) | Sloppy quorum or multi-DC strict |
| 99.999% (5min downtime/yr) | Sloppy quorum + multi-DC + aggressive hinted handoff |

### Complementary Mechanisms Required with Sloppy Quorum

Sloppy quorum alone is insufficient. A production system needs:

1. **Hinted Handoff** — Short-term reconciliation (seconds to minutes)
2. **Read Repair** — Fix inconsistencies detected during reads
3. **Anti-Entropy (Merkle Trees)** — Background full-dataset consistency check
4. **Conflict Resolution** — Vector clocks, LWW, or CRDTs for concurrent writes

```
    CONSISTENCY RECOVERY TIMELINE
    ═════════════════════════════

    Write occurs during partition
    │
    ├── Hinted Handoff ─────── seconds to minutes
    │   (best case: node recovers quickly)
    │
    ├── Read Repair ────────── on next read
    │   (fixes inconsistency when detected)
    │
    └── Anti-Entropy ───────── hours (background)
        (catches anything missed by above)

    Together these provide convergence guarantee:
    All replicas will EVENTUALLY hold consistent data,
    assuming no permanent node loss.
```

### Production Checklist

- [ ] Define acceptable staleness window for your use case
- [ ] Set hint TTL (don't let hints accumulate forever)
- [ ] Monitor hint queue depth — growing queues indicate systemic issues
- [ ] Alert on hint delivery failures
- [ ] Test double-failure scenarios (hint holder dies)
- [ ] Implement read repair alongside sloppy quorum
- [ ] Run periodic anti-entropy scans
- [ ] Capacity plan for fallback node load during failures
- [ ] Document conflict resolution strategy for your data model

---

## Summary

Sloppy quorum is a deliberate trade: it sacrifices the consistency guarantee of strict quorum (R+W>N intersection) in exchange for dramatically higher write availability during failures. It is not a replacement for strict quorum but an alternative operating point on the CAP spectrum, appropriate when your system prioritizes availability and can tolerate (and resolve) temporary inconsistency.

The key insight: **availability is a spectrum, not binary**. Sloppy quorum lets you write to any healthy nodes now and sort out placement later, turning a hard failure into a soft consistency delay.
