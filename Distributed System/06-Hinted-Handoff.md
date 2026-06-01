# Hinted Handoff

## 1. Problem Statement

In a distributed database with replicated data, writes are directed to specific replica nodes determined by the partitioning scheme (e.g., consistent hashing). When a target replica node experiences a **transient failure** (network partition, GC pause, restart, hardware maintenance), the system faces a dilemma:

| Option | Trade-off |
|--------|-----------|
| Reject the write | Sacrifices **availability** (violates AP in CAP) |
| Wait for recovery | Increases **latency** unboundedly |
| Write elsewhere with no tracking | Data is **lost** for that replica permanently |

**Hinted Handoff** resolves this by temporarily storing writes on a healthy surrogate node with metadata ("hints") indicating the intended recipient. When the failed node recovers, hints are replayed, achieving **write availability without permanent data loss**.

---

## 2. Core Mechanism

### Concept

1. Client sends write for key K → coordinator determines replicas {A, B, C}
2. Node B is detected as down (via gossip/failure detector)
3. Coordinator (or another healthy node D) accepts B's write **with a hint**
4. Hint = `{intended_target: B, timestamp: T, payload: <mutation>}`
5. When B recovers, D replays all accumulated hints to B, then deletes them locally

### Normal Write vs Hinted Write

```
                    NORMAL WRITE (all replicas healthy)
                    ===================================

  Client                Coordinator              Node A    Node B    Node C
    |                       |                      |         |         |
    |--- PUT(K, V) -------->|                      |         |         |
    |                       |--- write(K,V) ------>|         |         |
    |                       |--- write(K,V) ----------------->|         |
    |                       |--- write(K,V) ------------------------------>|
    |                       |                      |         |         |
    |                       |<-- ACK --------------|         |         |
    |                       |<-- ACK ------------------------|         |
    |                       |<-- ACK --------------------------------------|
    |<-- OK (W=3 met) -----|                      |         |         |
    |                       |                      |         |         |


                    HINTED WRITE (Node B is down)
                    ==============================

  Client                Coordinator              Node A    Node B    Node D
    |                       |                      |         |  XX     |
    |--- PUT(K, V) -------->|                      |         |  DOWN   |
    |                       |--- write(K,V) ------>|         |         |
    |                       |--- write(K,V) ------>| TIMEOUT |         |
    |                       |                      |         |         |
    |                       |  [B detected down, select D as surrogate]  |
    |                       |                      |         |         |
    |                       |--- hinted_write(K,V, hint=B) ------------>|
    |                       |--- write(K,V) ------------------------------>| (Node C)
    |                       |                      |         |         |
    |                       |<-- ACK --------------|         |         |
    |                       |<-- ACK (hint stored) ----------------------|
    |                       |<-- ACK ----------------------------------------| (C)
    |<-- OK (W=3 met) -----|                      |         |         |
    |                       |                      |         |         |
```

### Handoff on Recovery

```
  Node D (hint holder)           Node B (recovered)
    |                                  |
    | [Detects B is back via gossip]   |
    |                                  |
    |--- replay_hint(K1, V1) --------->|
    |<-- ACK --------------------------|
    |--- replay_hint(K2, V2) --------->|
    |<-- ACK --------------------------|
    |--- replay_hint(K3, V3) --------->|
    |<-- ACK --------------------------|
    |                                  |
    | [All hints delivered, delete     |
    |  local hint store for B]         |
    |                                  |
```

---

## 3. Algorithm in Detail

### Step-by-Step

```
PROCEDURE handle_write(key K, value V, replicas R[]):
    for each node N in R[]:
        if is_alive(N):
            send_write(N, K, V)
        else:
            surrogate = select_surrogate(N)      // next in ring or any live node
            hint = {
                target:    N,
                key:       K,
                value:     V,
                timestamp: now(),
                ttl:       HINT_TTL              // e.g., 3 hours
            }
            send_hinted_write(surrogate, hint)
    
    await W acknowledgments (from real writes + hint ACKs)
    return SUCCESS if W met, else FAILURE

PROCEDURE hint_replay_loop():            // runs on every node
    every REPLAY_INTERVAL:
        for each target T in local_hint_store.targets():
            if is_alive(T):
                hints = local_hint_store.get_all(T)
                for hint in hints (ordered by timestamp):
                    result = send_write(T, hint.key, hint.value)
                    if result == ACK:
                        local_hint_store.delete(hint)
                    else:
                        break    // T went down again, retry later

PROCEDURE hint_expiry_loop():
    every CLEANUP_INTERVAL:
        for each hint in local_hint_store:
            if now() - hint.timestamp > hint.ttl:
                local_hint_store.delete(hint)
                metrics.increment("hints_expired")
```

