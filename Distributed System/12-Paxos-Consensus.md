# Paxos Consensus

## 1. The Consensus Problem

Consensus is the fundamental problem in distributed systems: getting a set of nodes to agree on a single value even when some nodes crash, messages are delayed, duplicated, or lost.

**Formal Definition:**
- **Agreement**: All correct processes decide the same value
- **Validity**: The decided value was proposed by some process
- **Termination**: All correct processes eventually decide

**FLP Impossibility Result (Fischer, Lynch, Paterson 1985):**

No deterministic consensus protocol can guarantee termination in an asynchronous system where even one process may crash. This means every practical consensus protocol must either:
1. Use timeouts (partial synchrony assumption) for liveness
2. Use randomization
3. Accept that termination is not guaranteed in all executions

Paxos guarantees **safety always** (never decides two different values) but relies on partial synchrony (eventual leader stability) for **liveness**.

```
┌─────────────────────────────────────────────────────────┐
│              THE CONSENSUS LANDSCAPE                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  FLP Impossibility: Cannot have all three:               │
│    ✓ Safety (agreement + validity)                       │
│    ✓ Liveness (termination)                              │
│    ✓ Fault tolerance in async system                     │
│                                                          │
│  Paxos choice: Always safe, live under partial synchrony │
│                                                          │
│  Failure model: Crash-stop (no Byzantine faults)         │
│  Network model: Asynchronous, unreliable (messages may   │
│                 be lost, delayed, reordered, duplicated)  │
│  Requires: Majority (2f+1 nodes tolerate f failures)     │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Paxos Roles

### Proposers
- Initiate the protocol by proposing values
- Generate globally unique, monotonically increasing proposal numbers
- Drive the two-phase protocol

### Acceptors
- The "memory" of the system — they vote on proposals
- A quorum (majority) of acceptors must participate for progress
- Persist their state to survive crashes

### Learners
- Learn which value has been chosen
- Typically the application layer that needs the decided value
- Can be notified by acceptors or a distinguished learner

### Role Multiplexing
In practice, a single physical node plays all three roles. A cluster of 5 nodes has 5 proposers, 5 acceptors, and 5 learners co-located.

```
┌─────────────────────────────────────────────────────────────────┐
│                     PAXOS ROLE INTERACTIONS                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────┐         ┌──────────┐         ┌──────────┐        │
│   │Proposer 1│         │Proposer 2│         │Proposer 3│        │
│   └────┬─────┘         └────┬─────┘         └────┬─────┘        │
│        │                     │                     │              │
│        │    Prepare/Accept   │                     │              │
│        ▼                     ▼                     ▼              │
│   ┌──────────┐         ┌──────────┐         ┌──────────┐        │
│   │Acceptor 1│         │Acceptor 2│         │Acceptor 3│        │
│   └────┬─────┘         └────┬─────┘         └────┬─────┘        │
│        │                     │                     │              │
│        │   Accepted/Learn    │                     │              │
│        ▼                     ▼                     ▼              │
│   ┌──────────┐         ┌──────────┐         ┌──────────┐        │
│   │ Learner 1│         │ Learner 2│         │ Learner 3│        │
│   └──────────┘         └──────────┘         └──────────┘        │
│                                                                  │
│   Quorum = majority of acceptors (2 out of 3 here)              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Proposal Number Generation:**
Each proposer uses a unique proposal number scheme, e.g., `(round, server_id)` where:
- `round` is a local counter incremented each time
- `server_id` provides uniqueness across proposers
- Numbers are compared lexicographically: (round, id)

---

## 3. Basic Paxos (Single-Decree)

Basic Paxos decides a **single** value. It operates in two phases, each with two sub-steps.

### Phase 1a: Prepare

The proposer selects a proposal number `n` (higher than any it has used before) and sends `Prepare(n)` to a majority of acceptors.

**Purpose:** "I want to make a proposal numbered n. Has anyone already accepted something?"

### Phase 1b: Promise

