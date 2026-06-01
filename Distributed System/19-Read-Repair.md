# Read Repair

## 1. Problem Statement

In distributed databases using replication, replicas inevitably drift apart. This divergence occurs due to:

- **Failed writes**: A coordinator writes to 2 of 3 replicas; the third was temporarily unreachable.
- **Hinted handoff failures**: The hint store on the coordinator fills up or the coordinator itself crashes before replaying hints.
- **Network partitions**: A replica is isolated for a duration, missing a window of mutations.
- **Clock skew**: Timestamps disagree, causing silent overwrites or lost updates.
- **Partial failures during anti-entropy**: Merkle tree exchange was interrupted mid-stream.

The naive solution—full data scans comparing every key across every replica—is prohibitively expensive. For a cluster with billions of keys, scanning everything would saturate network and disk I/O continuously.

**Read Repair** solves this opportunistically: piggyback consistency checks onto normal read traffic. When a client reads data, the system uses that read as an opportunity to detect and fix inconsistencies—turning every read into a potential repair operation at marginal cost.

---

## 2. Core Mechanism

### How It Works

```
1. Client issues READ(key) to coordinator
2. Coordinator fans out read to N replicas (where N = replication factor)
3. Coordinator collects responses
4. Coordinator compares responses (version vectors, timestamps, checksums)
5. If all agree → return data to client
6. If divergent → determine winning value via conflict resolution
7. Write winning value back to stale replica(s)
8. Return winning value to client
```

### ASCII Diagram: Read Repair Flow

```
    Client
      │
      │  READ(key="user:42")
      ▼
  ┌──────────┐
  │Coordinator│
  └─────┬────┘
        │
        │ Fan-out read to all replicas
        ├────────────────────┬────────────────────┐
        ▼                    ▼                    ▼
  ┌──────────┐        ┌──────────┐        ┌──────────┐
  │ Replica A │        │ Replica B │        │ Replica C │
  │           │        │           │        │           │
  │ v=3       │        │ v=3       │        │ v=2       │
  │ ts=1001   │        │ ts=1001   │        │ ts=998    │
  │ data="bob"│        │ data="bob"│        │ data="al" │
  └─────┬─────┘        └─────┬─────┘        └─────┬─────┘
        │                     │                     │
        │ Response(v=3)       │ Response(v=3)       │ Response(v=2)
        ├─────────────────────┼─────────────────────┘
        ▼                     ▼
  ┌──────────┐
  │Coordinator│
  │           │
  │ Compare:  │
  │ A=v3 ✓   │
  │ B=v3 ✓   │
  │ C=v2 ✗   │  ← STALE!
  └─────┬────┘
        │
        ├──── Return "bob" (v=3) ────► Client
        │
        │  REPAIR: Write(v=3, "bob") to Replica C
        ▼
  ┌──────────┐
  │ Replica C │
  │ v=3  ✓   │  ← Now consistent
  │ data="bob"│
  └──────────┘
```

### Key Properties

| Property | Description |
|----------|-------------|
| **Lazy** | Only repairs keys that are actually read |
| **Opportunistic** | No dedicated repair traffic; piggybacks on reads |
| **Hot-data biased** | Frequently read keys get repaired fastest |
| **Incremental** | Fixes one key at a time, no bulk operations |

---

## 3. Types of Read Repair

### 3a. Foreground (Blocking) Read Repair

The client's read operation blocks until the repair write completes. The coordinator does not return the response until it has confirmed the stale replica has been updated.

```
    Client
      │
      │ READ(key)            Time
      ▼                        │
  Coordinator ─────────────────┼──────────────────────────────────
      │                        │
      ├── read ──► Replica A   │  ← returns v=5
      ├── read ──► Replica B   │  ← returns v=5
      ├── read ──► Replica C   │  ← returns v=3 (STALE)
      │                        │
      │ [Compare versions]     │
      │                        │
      ├── REPAIR write(v=5) ──► Replica C
      │                        │
      │ ◄── ACK ───────────── Replica C
      │                        │
      │ [Repair confirmed]     │
      │                        │
      ├── Response(v=5) ──► Client        ← Client waited for repair
      │                        │
  ────┼────────────────────────┼──────────────────────────────────
      │   Total latency =      │
      │   max(read latencies)  │
      │   + repair write RTT   │
                               ▼
```

