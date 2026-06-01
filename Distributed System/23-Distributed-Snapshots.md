# Distributed Snapshots

## 1. Problem Statement

In a distributed system, there is no shared memory, no global clock, and no way to
atomically "freeze" all nodes at the same instant. Yet we need to answer questions like:

- Is there a deadlock?
- Has a distributed computation terminated?
- Can we roll back to a consistent state after a failure?

All of these require capturing a **global state** — the combination of every process's
local state plus the state of every communication channel (messages in-flight).

**The fundamental tension:**

```
    Time ──────────────────────────────────────────────►

    P1:  ═══[state A]════════════[state B]═══════════►
                    \                     
                     \ msg m1            
                      \                  
    P2:  ═══[state X]══\═══[state Y]════[state Z]═══►
                         ▼               
                    m1 received          

    If we snapshot P1 at "state B" and P2 at "state X",
    we've captured P1 AFTER sending m1, but P2 BEFORE receiving m1.
    Where did m1 go? It must be recorded as "in the channel."

    If we snapshot P1 at "state A" and P2 at "state Z" (after receiving m1),
    we've captured P2 after receiving m1 but P1 before sending m1.
    This is INCONSISTENT — a message received but never sent.
```

**Requirements for a snapshot algorithm:**
1. Must not require stopping the system
2. Must produce a **consistent** global state
3. Must terminate in finite time
4. Should not require a global clock or synchronous execution

---

## 2. What is a Consistent Snapshot?

### Definitions

A **global state** S = (S₁, S₂, ..., Sₙ, C₁₂, C₁₃, ..., Cₙₙ₋₁) where:
- Sᵢ = local state of process i
- Cᵢⱼ = state of channel from i to j (messages in transit)

A **cut** is a set of events {e₁, e₂, ..., eₙ} — one "frontier" event per process
that divides its history into "before" and "after."

A **consistent cut** satisfies:
> For every message m: if the cut includes the **receive** of m,
> it must also include the **send** of m.

Equivalently: no causal arrows cross the cut from right to left.

### Consistent vs. Inconsistent Cuts

```
    Time ──────────────────────────────────────────────►

    P1:  ──●────●────●─────●─────●────●────●──────────►
           e1   e2   e3    e4    e5   e6   e7
                      │                ▲
                      │ send m1        │ recv m2
                      ▼                │
    P2:  ──●────●────●─────●─────●────●────●──────────►
           f1   f2   f3    f4    f5   f6   f7
                           │           ▲
                           │ send m2   │ recv m1
                           ▼           │
    P3:  ──●────●────●─────●─────●────●────●──────────►
           g1   g2   g3    g4    g5   g6   g7


    CONSISTENT CUT (C1):          INCONSISTENT CUT (C2):
                  │                            │
    P1:  ──●──●──●│──●──●──●──    P1:  ──●──●──●──●──●│──●──
                  │                                    │
    P2:  ──●──●──●│──●──●──●──    P2:  ──●──●──●│──●──●──●──
                  │                              │
    P3:  ──●──●──●│──●──●──●──    P3:  ──●──●──●──●──●│──●──
                  │                              │     │
                                                 
    C1: All cuts at same             C2: P2 cut is BEFORE sending m2,
    logical point. No message            but P3 cut is AFTER receiving m2.
    crosses from right to left.          m2 crosses right→left. INVALID!
```

**Why consistency matters:** An inconsistent snapshot represents a state that
could never have existed — violating causality. Any analysis on such a snapshot
(deadlock detection, termination detection) may produce false results.

---

## 3. Chandy-Lamport Algorithm (1985)

The seminal algorithm by K. Mani Chandy and Leslie Lamport for recording a
consistent global snapshot of a distributed system.

### Assumptions

1. **FIFO channels** — messages arrive in the order they were sent
2. **Reliable delivery** — no message loss, duplication, or corruption
3. **Strongly connected graph** — every process can reach every other process
4. **Finite message delay** — messages arrive in bounded time

### Algorithm Steps