Each acceptor receiving `Prepare(n)`:
- If `n` > highest prepare number it has responded to:
  - Updates `minProposal = n`
  - Responds with `Promise(n, acceptedProposal, acceptedValue)` — the highest-numbered proposal it has already accepted (if any)
  - **Promise:** "I will not accept any proposal numbered less than n"
- Otherwise: ignores or sends `Nack(n)`

### Phase 2a: Accept

Once the proposer receives Promise responses from a **majority** of acceptors:
- If any acceptor reported an already-accepted value, the proposer **must** use the value from the highest-numbered accepted proposal
- If no acceptor reported an accepted value, the proposer uses its own value
- Sends `Accept(n, v)` to a majority of acceptors

**This is the key safety mechanism** — by adopting the highest accepted value, the proposer preserves any value that might already be chosen.

### Phase 2b: Accepted

Each acceptor receiving `Accept(n, v)`:
- If `n >= minProposal` (no higher prepare has been promised):
  - Sets `acceptedProposal = n`, `acceptedValue = v`
  - Responds `Accepted(n, v)` to proposer and all learners
- Otherwise: ignores (or Nacks)

**Value is chosen** when a majority of acceptors have accepted the same proposal number.

### Complete Message Flow

```
    Proposer P              Acceptors (A1, A2, A3)           Learner L
        │                        │    │    │                     │
        │   Phase 1a: Prepare(n=1)                               │
        │───────────────────────►│    │    │                     │
        │───────────────────────►│────►    │                     │
        │───────────────────────►│────►────►                     │
        │                        │    │    │                     │
        │   Phase 1b: Promise(1, null, null)                     │
        │◄───────────────────────│    │    │                     │
        │◄────────────────────────────│    │                     │
        │◄─────────────────────────────────│                     │
        │                        │    │    │                     │
        │  [Majority promised — no prior accepted value]         │
        │  [Proposer uses its own value v="X"]                   │
        │                        │    │    │                     │
        │   Phase 2a: Accept(n=1, v="X")                         │
        │───────────────────────►│    │    │                     │
        │───────────────────────►│────►    │                     │
        │───────────────────────►│────►────►                     │
        │                        │    │    │                     │
        │   Phase 2b: Accepted(1, "X")                           │
        │◄───────────────────────│    │    │                     │
        │◄────────────────────────────│    │                     │
        │◄─────────────────────────────────│                     │
        │                        │    │    │                     │
        │                        │    │    │──────►│             │
        │                        │    │    │  Learned: "X"       │
        │                        │    │    │                     │
     ───┴────────────────────────┴────┴────┴──────────────┴──────
     TIME ──────────────────────────────────────────────────────►
```

### Scenario: Proposer Must Adopt Prior Value

```
    Proposer P1 (value="A")     Proposer P2 (value="B")     Acceptors (A1, A2, A3)
        │                            │                        │    │    │
        │  Prepare(n=1)             │                        │    │    │
        │───────────────────────────┼───────────────────────►│    │    │
        │───────────────────────────┼───────────────────────►│────►    │
        │                            │                        │    │    │
        │  Promise(1, -, -)         │                        │    │    │
        │◄───────────────────────────┼───────────────────────│    │    │
        │◄───────────────────────────┼────────────────────────────│    │
        │                            │                        │    │    │
        │  Accept(1, "A") → A1, A2  │                        │    │    │
        │───────────────────────────┼───────────────────────►│    │    │
        │───────────────────────────┼───────────────────────►│────►    │
        │                            │                        │    │    │
        │  Accepted(1,"A") by A1,A2 │   ← VALUE "A" CHOSEN  │    │    │
        │                            │                        │    │    │
        │                            │  Prepare(n=2)         │    │    │
        │                            │──────────────────────►│────►    │
        │                            │──────────────────────►│────►────►
        │                            │                        │    │    │
        │                            │  Promise(2, 1, "A")   │    │    │
        │                            │◄──────────────────────│────│    │
        │                            │  Promise(2, 1, "A")   │    │    │
        │                            │◄───────────────────────────│    │
        │                            │                        │    │    │
        │                            │  [Must use "A" not "B"!]   │    │
        │                            │  Accept(2, "A")       │    │    │
        │                            │──────────────────────►│────►────►
        │                            │                        │    │    │
```