**Characteristics:**

| Aspect | Detail |
|--------|--------|
| Consistency | Strong—after read returns, all replicas agree |
| Latency impact | P99 increases significantly; tail latency dominated by slowest replica + repair RTT |
| Use case | Financial systems, inventory counts, anything requiring read-after-write consistency |
| Failure mode | If repair write fails, coordinator may retry or timeout—further increasing latency |

### 3b. Background (Async) Read Repair

The coordinator returns the response to the client immediately after determining the winning value. The repair write is dispatched asynchronously—fire and forget.

```
    Client
      │
      │ READ(key)            Time
      ▼                        │
  Coordinator ─────────────────┼──────────────────────────────────
      │                        │
      ├── read ──► Replica A   │  ← returns v=5
      ├── read ──► Replica B   │  ← returns v=5
      ├── read ──► Replica C   │  ← returns v=3 (STALE)
      │                        │
      │ [Compare versions]     │
      │                        │
      ├── Response(v=5) ──► Client        ← Client gets response NOW
      │                        │
      │  [Async: background thread]       │
      │                        │
      ├── REPAIR write(v=5) ──► Replica C  (fire-and-forget)
      │                        │
  ────┼────────────────────────┼──────────────────────────────────
      │   Client latency =     │
      │   max(read latencies)  │
      │   (no repair wait)     │
                               ▼
```

**Characteristics:**

| Aspect | Detail |
|--------|--------|
| Consistency | Eventual—subsequent reads *may* still hit stale replica before repair lands |
| Latency impact | Minimal; client latency unaffected by repair |
| Use case | Social feeds, caches, analytics—where eventual consistency is acceptable |
| Failure mode | If repair write fails silently, inconsistency persists until next read or anti-entropy |

### Comparison

```
  Latency         Blocking              Async
  ─────────────────────────────────────────────────
  
  P50:            ~5ms                  ~3ms
  P99:            ~45ms (repair wait)   ~12ms
  P999:           ~200ms                ~25ms
  
  Consistency     Immediate             Eventual (seconds)
  after read:
  
  Repair          Guaranteed            Best-effort
  reliability:
```

---

## 4. Conflict Resolution During Repair

When replicas disagree, the coordinator must pick a winner. Several strategies exist:

### 4.1 Last Writer Wins (LWW) — Timestamp-Based

```
Replica A:  { value: "bob",   timestamp: 1709234567890 }
Replica B:  { value: "alice", timestamp: 1709234567920 }  ← WINS (higher ts)
Replica C:  { value: "bob",   timestamp: 1709234567890 }

Resolution: "alice" wins. Repair A and C with "alice".
```

**Pros**: Simple, deterministic, no coordination needed.  
**Cons**: Clock skew can silently drop writes. Concurrent writes lose data without detection.

### 4.2 Version Vector Comparison

```
Replica A:  { value: "bob",   vclock: {node1: 3, node2: 1} }
Replica B:  { value: "alice", vclock: {node1: 2, node2: 2} }

Comparison:
  A.node1(3) > B.node1(2) → A dominates on node1
  A.node2(1) < B.node2(2) → B dominates on node2
  
  Neither dominates → CONCURRENT / CONFLICT
```

When neither version vector dominates, we have a true conflict. Options:
- Return both as **siblings** to the application
- Apply a **CRDT merge** function
- Use application-defined **resolver callback**

### 4.3 Application-Level Resolution (Siblings)

Used by Riak (pre-CRDT era) and CouchDB:

```
Client READ(key) → receives:
  [
    { value: {cart: ["item1", "item2"]}, vclock: vc1 },
    { value: {cart: ["item1", "item3"]}, vclock: vc2 }
  ]

Application resolves:
  merged = {cart: ["item1", "item2", "item3"]}  // Union merge

Client WRITE(key, merged, vclock: merge(vc1, vc2))
```

### 4.4 Digest Comparison (Pre-check)

Before transferring full values, compare hashes:

```
Coordinator asks for digests:
  Replica A: SHA256(value) = 0xABCD...
  Replica B: SHA256(value) = 0xABCD...  ← Match!
  Replica C: SHA256(value) = 0x1234...  ← Different!

Only fetch full value from A (or B) and C to resolve.
```

This saves significant bandwidth when most reads find consistent data (the common case).

---

## 5. Read Repair vs Anti-Entropy

```
                    Read Repair                    Anti-Entropy
  ┌────────────────────────────────────┬──────────────────────────────────────┐
  │                                    │                                      │
  │  Triggered by: Client reads        │  Triggered by: Background timer      │
  │                                    │                                      │
  │  Coverage: Only keys being read    │  Coverage: ALL keys in the cluster   │
  │            (hot data)              │            (including cold data)      │
  │                                    │                                      │
  │  Cost: Marginal (per-read)         │  Cost: High (full Merkle tree scan)  │
  │                                    │                                      │
  │  Latency: Immediate               │  Latency: Periodic (hours/days)      │
  │                                    │                                      │
  │  Repair speed: Instant for hot     │  Repair speed: Eventually for all    │
  │                keys                │                                      │
  │                                    │                                      │
  │  Network: Low (single key)         │  Network: High (tree exchange +      │
  │                                    │           streaming differences)      │
  │                                    │                                      │
  │  Cold data: NEVER repaired         │  Cold data: Repaired on schedule     │
  │                                    │                                      │
  └────────────────────────────────────┴──────────────────────────────────────┘
```

### Why You Need Both

```
  Key Access Frequency
  ▲
  │
  │ █████  ← Hot keys: Read repair handles these efficiently
  │ █████
  │ █████████
  │ █████████████
  │ ██████████████████
  │ ██████████████████████████████  ← Warm keys: Read repair covers partially
  │ ████████████████████████████████████████████████████
  │ ██████████████████████████████████████████████████████████████████████
  │ ─────────────────────────────────────────────────────────────────────
  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
  │    ↑ Cold keys: ONLY anti-entropy repairs these
  └───────────────────────────────────────────────────────────────────────► Keys
```

**Complementary strategy:**
- Read repair provides **fast convergence for active data** (seconds)
- Anti-entropy provides **guaranteed convergence for all data** (hours)
- Together they minimize the window of inconsistency across the entire dataset

---

## 6. Probabilistic Read Repair

### The Problem with Repairing Every Read

If a cluster handles 100K reads/sec and 5% of reads find inconsistencies, that's 5K repair writes/sec added to the system. Even when data IS consistent, the overhead of comparing digests across all replicas on every single read is non-trivial.

### Solution: Repair with Probability p

```
On each read:
  if random() < read_repair_chance:
      perform_full_read_from_all_replicas()
      compare_and_repair_if_needed()
  else:
      read_from_CL_replicas_only()  // Normal fast path
```

### Cassandra's Configuration (Pre-4.0)

```yaml
# Probability of read repair for cross-DC reads
dclocal_read_repair_chance: 0.1    # 10% of reads trigger repair

# Probability of read repair (all DCs)  
read_repair_chance: 0.0            # Disabled for cross-DC (expensive)
```

**Note**: Cassandra 4.0+ deprecated these in favor of dedicated `nodetool repair` because probabilistic repair was found to be insufficient for long-running inconsistencies and added unpredictable load.

### Trade-off Curve