```
INITIATOR (process Pᵢ decides to start snapshot):
───────────────────────────────────────────────────
1. Record own local state Sᵢ
2. Send MARKER message on every outgoing channel
3. Start recording incoming messages on ALL incoming channels

ON RECEIVING MARKER on channel Cⱼᵢ (from Pⱼ to Pᵢ):
───────────────────────────────────────────────────
IF Pᵢ has NOT yet recorded its state:
    1. Record own local state Sᵢ
    2. Record state of Cⱼᵢ = ∅ (empty — no messages in transit)
    3. Send MARKER on all outgoing channels
    4. Start recording messages on all OTHER incoming channels (not Cⱼᵢ)

ELSE (Pᵢ already recorded its state):
    1. Stop recording on channel Cⱼᵢ
    2. Channel state of Cⱼᵢ = all messages recorded since Pᵢ's state save
```

**Termination:** Each process finishes when it has received a MARKER on every
incoming channel.

### Execution Example: 3-Node System

```
    Initial: P1 has $100, P2 has $200, P3 has $50
    P1 sends $30 to P2 (msg A), P2 sends $20 to P3 (msg B)

    Step 0: P1 initiates snapshot
    ═══════════════════════════════════════════════════════════════

    P1                      P2                      P3
    ┌─────────┐             ┌─────────┐             ┌─────────┐
    │State:$70│             │State:$180│            │State:$50 │
    │(sent $30│             │(sent $20)│            │          │
    │ already)│             │          │            │          │
    └─────────┘             └─────────┘             └─────────┘

    Step 1: P1 records state ($70), sends MARKER to P2 and P3
    ═══════════════════════════════════════════════════════════════

    P1 ─────MARKER──────────► P2
    P1 ─────MARKER─────────────────────────────────► P3

    Channel P2→P1: P1 starts recording
    Channel P3→P1: P1 starts recording

    NOTE: msg A ($30) was sent BEFORE marker, so it's ahead of marker
          in the P1→P2 channel (FIFO!)

    Step 2: msg A ($30) arrives at P2 (before MARKER, because FIFO)
    ═══════════════════════════════════════════════════════════════

    P2 state becomes $210 ($180 + $30)

    Step 3: MARKER arrives at P2 from P1
    ═══════════════════════════════════════════════════════════════

    P2 has NOT recorded state yet (first MARKER), so:
      - Record state: $210
      - Channel P1→P2 state = ∅ (nothing between state-record and marker)
      - Send MARKER to P1 and P3
      - Start recording on channel P3→P2

    P2 ─────MARKER──────────► P1
    P2 ─────MARKER─────────────────────────────────► P3

    Step 4: MARKER arrives at P3 from P1
    ═══════════════════════════════════════════════════════════════

    P3 has NOT recorded state yet (first MARKER), so:
      - Record state: $50
      - Channel P1→P3 state = ∅
      - Send MARKER to P1 and P2
      - Start recording on channel P2→P3

    But wait — msg B ($20) from P2 is still in transit on P2→P3!

    Step 5: MARKER from P2 arrives at P1
    ═══════════════════════════════════════════════════════════════

    P1 already recorded state, so:
      - Stop recording on P2→P1
      - Channel P2→P1 state = [] (nothing was recorded)

    Step 6: msg B ($20) arrives at P3 (from P2, sent before P2's marker)
    ═══════════════════════════════════════════════════════════════

    P3 is recording on P2→P3, so it captures msg B ($20)

    Step 7: MARKER from P2 arrives at P3
    ═══════════════════════════════════════════════════════════════

    P3 already recorded state, so:
      - Stop recording on P2→P3
      - Channel P2→P3 state = [msg B ($20)]

    Step 8: MARKER from P3 arrives at P1 and P2
    ═══════════════════════════════════════════════════════════════

    P1: Stop recording on P3→P1. Channel state = []
    P2: Stop recording on P3→P2. Channel state = []

    ═══════════════════════════════════════════════════════════════
    FINAL SNAPSHOT:
    ═══════════════════════════════════════════════════════════════

    Process States:          Channel States:
    ┌──────────────┐         ┌───────────────────┐
    │ P1: $70      │         │ P1→P2: ∅          │
    │ P2: $210     │         │ P1→P3: ∅          │
    │ P3: $50      │         │ P2→P1: ∅          │
    └──────────────┘         │ P2→P3: [$20]      │
                             │ P3→P1: ∅          │
    Total: $70 + $210        │ P3→P2: ∅          │
         + $50 + $20 = $350  └───────────────────┘
    
    Conservation: Original total was $100+$200+$50 = $350 ✓
```

### Why It Works

The MARKER serves as a **causal separator** in each FIFO channel:

```
    Channel Pᵢ → Pⱼ:

    Messages sent         MARKER        Messages sent
    BEFORE Pᵢ's      ◄── boundary ──►  AFTER Pᵢ's
    state record                        state record
    ─────────────────────┃──────────────────────────────►
                         ┃
    These are captured   ┃  These are NOT part
    in channel state     ┃  of the snapshot
    if they arrive       ┃
    after Pⱼ's record   ┃
```

Because channels are FIFO, the MARKER perfectly divides messages into
"pre-snapshot" and "post-snapshot." Any message sent before the sender
recorded state will arrive before the marker at the receiver.

### Complexity

- **Messages:** O(E) markers, where E = number of directed channels
- **Time:** O(D) where D = diameter of the network (longest shortest path)
- **Space:** O(M) where M = messages in transit during snapshot

---

## 4. Properties of the Captured Snapshot

### The Snapshot May Never Have "Actually" Occurred

```
    Real execution timeline:

    P1:  ═══[A]══════[B]══════[C]══════════►
                        ↑
                    P1 records state B

    P2:  ═══[X]══════[Y]══════[Z]══════════►
              ↑
          P2 records state X

    The global state (B, X) may never have existed simultaneously
    in real time — P2 was already at Y or Z when P1 was at B.
```

### But It IS Reachable and Reaches

**Theorem (Chandy-Lamport):** If Sᵢₙᵢₜ is the state when the snapshot starts
and Sᶠⁱⁿ is the state when it ends, and S* is the recorded snapshot, then:

```
    Sᵢₙᵢₜ  ──(sequence of events)──►  S*  ──(sequence of events)──►  Sᶠⁱⁿ
```

The snapshot S* is reachable from the initial state and the final state is
reachable from S*. This makes it valid for detecting **stable properties**
(properties that once true, remain true): deadlock, termination, garbage.

### Use Cases Leveraging This Property

| Use Case | Why Snapshot Works |
|----------|-------------------|
| Deadlock detection | Deadlock is stable — if detected in snapshot, it's real |
| Garbage collection | Unreachability is stable |
| Termination detection | Termination is stable |
| Checkpointing | Can restart from S* and reach any state reachable from S* |
| Debugging | Provides a causally consistent view for inspection |

---

## 5. Applications of Distributed Snapshots

### a) Exactly-Once Processing (Stream Processing Checkpoints)

```
    Source ──► Op1 ──► Op2 ──► Sink
    
    Checkpoint = snapshot of (Op1 state, Op2 state, channel states)
    
    On failure: restore checkpoint, replay from source offset
    Result: each record processed exactly once in output
```

The snapshot captures operator state + in-flight messages. On recovery, replay
from the source position recorded in the snapshot. Messages in recorded channel
states are replayed first.

### b) Failure Recovery

```
    Normal execution:
    ════════════●═══════════●═══════════●══════╳ CRASH
              CP1         CP2         CP3
    
    Recovery:
    Restore CP3 ──► replay inputs since CP3 ──► continue
```

Periodic snapshots serve as recovery points. The system rolls back to the
latest complete snapshot and replays. Only works if input is replayable
(e.g., Kafka with offset tracking).

### c) Debugging

Capture snapshot without stopping system → inspect for invariant violations,
unexpected states. Particularly valuable in production where you cannot attach
debuggers or pause the system.

### d) Garbage Collection

In a distributed object system, determine which objects are globally unreachable:
1. Take consistent snapshot
2. Trace references from roots across all processes
3. Objects not reachable in snapshot can be collected (unreachability is stable)

### e) Termination Detection

A distributed computation has terminated when:
1. All processes are idle (passive)
2. No messages are in transit

A consistent snapshot showing both conditions proves termination.

---

## 6. Asynchronous Barrier Snapshotting (ABS) — Flink's Approach

Flink adapted Chandy-Lamport for **DAG-structured stream processing** topologies.

### Key Insight

In a DAG (no cycles), barriers flowing through the graph naturally separate
"pre-checkpoint" from "post-checkpoint" records — no need to record channel state
if you align barriers at operators.

### Algorithm

```
1. JobManager injects BARRIER(n) into all sources
2. Sources checkpoint their state, forward barrier downstream
3. When operator receives barrier(n) on ONE input:
   - BLOCK that input (buffer incoming records)
   - Wait for barrier(n) on ALL other inputs (ALIGNMENT)
4. When barrier(n) received on ALL inputs:
   - Checkpoint operator state
   - Forward barrier(n) downstream
   - Unblock all inputs
5. When sinks receive barrier(n):
   - Checkpoint complete → acknowledge to JobManager
```