**P2 wanted "B" but MUST propose "A"** because it learned that "A" was accepted in proposal 1. This is how safety is preserved.

### Safety Proof Sketch

**Theorem:** At most one value can be chosen.

**Proof intuition:**
1. A value is chosen only when accepted by a majority of acceptors for the same proposal number
2. Any two majorities overlap in at least one acceptor
3. If value v is chosen with proposal n, then any higher proposal n' must also propose v because:
   - The proposer of n' must contact a majority in Phase 1
   - At least one acceptor in that majority accepted (n, v)
   - The proposer adopts the highest-numbered accepted value, which is v (or something chosen even later, which by induction is also v)

**Formal invariant:** If proposal (n, v) is issued, then there exists a majority S such that either:
- No acceptor in S has accepted a proposal numbered less than n, OR
- v is the value of the highest-numbered proposal accepted by any acceptor in S

---

## 4. Dueling Proposers (Livelock)

Basic Paxos has no liveness guarantee without additional mechanism. Two proposers can perpetually preempt each other:

```
    Proposer P1                     Proposer P2                   Acceptors
        │                               │                         │
        │  Prepare(n=1)                │                         │
        │──────────────────────────────┼────────────────────────►│
        │                               │                         │
        │  Promise(1)                  │                         │
        │◄─────────────────────────────┼────────────────────────│
        │                               │                         │
        │                               │  Prepare(n=2)          │
        │                               │──────────────────────►│
        │                               │                         │
        │                               │  Promise(2)            │
        │                               │◄──────────────────────│
        │                               │                         │
        │  Accept(1, v1)               │                         │
        │──────────────────────────────┼────────────────────────►│
        │                               │                         │
        │  REJECTED! (promised n=2)    │                         │
        │◄─────────────────────────────┼────────────────────────│
        │                               │                         │
        │  Prepare(n=3)                │                         │
        │──────────────────────────────┼────────────────────────►│
        │                               │                         │
        │  Promise(3)                  │                         │
        │◄─────────────────────────────┼────────────────────────│
        │                               │                         │
        │                               │  Accept(2, v2)         │
        │                               │──────────────────────►│
        │                               │                         │
        │                               │  REJECTED! (n=3)       │
        │                               │◄──────────────────────│
        │                               │                         │
        │                               │  Prepare(n=4)          │
        │  ... INFINITE LOOP ...        │  ...                   │
        ▼                               ▼                         ▼
```

### Solutions

1. **Distinguished Proposer (Leader Election):**
   - Elect a single leader; only the leader proposes
   - If the leader is stable, progress is guaranteed (Phase 2 always succeeds)
   - Leader failure triggers new election (temporary unavailability, not unsafety)

2. **Exponential Backoff:**
   - After being preempted, wait a random, exponentially increasing delay before retrying
   - Probabilistically ensures one proposer "wins"

3. **Leader Lease:**
   - Current leader holds a time-bounded lease
   - Other proposers defer during the lease period
   - Combines leader stability with bounded unavailability on failure

---

## 5. Multi-Paxos

Basic Paxos decides one value. Real systems need to decide a **sequence** of values (a replicated log). Multi-Paxos optimizes this.

### Key Insight: Stable Leader Optimization

If the same proposer (leader) drives consecutive instances:
- Phase 1 (Prepare/Promise) can be done **once** for many instances
- Subsequent decisions only need Phase 2 (Accept/Accepted) — **one round trip**

### Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        MULTI-PAXOS LOG                              │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Log Slot:  │  1  │  2  │  3  │  4  │  5  │  6  │  7  │  ...     │
│  Value:     │ "A" │ "B" │ "C" │ "D" │  ?  │  ?  │  ?  │          │
│  Status:    │chosen│chosen│chosen│chosen│pending│  │  │           │
│                                                                     │
│  Each slot is an independent Paxos instance                        │
│  But we amortize Phase 1 across all slots                          │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

### Multi-Paxos Message Flow (Steady State)

```
    Leader                    Acceptors (A1, A2, A3)           Learners
        │                        │    │    │                     │
        │  ══════ INITIAL PREPARE (done once) ══════             │
        │                        │    │    │                     │
        │  Prepare(ballot=5, slots=∞)                            │
        │───────────────────────►│    │    │                     │
        │───────────────────────►│────►    │                     │
        │───────────────────────►│────►────►                     │
        │                        │    │    │                     │
        │  Promise(5, prior accepted values for all slots)       │
        │◄───────────────────────│    │    │                     │
        │◄────────────────────────────│    │                     │
        │◄─────────────────────────────────│                     │
        │                        │    │    │                     │
        │  ══════ STEADY STATE (Phase 2 only) ══════             │
        │                        │    │    │                     │
        │  Accept(ballot=5, slot=1, v="A")                       │
        │───────────────────────►│    │    │                     │
        │───────────────────────►│────►    │                     │
        │───────────────────────►│────►────►                     │
        │  Accepted(5, slot=1)   │    │    │                     │
        │◄───────────────────────│    │    │──────►│  Learned    │
        │◄────────────────────────────│    │──────►│  slot 1     │
        │                        │    │    │                     │
        │  Accept(ballot=5, slot=2, v="B")                       │
        │───────────────────────►│    │    │                     │
        │───────────────────────►│────►    │                     │
        │───────────────────────►│────►────►                     │
        │  Accepted(5, slot=2)   │    │    │                     │
        │◄───────────────────────│    │    │──────►│  Learned    │
        │◄────────────────────────────│    │──────►│  slot 2     │
        │                        │    │    │                     │
        │  Accept(ballot=5, slot=3, v="C")   ← Pipelined!       │
        │───────────────────────►│    │    │                     │
        │  ... continues with 1 RTT per decision ...             │
        │                        │    │    │                     │
```

### Message Complexity Comparison

| Protocol | Messages per decision | Round trips |
|----------|----------------------|-------------|
| Basic Paxos | 4f+4 (f=failures tolerated) | 2 RTT |
| Multi-Paxos (stable leader) | 2f+2 | 1 RTT |
| Multi-Paxos (with distinguished learner) | f+2 | 1 RTT |

### Leader Election and Failover

```
┌──────────────────────────────────────────────────────────────┐
│                    LEADER FAILOVER                             │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Time ─────────────────────────────────────────────────►      │
│                                                               │
│  Leader 1: ████████████████████████░░░░░░  (crashes)         │
│                    Phase2 Phase2 Phase2                        │
│                                                               │
│  Leader 2:                          ░░░████████████████       │
│                                     ↑                         │
│                              Detects failure,                 │
│                              runs Phase 1 for                 │
│                              all pending slots,               │
│                              then resumes Phase 2             │
│                                                               │
│  Gap: brief unavailability (seconds), never inconsistency    │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Handling Gaps in the Log

When a new leader takes over, some log slots may have been partially decided. The new leader:
1. Runs Phase 1 for all slots from its first unchosen slot onward
2. For slots where a value was already accepted, re-proposes that value
3. For truly empty slots, can propose a no-op

---

## 6. Paxos Variants

### Fast Paxos (Lamport, 2006)

Reduces latency to **2 message delays** (instead of 4) in the common case by having clients send directly to acceptors.

```
    Client         Leader          Acceptors (need ⌊3f/2⌋+1 for fast quorum)
      │              │               │   │   │   │
      │  request     │               │   │   │   │
      │─────────────►│               │   │   │   │
      │              │  Any(v)       │   │   │   │
      │──────────────┼──────────────►│   │   │   │
      │──────────────┼──────────────►│───►   │   │
      │──────────────┼──────────────►│───►───►   │
      │──────────────┼──────────────►│───►───►───►
      │              │               │   │   │   │
      │  Accepted    │               │   │   │   │
      │◄─────────────┼───────────────│   │   │   │
      │◄─────────────┼───────────────────│   │   │
      │◄─────────────┼───────────────────────│   │
      │              │               │   │   │   │
      │  2 message delays (client→acceptors→client)