```
  Consistency     ▲
  (freshness)     │
                  │            ╭──────────── p = 1.0 (every read)
                  │         ╭──╯
                  │       ╭─╯
                  │     ╭─╯
                  │   ╭─╯              Sweet spot: p = 0.1
                  │  ╭╯                (90% cost reduction,
                  │ ╭╯                  ~10x slower convergence)
                  │╭╯
                  │╯
                  ├─────────────────────────────────────────► Read cost
                  0        0.1    0.2         0.5        1.0
                              Repair probability (p)
```

### Choosing the Right Probability

| Scenario | Recommended p | Rationale |
|----------|---------------|-----------|
| High-write, high-read workload | 0.01 - 0.05 | Writes keep things fresh; minimal repair needed |
| Read-heavy, infrequent writes | 0.1 - 0.2 | Stale data lingers longer; need more repair |
| Multi-DC with slow WAN | 0.0 (cross-DC) | Cross-DC repair too expensive; use anti-entropy |
| Small dataset, critical data | 1.0 | Dataset is small enough to afford full consistency |

---

## 7. Real-World Implementations

### Apache Cassandra

```
Read Path:
  1. Coordinator receives read request
  2. Sends data request to closest replica (by snitch)
  3. Sends digest requests to CL-1 additional replicas
  4. If digests match → return data
  5. If digests mismatch → full data read from all, repair
  6. Additionally: probabilistic background repair for non-CL replicas

Configuration (pre-4.0):
  ALTER TABLE users WITH
    read_repair_chance = 0.0 AND
    dclocal_read_repair_chance = 0.1;

Post-4.0:
  - Deprecated probabilistic read repair
  - Blocking read repair still occurs for CL violations
  - Incremental repair (`nodetool repair`) is the primary mechanism
```

### Amazon DynamoDB

```
Behavior:
  - Eventually consistent reads: No read repair (single replica read)
  - Strongly consistent reads: Reads from leader; no repair needed
  - Global tables (multi-region): Background replication + conflict resolution (LWW)

DynamoDB doesn't expose read repair as a tunable—it's internal.
Strong reads go to the leader replica, so staleness is impossible.
```

### Riak (KV)

```
Read Repair Flow:
  1. Client GET with R=2, N=3
  2. Coordinator reads from all 3 replicas (regardless of R)
  3. Returns to client after R replies
  4. Compares all 3 responses
  5. If divergent: repair using vector clock comparison
  6. If concurrent: return siblings (allow_mult=true) or use LWW

Additional: Active Anti-Entropy (AAE)
  - Persistent Merkle trees per vnode
  - Background exchange every 15 minutes
  - Catches anything read repair misses
```

### Voldemort (LinkedIn)

```
- Read repair triggered on every read
- Uses vector clocks for versioning
- Concurrent versions returned as list to client
- Repair writes merged version back
- No probabilistic mode—always full comparison
```

### CouchDB

```
- Multi-Version Concurrency Control (MVCC)
- Conflicts stored as document branches (revision tree)
- On read: winning revision returned, conflicts accessible via ?conflicts=true
- Application responsible for resolving conflicts
- Replication protocol detects and propagates conflicts
- No automatic read repair—conflict resolution is explicitly application-level
```

---

## 8. Digest Optimization

The digest (hash-based) optimization is critical for production systems because the majority of reads (often >99%) find consistent data. Transferring full values for every read across replicas would be wasteful.

### Flow