### Barrier Alignment in a Stream DAG

```
    ┌────────┐       ┌────────┐       ┌────────┐
    │Source 1│──────►│        │       │        │
    │        │  ●●●●B│  Join  │──────►│  Sink  │
    └────────┘       │   Op   │       │        │
                     │        │       └────────┘
    ┌────────┐       │        │
    │Source 2│──────►│        │
    │        │  ●●B  │        │
    └────────┘       └────────┘

    ● = data record     B = barrier

    ═══════════════════════════════════════════════════════
    STEP 1: Barrier arrives from Source 1 first
    ═══════════════════════════════════════════════════════

    ┌────────┐       ┌────────────────┐       ┌────────┐
    │Source 1│──────►│ BLOCKED ░░░░░░ │──────►│        │
    │  [CP✓] │   B►  │                │       │  Sink  │
    └────────┘       │   Join Op      │       │        │
                     │   (waiting)    │       └────────┘
    ┌────────┐       │                │
    │Source 2│──●●──►│ still flowing  │
    │        │       │                │
    └────────┘       └────────────────┘

    Source 1's input is blocked. Records from Source 2 still processed.
    Join Op waits for barrier on Source 2's input.

    ═══════════════════════════════════════════════════════
    STEP 2: Barrier arrives from Source 2
    ═══════════════════════════════════════════════════════

    ┌────────┐       ┌────────────────┐       ┌────────┐
    │Source 1│──────►│                │       │        │
    │  [CP✓] │       │  Join Op [CP✓] │──B───►│  Sink  │
    └────────┘       │                │       │        │
                     │  Barriers      │       └────────┘
    ┌────────┐       │  aligned!      │
    │Source 2│──────►│                │
    │  [CP✓] │   B►  │  Unblock all   │
    └────────┘       └────────────────┘

    Both barriers received → checkpoint state → forward barrier → unblock
```

### Why No Channel State Recording?

Because of **barrier alignment**: when an operator checkpoints, ALL pre-barrier
records from all inputs have already been processed (they arrived before the
barrier on their respective channels). Post-barrier records haven't been
processed yet. So the operator state already reflects exactly the pre-barrier
input — no need to separately record channel contents.

### Limitation

Barrier alignment **blocks** one input while waiting for the other. Under
skew (one input much faster), this causes **backpressure** and latency spikes.

---

## 7. Unaligned Checkpoints (Flink 1.11+)

### Problem with Aligned Checkpoints

```
    Fast input:  ●●●●●●●●●B●●●●●●●●●  (barrier arrived early)
                          ↓ BLOCKED — records pile up
    Slow input:  ●●●●●●●●●●●●●●●●B●●  (barrier far behind)
                                       ↑ takes a long time

    Result: Checkpoint latency = time for slowest input to deliver barrier
            During this time, fast input is blocked → backpressure propagates
```

### Unaligned Checkpoint Approach

```
    On first barrier arrival (from any input):
    1. Immediately checkpoint operator state
    2. Snapshot all BUFFERED records between barriers on other inputs
       (these are "in-flight" data that becomes part of checkpoint)
    3. Forward barrier immediately (don't wait for alignment)
    4. Continue processing all inputs without blocking

    ┌─────────────────────────────────────────────┐
    │           Checkpoint Contents:               │
    │                                              │
    │  ┌─────────────┐  ┌──────────────────────┐  │
    │  │ Op State    │  │ In-flight buffers    │  │
    │  │ (at barrier │  │ (records between     │  │
    │  │  from fast  │  │  first barrier and   │  │
    │  │  input)     │  │  later barriers on   │  │
    │  │             │  │  other inputs)       │  │
    │  └─────────────┘  └──────────────────────┘  │
    └─────────────────────────────────────────────┘
```

### Trade-offs

| Property | Aligned | Unaligned |
|----------|---------|-----------|
| Checkpoint latency | High under skew | Low (constant) |
| Checkpoint size | Smaller (no buffers) | Larger (includes in-flight) |
| Processing stalls | Yes (blocked inputs) | No |
| Recovery time | Faster (less to replay) | Slower (more state to restore) |
| Complexity | Simpler | More complex |