```

**Trade-offs:**
- Requires larger quorums (3f+1 acceptors instead of 2f+1, or ⌊3f/2⌋+1 fast quorum)
- Collision recovery falls back to Classic Paxos (adds latency)
- Best for low-contention workloads

### Cheap Paxos (Lamport, 2004)

Uses **f+1 main acceptors** plus **f auxiliary acceptors** (instead of 2f+1 main):
- Normal operation: f+1 main acceptors handle requests
- On failure: auxiliary acceptors activate to reconfigure
- Saves hardware in steady state

### Flexible Paxos (Howard, Malkhi, Spiegelman, 2016)

**Key insight:** Phase 1 quorum and Phase 2 quorum don't both need to be majorities. They only need to **intersect**.

```
Requirements:
  Q1 ∩ Q2 ≠ ∅   (Phase 1 quorum intersects Phase 2 quorum)

Examples with 10 acceptors:
  Classic:    Q1 = 6, Q2 = 6   (both majorities)
  Flexible:   Q1 = 9, Q2 = 2   (fast writes, slow recovery)
  Flexible:   Q1 = 3, Q2 = 8   (fast recovery, slow writes)
```

This is powerful for Multi-Paxos: since Phase 1 happens rarely (only on leader change), make Q1 large and Q2 small for faster steady-state commits.

### EPaxos (Egalitarian Paxos — Moraru, Andersen, Kaminsky, 2013)

No designated leader. Any replica can commit in **1 RTT** for non-conflicting commands.

```
┌───────────────────────────────────────────────────────────────┐
│                      EPAXOS FAST PATH                           │
├───────────────────────────────────────────────────────────────┤
│                                                                │
│  Replica R1 (command leader for cmd A):                        │
│                                                                │
│    R1 ──── PreAccept(A) ──── ► R2, R3, R4, R5                │
│    R1 ◄─── PreAcceptOK ─────── R2, R3, R4, R5                │
│                                                                │
│    If all replies agree (no conflicts): COMMIT in 1 RTT        │
│    If conflicts detected: run Paxos-Accept phase (2 RTT)       │
│                                                                │
│  Benefits:                                                     │
│  • No leader bottleneck — any replica handles any command      │
│  • Optimal latency (1 RTT) when commands don't conflict        │
│  • Better load distribution                                    │
│  • Tolerates slow replicas (uses fast quorum of f+⌊f/2⌋+1)   │
│                                                                │
│  Drawbacks:                                                    │
│  • Complex dependency tracking and execution ordering          │
│  • 2 RTT on conflicts (worse than Multi-Paxos leader)         │
│  • Significantly harder to implement correctly                 │
│                                                                │
└───────────────────────────────────────────────────────────────┘
```

---

## 7. Correctness Properties

### Safety (Always Holds)

**Agreement:** Only a single value can be chosen for any given instance.

**Validity:** Only a value that was proposed can be chosen (no fabrication).

These hold regardless of:
- Arbitrary message delays/losses/reordering
- Any number of concurrent proposers
- Any minority of acceptor crashes

### Liveness (Conditional)

**Termination:** Eventually some value is chosen — BUT only if:
- A stable leader exists (no dueling proposers)
- A majority of acceptors are alive and reachable
- Messages are eventually delivered (partial synchrony)

Without a stable leader, livelock is possible (see Section 4).

### Formal Specification

Lamport's TLA+ specification provides a machine-checkable proof:

```
Invariants (TLA+):
  TypeOK ≜ 
    ∧ maxBal ∈ [Acceptor → Ballot ∪ {-1}]
    ∧ maxVBal ∈ [Acceptor → Ballot ∪ {-1}]  
    ∧ maxVal ∈ [Acceptor → Value ∪ {None}]

  Chosen(v) ≜ ∃ b ∈ Ballot, Q ∈ Quorum :
    ∀ a ∈ Q : maxVBal[a] ≥ b ∧ maxVal[a] = v

  Safety ≜ ∀ v1, v2 ∈ Value :
    Chosen(v1) ∧ Chosen(v2) ⇒ v1 = v2