```
  ┌────────┐
  │ Client │
  └───┬────┘
      │ READ(key)
      ▼
  ┌──────────────┐
  │  Coordinator  │
  └──────┬───────┘
         │
         │ PHASE 1: Request data from ONE replica, digests from others
         │
         ├── GET_DATA(key) ──────────────────► Replica A
         ├── GET_DIGEST(key) ────────────────► Replica B
         ├── GET_DIGEST(key) ────────────────► Replica C
         │
         │ Responses:
         │   A: { data: "bob", version: 5, size: 4KB }
         │   B: { digest: SHA256("bob") = 0xABCD, version: 5 }
         │   C: { digest: SHA256("bob") = 0xABCD, version: 5 }
         │
         │ Compare: A.hash == B.digest == C.digest → ALL MATCH ✓
         │
         ├── Return "bob" to Client
         │
         │ Bandwidth used: 4KB (data) + 64B (two digests) = ~4KB
         │ vs. without optimization: 4KB × 3 = 12KB
         │
  ═══════╪═══════════════════════════════════════════════════════
         │
         │ MISMATCH SCENARIO:
         │
         │   A: { data: "bob", version: 5 }
         │   B: { digest: 0xABCD, version: 5 }
         │   C: { digest: 0x1234, version: 3 }  ← MISMATCH!
         │
         │ PHASE 2: Full data fetch from mismatched replica
         │
         ├── GET_DATA(key) ──────────────────► Replica C
         │
         │   C: { data: "al", version: 3 }
         │
         │ Resolution: version 5 > version 3 → "bob" wins
         │
         │ PHASE 3: Repair
         │
         ├── PUT(key, "bob", v=5) ───────────► Replica C
         │
         ├── Return "bob" to Client
         │
  ───────┴──────────────────────────────────────────────────────
```

### Bandwidth Savings

```
Assume:
  - Average value size: 4KB
  - Digest size: 32 bytes (SHA-256)
  - Replication factor: 3
  - Inconsistency rate: 1%

Without digest optimization:
  Per read: 3 × 4KB = 12KB network transfer

With digest optimization:
  99% of reads (consistent): 4KB + 2×32B = ~4.06KB   (66% savings)
  1% of reads (inconsistent): 4KB + 32B + 4KB = ~8KB  (then repair write)

  Average: 0.99 × 4.06KB + 0.01 × 8KB = 4.10KB per read
  Savings: (12KB - 4.10KB) / 12KB = 65.8% bandwidth reduction
```

---

## 9. Operational Concerns

### 9.1 Read Amplification

Read repair causes additional writes. In a write-heavy system this can cascade:

```
Normal read:       1 read op
Read + repair:     1 read op + 1 write op (to stale replica)
                   That write triggers compaction on the stale replica
                   That compaction consumes disk I/O and CPU
                   
In extreme cases (many stale replicas):
  1 read → N-1 repair writes → N-1 compactions
```

**Mitigation**: Use probabilistic repair or disable read repair on write-heavy tables.

### 9.2 Tail Latency Impact

```
  Latency
  Distribution
  
  ▲
  │                              Without read repair
  │  ╭╮
  │  │╰╮
  │  │  ╰╮
  │  │    ╰──╮
  │  │        ╰────────────────────────────── P99 = 15ms
  │  │
  │  ╭╮                         With blocking read repair
  │  │╰╮
  │  │  ╰╮
  │  │    ╰──╮
  │  │        ╰──────╮
  │  │               ╰────────────────────────────────── P99 = 45ms
  │  │                                                      ↑
  └──┴──────────────────────────────────────────────────────┴──► Latency (ms)
     0    5    10   15   20   25   30   35   40   45   50
```

Blocking read repair adds the repair write latency to the read path, directly inflating P99 and P999.

### 9.3 Monitoring Repair Rate

The **read repair rate** is a key cluster health metric:

```
Healthy cluster:     repair_rate / total_reads < 0.01  (< 1%)
Degraded:           repair_rate / total_reads = 0.01 - 0.05
Unhealthy:          repair_rate / total_reads > 0.05   (> 5%)
```

**High repair rates indicate:**
- A replica recently recovered from an outage and is catching up
- Hinted handoff is failing systematically
- Network partition caused a divergence window
- Anti-entropy repairs are not running (or are failing)
- A node has corrupted data (disk issue)

### 9.4 Read Repair Storms

When a previously-down node returns with very stale data, every read hitting that node triggers a repair. This can cause a **repair storm**:

```
Node C comes back after 2-hour outage
  → 100K keys are stale on Node C
  → Reads distributed across ring include Node C
  → Suddenly 30K repair writes/sec to Node C
  → Node C disk I/O saturates
  → Node C becomes slow → more timeouts → cascading failure
```

**Mitigation strategies:**
- Rate-limit repair writes per node
- Use anti-entropy (full repair) before bringing node back to serving traffic
- Gradually increase traffic to recovered nodes (traffic ramping)

---

## 10. Architect's Guide

### When to Enable Read Repair

| Enable | Disable |
|--------|---------|
| Read-heavy workloads with eventual consistency requirements | Write-heavy tables where repair writes add unacceptable load |
| Hot key patterns where convergence speed matters | Append-only/immutable data (no conflicts possible) |
| Multi-DC deployments for local DC repair | Time-series data with TTL (self-healing via expiry) |
| Systems without regular anti-entropy schedules | Tables under heavy compaction pressure |

### Tuning Parameters

```
┌─────────────────────────────────────────────────────────────────────┐
│ Parameter               │ Conservative    │ Aggressive              │
├─────────────────────────┼─────────────────┼─────────────────────────┤
│ repair_probability      │ 0.01 (1%)       │ 1.0 (every read)        │
│ blocking vs async       │ async           │ blocking                │
│ digest_optimization     │ enabled         │ enabled                 │
│ cross_dc_repair         │ disabled        │ enabled (if WAN is fast)│
│ repair_timeout          │ 100ms           │ 500ms                   │
│ max_repair_rate/node    │ 1000 ops/sec    │ unlimited               │
└─────────────────────────┴─────────────────┴─────────────────────────┘
```

### Decision Framework

```
                      Is data mutable?
                           │
                    ┌──────┴──────┐
                    │ No          │ Yes
                    ▼             ▼
              No read repair   Is low read latency critical?
              needed                    │
                              ┌────────┴────────┐
                              │ Yes             │ No
                              ▼                 ▼
                     Async read repair    Blocking read repair
                     p = 0.1              p = 1.0
                              │                 │
                              ▼                 ▼
                     Complement with      May skip anti-entropy
                     anti-entropy          for hot data
                     for cold data
```

### Complementary Mechanisms

Read repair does not exist in isolation. A production system combines:

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                    Consistency Stack                              │
  │                                                                  │
  │  Layer 1: Write Path          Quorum writes (W + R > N)          │
  │  Layer 2: Hinted Handoff      Replay missed writes on recovery   │
  │  Layer 3: Read Repair         Fix on read (hot data, fast)       │
  │  Layer 4: Anti-Entropy        Merkle tree repair (all data)      │
  │  Layer 5: Full Repair         Streaming repair (last resort)     │
  │                                                                  │
  │  Convergence     Seconds        Minutes       Hours              │
  │  speed:          (L1-L3)        (L2-L4)       (L4-L5)           │
  │                                                                  │
  │  Coverage:       Hot data       Recent data    All data           │
  └──────────────────────────────────────────────────────────────────┘
```

### Key Takeaways

1. **Read repair is not a substitute for anti-entropy**—it only covers data that is actively read.
2. **Digest optimization is non-negotiable** in production—without it, read repair doubles your read bandwidth.
3. **Monitor repair rate religiously**—a spike signals infrastructure problems before they cascade.
4. **Blocking repair is rarely worth it**—the P99 hit is severe; prefer async repair + quorum reads for strong consistency.
5. **Disable cross-DC repair** unless you have measured the WAN cost and accept it.
6. **After node recovery, run anti-entropy before serving reads**—prevents repair storms.
7. **Probabilistic repair at p=0.1 is a good default**—it provides 90% of the convergence benefit at 10% of the cost.

---

## References

- Dynamo Paper (DeCandia et al., 2007) — Original description of read repair in production
- Apache Cassandra documentation — Read path and repair mechanics
- Riak documentation — Active Anti-Entropy design
- "Designing Data-Intensive Applications" (Kleppmann, 2017) — Chapter 5: Replication