---

## 8. Real-World Implementations

### Apache Flink

- Uses ABS (aligned) by default, unaligned optional
- Checkpoints stored in RocksDB (local) + S3/HDFS (durable)
- Incremental checkpoints: only SST files changed since last CP
- Checkpoint interval: typically 1-10 minutes
- Exactly-once with two-phase commit sinks (Kafka, JDBC)

### Apache Spark Structured Streaming

- Not Chandy-Lamport based — uses **micro-batch** model
- Each micro-batch is atomic; checkpoint = (batch ID, offsets, state)
- WAL (Write-Ahead Log) for driver metadata
- State stored in HDFS-compatible storage
- Trade-off: higher latency than Flink, simpler fault tolerance

### Google Dataflow / MillWheel

- **Upstream backup**: don't checkpoint all state; instead ensure all inputs
  are replayable and re-process from upstream on failure
- Combines with **strong productions** (idempotent writes with sequence IDs)
- Per-key checkpointing via Bigtable for low-watermark state
- No global barrier — each worker checkpoints independently

### Apache Kafka

- Consumer offsets as a "degenerate" snapshot: records the position in each
  partition, enabling replay
- Kafka Streams: changelog topics as incremental state snapshots
- Combined with Flink: source offsets included in Flink checkpoints

### CockroachDB

- MVCC provides **point-in-time consistent reads** across distributed ranges
- Each transaction reads from a snapshot at its read timestamp
- Uses hybrid logical clocks (HLC) for timestamp ordering
- Snapshot isolation: read set guaranteed consistent without locks

### VMware vMotion / Live Migration

- Iterative pre-copy: snapshot memory pages, transfer, re-snapshot dirty pages
- Converges when dirty rate < transfer rate
- Final phase: brief pause, transfer remaining dirty pages, resume at destination

### CRIU (Checkpoint/Restore in Userspace)

- Linux tool: freeze process, dump state to files, restore elsewhere
- Used in container migration (Podman, Docker experimental)
- Captures: memory, registers, file descriptors, network sockets, IPC

---

## 9. MVCC as Snapshot

Multi-Version Concurrency Control provides snapshot semantics at the database level:

```
    Version Timeline for Key "X":
    
    t=1     t=5      t=10     t=15     t=20
    ┌───┐   ┌───┐    ┌───┐    ┌───┐    ┌───┐
    │X=1│   │X=3│    │X=7│    │X=7│    │X=9│
    └───┘   └───┘    └───┘    └───┘    └───┘
    
    Transaction T starting at t=12 sees: X=7 (latest version ≤ t=12)
    Transaction T' starting at t=4 sees: X=1 (latest version ≤ t=4)
    
    Both run concurrently without blocking each other!
```

### Relation to Distributed Snapshots

| Distributed Snapshot | MVCC Snapshot |
|---------------------|---------------|
| Captures process + channel state | Captures data versions |
| Point-in-time cut across processes | Point-in-time cut across data |
| Uses markers/barriers | Uses timestamps/versions |
| For recovery/debugging | For transaction isolation |
| Consistency = causal | Consistency = serializable/SI |

In distributed databases (CockroachDB, Spanner, YugabyteDB), MVCC snapshots
must be **globally consistent** — requiring clock synchronization (TrueTime,
HLC) to agree on "what time is it" across nodes.

---

## 10. Challenges

### Non-FIFO Channels

Chandy-Lamport requires FIFO. Without it:

```
    P1 sends: [m1, MARKER, m2]
    Channel reorders: [m1, m2, MARKER]
    
    P2 receives m2 before MARKER → m2 incorrectly included in channel state
    But m2 was sent AFTER P1's snapshot → INCONSISTENCY
```

**Solutions:**
- Sequence numbers on all messages + markers
- Logical clocks (vector clocks) — include message in channel state only if
  its vector timestamp is "before" the sender's snapshot timestamp
- TCP guarantees FIFO in practice (most systems rely on this)

### Large State Size

- **Incremental snapshots:** Only store diff from previous snapshot (Flink RocksDB)
- **Copy-on-write:** Fork process, snapshot in background (Redis RDB)
- **LSM-based:** Snapshot = set of immutable SST files (trivial incremental)

### Snapshot Coordination Overhead

- Barriers cause backpressure (solved by unaligned checkpoints)
- Marker flooding in fully-connected topologies: O(n²) messages
- Solution: tree-based propagation, piggybacking on data messages