```

Reference: `Paxos.tla` in Lamport's TLA+ examples repository.

---

## 8. Real-World Implementations

### Google Chubby (2006)

- **Purpose:** Distributed lock service, name service, small-file storage
- **Architecture:** 5-node Paxos cell; one elected master handles all reads/writes
- **Paper:** "The Chubby Lock Service for Loosely-Coupled Distributed Systems" (Burrows, 2006)
- **Lessons from "Paxos Made Live" (Chandra, Griesemer, Redstone, 2007):**
  - 1000s of lines of code beyond basic algorithm
  - Master leases for read optimization
  - Disk corruption handling, snapshot/replay for truncation
  - Group membership changes are the hardest part

### Google Spanner (2012)

- **Purpose:** Globally-distributed SQL database
- **Multi-Paxos usage:** Each shard (split) is replicated via Multi-Paxos
- **Innovation:** TrueTime API enables externally-consistent distributed transactions across Paxos groups
- **Leader leases:** 10-second leases, leader serves reads locally

### Google Megastore (2011)

- **Purpose:** Structured storage for Google App Engine
- **Paxos per entity group:** Each entity group is a mini Paxos instance
- **Optimistic fast writes** with coordinator-based conflict detection
- **Largely superseded by Spanner**

### Apache ZooKeeper (ZAB Protocol)

- **ZAB (ZooKeeper Atomic Broadcast):** Paxos-like but designed for primary-backup with total ordering
- **Differences from Paxos:**
  - Requires FIFO ordering of proposals from a leader
  - Recovery protocol explicitly handles leader's in-flight proposals
  - Designed for the replicated state machine use case (not single-value consensus)
- **Usage:** Kafka (pre-KRaft), HBase, HDFS NameNode HA, Solr

### Microsoft Azure Storage

- **Paxos for partition primary election** — selects which replica serves a partition
- **Stream layer:** Append-only extent-based replication (chain replication, not Paxos)
- **Paxos scope:** Limited to failure detection and leader election

### Delos (Meta/Facebook, 2020)

- **Virtual consensus:** A shared log abstraction where the consensus protocol is pluggable
- **Innovation:** Can migrate between different Paxos implementations without downtime
- **VirtualLog:** Chains multiple physical logs, each running different consensus protocols
- **Used by:** Meta's control plane services

---

## 9. Why Paxos is Hard to Implement

### The Gap Between Theory and Practice

Lamport's "Paxos Made Simple" describes single-decree Paxos in ~2 pages. A production system needs:

```
┌─────────────────────────────────────────────────────────────┐
│          FROM SINGLE-DECREE TO PRODUCTION SYSTEM             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Basic Paxos (paper)           Production system needs:      │
│  ─────────────────────         ─────────────────────────     │
│  • One value                   • Log of values (Multi-Paxos) │
│  • Static membership           • Dynamic membership changes  │
│  • No optimization             • Batching & pipelining       │
│  • No persistence detail       • WAL, fsync, snapshots       │
│  • No client interaction       • Exactly-once semantics      │
│  • No state transfer           • Snapshot + catch-up         │
│  • No leader election detail   • Lease-based leader          │
│  • No reconfiguration          • Joint consensus / ISR       │
│                                                              │
│  Result: 1000s of lines of subtle, hard-to-test code         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Specific Challenges