### Full Lifecycle Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     HINTED HANDOFF LIFECYCLE                             │
└─────────────────────────────────────────────────────────────────────────┘

  TIME ──────────────────────────────────────────────────────────────►

  T0: Normal operation
  ┌─────┐    ┌─────┐    ┌─────┐
  │  A  │    │  B  │    │  C  │     All replicas healthy
  └─────┘    └─────┘    └─────┘

  T1: Node B fails
  ┌─────┐    ┌─────┐    ┌─────┐    ┌─────┐
  │  A  │    │  B  │    │  C  │    │  D  │
  └─────┘    └──╳──┘    └─────┘    └─────┘
                 │                      │
                 │   B's writes go ─────┘
                 │   to D with hints
                 ▼
         ┌──────────────┐
         │ D's Hint     │
         │ Store:       │
         │  hint1(B,K1) │
         │  hint2(B,K2) │
         │  hint3(B,K3) │
         └──────────────┘

  T2: Node B recovers
  ┌─────┐    ┌─────┐    ┌─────┐    ┌─────┐
  │  A  │    │  B  │    │  C  │    │  D  │
  └─────┘    └─────┘    └─────┘    └─────┘
                 ▲                      │
                 │                      │
                 └──── replay hints ────┘
                       K1, K2, K3

  T3: Handoff complete
  ┌─────┐    ┌─────┐    ┌─────┐    ┌─────┐
  │  A  │    │  B  │    │  C  │    │  D  │
  └─────┘    └─────┘    └─────┘    └─────┘
              (caught up)           (hints deleted)
```

### Integration with Consistent Hashing Ring

```
            Consistent Hashing Ring with Hinted Handoff
            =============================================

                         Node A (token 0)
                        ╱              ╲
                      ╱                  ╲
                    ╱                      ╲
         Node F (token 250)          Node B (token 50) ← DOWN
                  │                        │
                  │                        │ Key K hashes to token 42
                  │                        │ Replicas: B, C, D (clockwise)
                  │                        │
         Node E (token 200)          Node C (token 100)
                    ╲                      ╱
                      ╲                  ╱
                        ╲              ╱
                         Node D (token 150)

    Key K (token 42) → Replica list: [B, C, D]
    B is down → Sloppy replica list: [E, C, D]
                                       ▲
                                       │
                              E holds hint for B
                              (next healthy node
                               walking the ring)
```

---

## 4. Hint Storage

### Architecture

Hints are stored in a **dedicated, separate store** from regular data:

```
┌─────────────────────────────────────────────┐
│              Node D Storage                  │
├─────────────────────┬───────────────────────┤
│   Regular Data      │     Hint Store        │
│   (SSTables/        │   (Separate files/    │
│    Memtables)       │    directory)         │
│                     │                       │
│   K1 → V1          │   Target: B           │
│   K5 → V5          │     hint1: {K,V,T}    │
│   K9 → V9          │     hint2: {K,V,T}    │
│                     │     hint3: {K,V,T}    │
│                     │                       │
│                     │   Target: E           │
│                     │     hint4: {K,V,T}    │
└─────────────────────┴───────────────────────┘
```

**Why separate?**
- Hints are transient; regular data is permanent
- Different compaction/GC strategies
- Hints can be bulk-deleted per target without touching data files
- Easier to monitor and size independently

### TTL on Hints

Hints typically expire after **1–3 hours** (Cassandra default: 3 hours). Rationale:

| Reason | Explanation |
|--------|-------------|
| Disk exhaustion | Long outage → unbounded hint accumulation |
| Staleness | Very old hints may conflict with newer writes already reconciled by anti-entropy |
| Failure reclassification | If node is down > 3 hours, it's likely a **permanent** failure requiring full repair, not hint replay |
| Operational signal | Expired hints trigger alerts → operator knows repair is needed |

### Hint Compaction

- **Deduplication**: Multiple writes to same key → keep only latest (last-write-wins)
- **Tombstone absorption**: Write + Delete for same key → hints cancel out
- **Batch coalescing**: Multiple small hints merged into batch mutations for efficient replay

### Disk Space Management

```
Configuration knobs:
  max_hints_size_per_host:     128 MB   (per-target cap)
  max_hints_total_size:        1 GB     (total across all targets)
  hints_flush_period:          10 sec
  hints_compression:           LZ4      (reduce I/O footprint)

When limits exceeded:
  → Oldest hints evicted (FIFO)
  → Metric: hints_dropped incremented
  → Alert: operator must run full repair