### Storage and Retention

- Snapshots can be gigabytes/terabytes for stateful streaming jobs
- Retention policy: keep last N checkpoints, garbage collect older ones
- Distributed storage required (S3, HDFS, GCS)
- Compression essential (snappy, zstd on state backends)

---

## 11. Architect's Guide

### When to Use Distributed Snapshots

| Scenario | Snapshot Approach |
|----------|-------------------|
| Stream processing exactly-once | ABS/Unaligned (Flink) |
| Database consistent backup | MVCC snapshot + export |
| Distributed debugging | Chandy-Lamport or vector-clock based |
| VM/container migration | Memory page snapshotting |
| Long-running computation resilience | Periodic coordinated checkpoints |
| Termination/deadlock detection | Classic Chandy-Lamport |

### Choosing Checkpoint Interval

```
    Recovery Time = Checkpoint_Interval / 2 (avg) + Replay_Time
    
    Checkpoint Cost = State_Size × Serialization_Overhead + Network_Transfer
    
    ┌─────────────────────────────────────────────────────────┐
    │                                                         │
    │   Total Cost                                            │
    │   ▲          ╲                                          │
    │   │           ╲  Recovery cost                          │
    │   │            ╲  (increases with                       │
    │   │             ╲  interval)                            │
    │   │              ╲         ╱                            │
    │   │               ╲      ╱                              │
    │   │                ╲   ╱  Checkpoint overhead           │
    │   │                 ╲╱   (decreases with interval)      │
    │   │                  ●                                  │
    │   │              OPTIMAL                                │
    │   │                                                     │
    │   └──────────────────────────────────────────────► Interval
    │         1s    10s    1m     5m    10m                    │
    └─────────────────────────────────────────────────────────┘
```

**Rules of thumb:**
- Stream processing: 30s–5min (Flink default: 10min)
- Database WAL checkpoints: every N MB of WAL
- Stateless operators: cheap checkpoints → shorter intervals
- Large keyed state (TB): longer intervals + incremental

### Recovery Strategies

1. **Full restart from checkpoint:** Simple, but slow for large state
2. **Local recovery:** Store checkpoint locally + remote backup; prefer local on restart
3. **Standby replicas:** Hot standby continuously applies same input; instant failover
4. **Regional recovery:** Only restart failed operators, not entire pipeline

### Design Checklist

```
□ Are channels FIFO? (TCP = yes, UDP = no → need sequence numbers)
□ Is input replayable? (Kafka = yes, push sources = need WAL)
□ State size per operator? (Determines checkpoint storage cost)
□ Acceptable recovery time? (Determines checkpoint interval)
□ Exactly-once needed? (Requires transactional sinks)
□ Topology: DAG or cycles? (DAG → ABS; cycles → full Chandy-Lamport)
□ Backpressure tolerance? (Low → unaligned checkpoints)
□ Incremental possible? (RocksDB state backend → yes)
□ Storage for checkpoints? (S3/HDFS/GCS with retention policy)
□ Checkpoint timeout configured? (Avoid infinite checkpoint hangs)
```

---

## Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DISTRIBUTED SNAPSHOTS                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Theory:  Chandy-Lamport (1985)                                     │
│           → FIFO channels + MARKER messages                         │
│           → Consistent cut guaranteed                               │
│           → O(E) messages, O(D) time                                │
│                                                                     │
│  Practice: ABS (Flink) / Unaligned / MVCC / Micro-batch             │
│           → Adapted for specific topologies & requirements          │
│           → Trade-offs: latency vs size vs complexity               │
│                                                                     │
│  Key Insight: Snapshot need not have "occurred" — it only needs     │
│              to be a REACHABLE consistent state                     │
│                                                                     │
│  Architect's Rule: Checkpoint interval = f(state_size,              │
│                    acceptable_recovery_time, throughput_overhead)    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## References

- Chandy, K.M. & Lamport, L. (1985). "Distributed Snapshots: Determining Global States of Distributed Systems"
- Carbone et al. (2015). "Lightweight Asynchronous Snapshots for Distributed Dataflows" (Flink ABS)
- Apache Flink Documentation: Stateful Stream Processing & Checkpointing
- Mattern, F. (1993). "Efficient Algorithms for Distributed Snapshots and Global Virtual Time Approximation"