**1. Membership Changes (Reconfiguration):**
- Cannot simply add/remove nodes — quorum definition changes
- Must be done via a Paxos decision itself (consensus on the configuration)
- α-based reconfiguration: new config takes effect after α slots

**2. Persistent Storage:**
- Acceptors must persist `minProposal`, `acceptedProposal`, `acceptedValue` before responding
- Requires fsync (expensive!) — must batch to amortize
- Corruption recovery needs checksums and careful replay

**3. Log Compaction:**
- Log grows unboundedly; need snapshots
- Slow followers need state transfer (snapshot + replay)
- Must track which slots are safe to garbage collect

**4. Client Semantics:**
- Client retries can cause duplicate execution
- Need request deduplication (client ID + sequence number)
- Exactly-once requires idempotency or dedup table

### Paxos vs Raft

| Dimension | Paxos | Raft |
|-----------|-------|------|
| Specification | Consensus on single value; multi-paxos loosely specified | Complete replicated log protocol |
| Understandability | Famously hard to understand | Designed for pedagogy |
| Leader election | Unspecified (left to implementation) | Explicit term-based election |
| Log structure | Gaps allowed in log | No gaps (leader has all committed entries) |
| Membership change | Various approaches, no standard | Joint consensus or single-server changes |
| Formal proof | TLA+ specification | TLA+ specification |
| Performance ceiling | Higher (more optimization latitude) | Slightly lower (stronger invariants constrain) |
| Real-world usage | Google, Meta, Azure | etcd, CockroachDB, TiKV, Consul |

**When to choose Raft:** Most new systems. Easier to implement correctly, well-specified, abundant reference implementations.

**When to choose Paxos:** When you need flexibility (EPaxos, Flexible Paxos), or are building on existing Paxos infrastructure.

---

## 10. Performance Analysis

### Message Complexity

```
┌────────────────────────────────────────────────────────────────┐
│           MESSAGES PER CONSENSUS DECISION                       │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Basic Paxos:                                                   │
│    Phase 1: Proposer → N acceptors + N responses = 2N          │
│    Phase 2: Proposer → N acceptors + N responses = 2N          │
│    Total: 4N messages (or 4f+4 with majority quorums)          │
│    Latency: 2 RTT                                              │
│                                                                 │
│  Multi-Paxos (stable leader):                                   │
│    Phase 2 only: Leader → N acceptors + N responses = 2N       │
│    Total: 2N messages per decision                             │
│    Latency: 1 RTT                                              │
│                                                                 │
│  Multi-Paxos (distinguished learner):                           │
│    Leader → N acceptors, majority → leader = N + f+1           │
│    Total: ~1.5N messages per decision                          │
│    Latency: 1 RTT                                              │
│                                                                 │
│  EPaxos (no conflicts):                                         │
│    PreAccept + PreAcceptOK = 2f+2 messages                     │
│    Latency: 1 RTT                                              │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### Latency Breakdown

| Scenario | Network RTTs | Disk Syncs |
|----------|-------------|------------|
| Basic Paxos | 2 | 2 (one per phase, acceptor-side) |
| Multi-Paxos (stable leader) | 1 | 1 (acceptor on Accept) |
| Multi-Paxos + batching | 1 | 1 (amortized over batch) |
| Fast Paxos (no conflict) | 1 (client→acceptor→client) | 1 |

### Throughput Optimizations

**Batching:**
- Accumulate multiple client requests, commit them as one Paxos instance
- Amortizes disk sync and message overhead
- Typical batch window: 1-5ms or max-batch-size

**Pipelining:**
- Don't wait for slot N to commit before proposing slot N+1
- Leader sends Accept for slots N, N+1, N+2 concurrently
- Window size W allows W concurrent in-flight slots
- Throughput ≈ W / RTT (bounded by disk/network bandwidth)

**Parallel Acceptors (read optimization):**
- With leader leases, reads can be served locally without consensus
- Lease duration: typically 5-10 seconds
- Stale reads allowed for some workloads (timeline consistency)

```
Throughput model (simplified):

  T = min(
    batch_size / RTT,            ← network-bound
    batch_size / fsync_latency,  ← disk-bound
    pipeline_window / RTT,       ← concurrency-bound
    network_bandwidth / msg_size ← bandwidth-bound
  )

  Typical production numbers (3-node, same datacenter):
    RTT ≈ 0.5ms, fsync ≈ 1ms, batch = 100
    Throughput ≈ 100K ops/sec (batched, pipelined)