```

---

## 5. Sloppy Quorum Integration

### Strict Quorum vs Sloppy Quorum

**Strict quorum**: W writes must go to nodes in the **designated** replica set.  
**Sloppy quorum**: W writes can go to **any** W nodes, including non-designated nodes holding hints.

```
    STRICT QUORUM (W=2, replicas={A,B,C}, B is down)
    ─────────────────────────────────────────────────
    Write to A: ✓
    Write to B: ✗ (down)
    Write to C: ✓
    Result: W=2 met → SUCCESS (but only among designated replicas)
    
    If A AND B are down:
    Write to A: ✗
    Write to C: ✓
    Result: W=2 NOT met → FAILURE (write rejected)


    SLOPPY QUORUM (W=2, replicas={A,B,C}, B is down)
    ─────────────────────────────────────────────────
    Write to A: ✓
    Write to B: ✗ (down) → redirect to D (hint)
    Write to D: ✓ (hint for B)
    Write to C: ✓
    Result: W=2 met (A + D counted) → SUCCESS
    
    If A AND B are down:
    Write to D: ✓ (hint for A)
    Write to E: ✓ (hint for B)  
    Write to C: ✓
    Result: W=2 met → SUCCESS (higher availability!)
```

### Diagram: Sloppy Quorum with Hinted Handoff

```
    Write(K, V) with N=3, W=2, R=2

    Preference list for K: [B, C, D]    (B is down)
    Extended list:         [B, C, D, E, F, ...]

    ┌──────────────────────────────────────────────────────────┐
    │  Coordinator                                             │
    │                                                          │
    │  1. Try B → TIMEOUT                                      │
    │  2. Walk list → next healthy = E                         │
    │  3. Send hinted_write to E (hint target=B)               │
    │  4. Send write to C → ACK                                │
    │  5. Send write to D → ACK                                │
    │                                                          │
    │  ACKs received: E(hint) + C + D = 3                      │
    │  W=2 satisfied ✓                                         │
    │                                                          │
    │  NOTE: A read with R=2 hitting C+D will get data.        │
    │        A read hitting E will NOT get data from            │
    │        regular store (it's in hint store only).           │
    └──────────────────────────────────────────────────────────┘
```

**Critical insight**: In sloppy quorum, hinted nodes **count toward W** for availability purposes, but they do **NOT** count toward R for read consistency. The hint store is opaque to read queries. This is why sloppy quorum sacrifices consistency for availability.

---

## 6. Consistency Implications

### Eventual Consistency Window

```
    Timeline of inconsistency:

    T0        T1              T2           T3
    │         │               │            │
    │  B dies │  Write to D   │  B returns │  Hints replayed
    │         │  (as hint)    │            │  B is consistent
    │         │               │            │
    ├─────────┼───────────────┼────────────┤
    │         │◄─────────────────────────►│
    │         │   INCONSISTENCY WINDOW     │
    │         │   (B missing data)         │
    │         │                            │
    │         │   Reads from B return      │
    │         │   stale/missing data       │
    └─────────┴────────────────────────────┘
```

### Failure Scenarios

| Scenario | Consequence | Mitigation |
|----------|-------------|------------|
| Target node recovers normally | Hints replayed, consistency restored | None needed |
| Hint-holding node fails before replay | **Hints lost permanently** | Anti-entropy repair |
| Both target + hint-holder fail | Data only on remaining replicas | Read repair + anti-entropy |
| Target never comes back | Hints expire (TTL), data lost on that replica | Full streaming repair to replacement node |
| Hint replay partially completes | Some data delivered, some not | Idempotent writes + retry |

### Safety Net: Anti-Entropy and Read Repair

Hinted handoff is an **optimization**, not a guarantee. The full consistency stack:

```
┌─────────────────────────────────────────────────────────────────┐
│                   CONSISTENCY MECHANISMS                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 3: Anti-Entropy (Merkle tree repair)    ← BACKGROUND     │
│           Full replica synchronization                           │
│           Catches ALL divergence                                 │
│           Expensive, runs periodically                           │
│                                                                  │
│  Layer 2: Read Repair                          ← ON READ        │
│           Detect stale replicas during reads                     │
│           Fix divergence for accessed keys                       │
│           Only works for hot keys                                │
│                                                                  │
│  Layer 1: Hinted Handoff                       ← ON WRITE       │
│           Fast recovery for transient failures                   │
│           Low overhead, handles common case                      │
│           Can lose hints (not durable guarantee)                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

    Coverage: Hinted Handoff ⊂ Read Repair ⊂ Anti-Entropy
    Cost:     Hinted Handoff < Read Repair < Anti-Entropy
    Speed:    Hinted Handoff > Read Repair > Anti-Entropy
```

---

## 7. Real-World Implementations

### Apache Cassandra

```yaml
# cassandra.yaml
hinted_handoff_enabled: true
max_hint_window_in_ms: 10800000          # 3 hours (default)
hinted_handoff_throttle_in_kb: 1024      # KB/s per target during replay
max_hints_delivery_threads: 2            # concurrent replay streams
hints_directory: /var/lib/cassandra/hints # separate from data
hints_compression:
  class_name: LZ4Compressor
```

Key behaviors:
- Hints stored as serialized mutations in dedicated hint files
- Per-destination hint isolation (one node's hints don't block another's)
- `nodetool statushandoff` to check hint state
- `nodetool resumehandoff` / `nodetool pausehandoff` for operational control
- Cassandra 3.0+: hints stored in a system table (`system.hints`) with improved compaction

### Amazon DynamoDB (Dynamo Paper)

From the 2007 Dynamo paper:
- Hinted handoff is a core design principle
- Sloppy quorum with preference list extension
- Hints stored in a separate local database on the surrogate
- Designed for "always writeable" data store semantics
- Combined with vector clocks for conflict resolution

### Riak

- Uses hinted handoff for **two** purposes:
  1. Transient failure recovery (classical)
  2. **Ownership handoff** during ring membership changes (vnode transfer)
- Configurable handoff concurrency: `handoff_concurrency = 2`
- Folder-based hint storage per vnode
- Handoff sender/receiver processes with backpressure

### Voldemort (LinkedIn)

- Slop store: dedicated BDB (Berkeley DB) store for hints
- Slop pusher: background thread replaying hints
- Configurable slop stores per node
- Hint routing: can use any node in the cluster, not just ring neighbors
- Supports "zone-aware" hinting (prefer hints within same datacenter)

### ScyllaDB

- Written in C++ for low-latency hint processing
- Per-shard hint stores (leveraging shared-nothing architecture)
- Significantly lower hint replay latency vs Cassandra
- Hint size limit per node: configurable, default 10 GB
- Mutation-based hint format (same as internal write path)
- View-based hint table for efficient scanning

---

## 8. Operational Concerns

### Monitoring Hint Queues

```
KEY METRICS TO MONITOR:
─────────────────────────────────────────────────────────
Metric                          Alert Threshold
─────────────────────────────────────────────────────────
hints_created_per_second        > 1000/s (sustained)
hints_total_stored              > 500 MB per node
hints_not_delivered             increasing monotonically
oldest_hint_age                 > hint_window / 2
hint_replay_rate                dropping to 0 (stuck)
hints_expired                   any (data loss signal)
─────────────────────────────────────────────────────────

INTERPRETATION:
  hints_created ↑ + hints_delivered = 0 → target is still down
  hints_created = 0 + hints_delivered ↑ → recovery in progress
  hints_expired > 0 → REPAIR REQUIRED (run anti-entropy)
```

### Hint Storms (Thundering Herd)

When a node that was down for a long time comes back:

```
                    HINT STORM
                    ══════════

  Node B recovers after 2 hours of downtime
  
  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐
  │  A  │  │  C  │  │  D  │  │  E  │  │  F  │
  └──┬──┘  └──┬──┘  └──┬──┘  └──┬──┘  └──┬──┘
     │        │        │        │        │
     │  ALL nodes simultaneously replay hints to B
     │        │        │        │        │
     ▼        ▼        ▼        ▼        ▼
            ┌─────────────────────────┐
            │          Node B          │
            │                          │
            │  CPU: 100%               │
            │  Disk I/O: saturated     │
            │  Network: saturated      │
            │  Compaction: backed up   │
            │                          │
            │  Result: B crashes again │
            └─────────────────────────┘
```

**Mitigations:**

| Strategy | Implementation |
|----------|---------------|
| Throttling | Limit replay to N KB/s per source (e.g., 1024 KB/s) |
| Concurrency cap | Max M simultaneous replay streams to one target |
| Staggered start | Random delay before beginning replay (jitter) |
| Backpressure | Target node signals "slow down" if overloaded |
| Progressive replay | Start slow, increase rate as target stabilizes |

### Disk I/O Impact on Hint-Holding Nodes

```
Normal operation:     [═══ data writes ═══]──────────────── disk bandwidth
                                                            
During hint storage:  [═══ data writes ═══][░░ hints ░░]── disk bandwidth
                                            ▲
                                            │
                                    Additional I/O burden
                                    (writes to hint store)

During hint replay:   [═══ data writes ═══][▓▓ replay ▓▓]─ disk bandwidth
                                            ▲
                                            │
                                    Read hints + send over network
                                    (read I/O + network)
```

Best practices:
- Place hint store on separate disk/partition if possible
- Use compression (LZ4) for hints
- Set hard disk space limits for hint store
- Monitor disk utilization on nodes holding many hints

---

## 9. Limitations and Complementary Mechanisms

### What Hinted Handoff Does NOT Cover

| Limitation | Explanation |
|------------|-------------|
| Permanent node loss | Hints expire; need full repair to new replacement node |
| Hint holder failure | Hints are single-copy; if hint holder dies, hints are lost |
| Long outages (> TTL) | Hints expire, creating gaps only anti-entropy can fill |
| Read consistency | Hints are invisible to reads; stale reads possible until replay |
| Network partitions (both sides active) | May create conflicting writes needing CRDTs or vector clocks |

### Defense in Depth

```
    Failure Duration vs Recovery Mechanism
    ═══════════════════════════════════════

    │
    │  Anti-Entropy
    │  (full Merkle tree sync)
    │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    │
    │  Read Repair (on-access)
    │  ████████████████████████████████████████████████████
    │
    │  Hinted Handoff
    │  ░░░░░░░░░░░░░░░░░░░░░░│
    │                         │
    │                    TTL expires
    ├─────────────────────────┼─────────────────────────── Duration
    0                      3 hours                      days/weeks
    
    
    Key: Hinted handoff handles the COMMON case (brief failures)
         cheaply and fast. Anti-entropy handles EVERYTHING but
         is expensive and slow.
```

---

## 10. Architect's Decision Guide

### When to Enable Hinted Handoff

| Enable | Disable |
|--------|---------|
| AP systems prioritizing write availability | CP systems requiring strong consistency |
| Transient failures are common (cloud environments, rolling upgrades) | Disk space is extremely constrained |
| Can tolerate eventual consistency | Hint replay I/O is unacceptable |
| Replication factor >= 3 | Single-replica setups (hints pointless) |

### Tuning Parameters

```
┌─────────────────────────────────────────────────────────────────────┐
│ Parameter                │ Conservative │ Aggressive │ Notes         │
├──────────────────────────┼──────────────┼────────────┼───────────────┤
│ hint_window              │ 1 hour       │ 6 hours    │ Balance disk  │
│                          │              │            │ vs coverage   │
├──────────────────────────┼──────────────┼────────────┼───────────────┤
│ replay_throttle (KB/s)   │ 512          │ 4096       │ Protect       │
│                          │              │            │ recovering    │
│                          │              │            │ node          │
├──────────────────────────┼──────────────┼────────────┼───────────────┤
│ max_hints_per_host (MB)  │ 64           │ 512        │ Disk budget   │
├──────────────────────────┼──────────────┼────────────┼───────────────┤
│ replay_threads           │ 1            │ 4          │ CPU/network   │
│                          │              │            │ trade-off     │
├──────────────────────────┼──────────────┼────────────┼───────────────┤
│ replay_check_interval    │ 30s          │ 5s         │ Recovery      │
│                          │              │            │ latency vs    │
│                          │              │            │ gossip load   │
└──────────────────────────┴──────────────┴────────────┴───────────────┘
```

### Monitoring Strategy

```
RUNBOOK: Hint Queue Growing

1. hints_stored > threshold?
   ├─ YES → Which target node(s)?
   │        ├─ Single target → That node is likely down
   │        │   └─ Check: is it expected maintenance?
   │        │       ├─ YES → hints will replay on return, monitor TTL
   │        │       └─ NO  → investigate node health
   │        └─ Multiple targets → Possible network partition
   │            └─ Check network, gossip state
   └─ NO → Healthy state

2. hints_expired > 0?
   └─ YES → DATA LOSS on that replica
       └─ ACTION: Schedule `nodetool repair` on affected node
                  after it recovers

3. hint_replay_rate = 0 but hints exist?
   └─ Possible causes:
       ├─ Target still down (expected)
       ├─ Replay thread stuck (bug)
       └─ Replay paused operationally
```

### Summary: Hinted Handoff in One Sentence

> A lightweight, best-effort mechanism that preserves write availability during transient node failures by temporarily storing mutations on surrogate nodes, trading strong consistency for availability and relying on anti-entropy as the ultimate consistency backstop.

---

## References

- DeCandia et al., "Dynamo: Amazon's Highly Available Key-value Store" (SOSP 2007)
- Apache Cassandra Documentation: Hinted Handoff
- Riak Documentation: Hinted Handoff and Handoff
- Kleppmann, "Designing Data-Intensive Applications" (2017), Chapter 5