```

---

## 11. Architect's Guide

### Decision Framework

```
┌─────────────────────────────────────────────────────────────────┐
│              WHEN TO USE WHAT                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Need replicated log / state machine?                            │
│    ├─ New system, want simplicity ──────────► Raft (etcd, etc.) │
│    ├─ Need leaderless / geo-distributed ────► EPaxos / CRDTs    │
│    ├─ Existing Paxos infra ─────────────────► Multi-Paxos       │
│    └─ Maximum flexibility in quorums ───────► Flexible Paxos    │
│                                                                  │
│  Need leader election only?                                      │
│    └─ Use existing service (ZooKeeper, etcd, Consul)            │
│                                                                  │
│  Need distributed lock?                                          │
│    └─ Chubby/ZooKeeper pattern (Paxos/ZAB underneath)           │
│                                                                  │
│  Multi-datacenter?                                               │
│    ├─ Linearizable ─────► Paxos/Raft across DCs (high latency)  │
│    ├─ Per-shard Paxos ──► Spanner model                         │
│    └─ Eventual consistency OK ──► CRDTs, last-writer-wins       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation Recommendations

1. **Don't implement Paxos yourself** unless you have exceptional reason. Use etcd, ZooKeeper, or a tested library.

2. **If you must implement:** Start from a TLA+ spec. Model-check your implementation. Use Jepsen-style testing.

3. **Performance priorities:**
   - Batch aggressively (most impactful single optimization)
   - Pipeline proposals (second most impactful)
   - Minimize fsync (group commit, O_DIRECT + checksums)
   - Use leader leases for reads

4. **Monitoring essentials:**
   - Leader stability (elections/hour)
   - Proposal latency (p50, p99, p999)
   - Log divergence (how far behind are followers)
   - Disk sync latency

5. **Testing requirements:**
   - Jepsen-style linearizability checker
   - Network partition injection
   - Disk failure simulation
   - Clock skew testing (for lease-based optimizations)

### Key Papers

| Paper | Year | Key Contribution |
|-------|------|-----------------|
| "The Part-Time Parliament" (Lamport) | 1998 | Original Paxos |
| "Paxos Made Simple" (Lamport) | 2001 | Simplified explanation |
| "Paxos Made Live" (Chandra et al.) | 2007 | Production lessons (Chubby) |
| "Paxos Made Moderately Complex" (van Renesse, Altinbuken) | 2015 | Complete Multi-Paxos |
| "In Search of an Understandable Consensus Algorithm" (Ongaro, Ousterhout) | 2014 | Raft |
| "Flexible Paxos" (Howard et al.) | 2016 | Non-intersecting quorum relaxation |
| "There Is More Consensus in Egalitarian Parliaments" (Moraru et al.) | 2013 | EPaxos |
| "Virtual Consensus in Delos" (Balakrishnan et al.) | 2020 | Pluggable consensus |

---

## Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    PAXOS AT A GLANCE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  What:     Agreement on a single value despite crashes           │
│  How:      Two-phase protocol with majority quorums              │
│  Safety:   Always (even under async, partitions)                 │
│  Liveness: Only with stable leader + majority alive              │
│                                                                  │
│  Basic Paxos:  2 RTT, decides one value                         │
│  Multi-Paxos:  1 RTT (amortized), decides sequence              │
│                                                                  │
│  Production:   Batch + Pipeline + Lease = high throughput        │
│  Reality:      Use Raft unless you have specific Paxos needs     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
