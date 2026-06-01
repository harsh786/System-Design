# CRDTs — Conflict-free Replicated Data Types

## 1. Problem Statement

In distributed systems, we face a fundamental tension: **strong consistency** requires coordination (consensus, locking, leader-based replication), which sacrifices availability and latency. CAP theorem forces a choice during partitions.

**The core question**: Can replicas accept writes independently, with no coordination, and still guarantee convergence to the same state?

```
┌─────────────────────────────────────────────────────────────────────┐
│                    THE COORDINATION DILEMMA                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Strong Consistency          vs.         Availability              │
│   ┌──────────────┐                       ┌──────────────┐          │
│   │ All replicas │                       │ Every replica│          │
│   │ agree before │                       │ can accept   │          │
│   │ responding   │                       │ writes always│          │
│   └──────────────┘                       └──────────────┘          │
│         │                                       │                   │
│         ▼                                       ▼                   │
│   High latency,                          Divergent state,           │
│   unavailable during                     conflicts on merge         │
│   partitions                                                        │
│                                                                     │
│                    ┌──────────────────┐                              │
│                    │      CRDTs       │                              │
│                    │                  │                              │
│                    │ Strong Eventual  │                              │
│                    │ Consistency:     │                              │
│                    │ No coordination  │                              │
│                    │ + Guaranteed     │                              │
│                    │   convergence    │                              │
│                    └──────────────────┘                              │
└─────────────────────────────────────────────────────────────────────┘
```

**Strong Eventual Consistency (SEC)** guarantees:
- **Eventual delivery**: Every update delivered to one correct replica is eventually delivered to all.
- **Convergence**: Correct replicas that have received the same set of updates are in the same state — **immediately**, without further communication.
- **Termination**: All executions terminate (no blocking, no rollback).

CRDTs achieve SEC by designing data types whose operations are mathematically guaranteed to converge regardless of ordering or duplication.

---

## 2. Mathematical Foundation

### 2.1 Join-Semilattice

A **join-semilattice** is a partially ordered set `(S, ≤)` where every two elements `a, b ∈ S` have a **least upper bound** (LUB), called the **join**: `a ⊔ b`.

```
                    Lattice Structure (Set union example)
                    
                         {a, b, c}           ← top (supremum)
                        /    |    \
                   {a,b}   {a,c}   {b,c}
                    / \     / \     / \
                  {a}  {b} {a} {c} {b} {c}
                    \   |   |   |   |   /
                     \  |   |   |   |  /
                      \ |   |   |   | /
                         {}              ← bottom (infimum)

    Join operation (⊔) = set union
    {a} ⊔ {b} = {a, b}
    {a, b} ⊔ {b, c} = {a, b, c}
```

### 2.2 Properties of the Join Operation

For CRDTs to guarantee convergence, the merge/join operation must satisfy:

| Property | Definition | Why It Matters |
|----------|-----------|----------------|
| **Commutativity** | `a ⊔ b = b ⊔ a` | Order of receiving updates doesn't matter |
| **Associativity** | `(a ⊔ b) ⊔ c = a ⊔ (b ⊔ c)` | Grouping of merges doesn't matter |
| **Idempotency** | `a ⊔ a = a` | Duplicate delivery is harmless |

### 2.3 Monotonically Increasing State

A CRDT's state only moves "upward" in the lattice:

```
    State Space (Lattice)
    
    ─────────────────────────────────────────── time →
    
    s₀  →  s₁  →  s₂  →  s₃  →  ...
    
    Where: s₀ ≤ s₁ ≤ s₂ ≤ s₃ ≤ ...
    
    States can NEVER move downward.
    Each update or merge produces a state ≥ current state.
```

### 2.4 Why These Properties Guarantee Convergence

**Theorem**: If all replicas start at the same initial state and receive the same set of updates (in any order, with any duplicates), they will converge to the same final state.

**Proof sketch**:
1. **Commutativity** → any permutation of operations yields same result
2. **Associativity** → any grouping/batching yields same result
3. **Idempotency** → any re-delivery yields same result
4. **Monotonicity** → state always advances toward the LUB of all updates

```
    Replica A:  s₀ ⊔ op1 ⊔ op2 ⊔ op3 = final_state
    Replica B:  s₀ ⊔ op3 ⊔ op1 ⊔ op2 = final_state    (commutativity)
    Replica C:  s₀ ⊔ op1 ⊔ op1 ⊔ op2 ⊔ op3 = final_state  (idempotency)
    
    All three converge to the SAME final_state. ∎
```

---

## 3. Two Families of CRDTs

### 3.1 CmRDTs (Commutative Replicated Data Types) — Operation-Based

- Each replica broadcasts the **operation** (e.g., "increment by 1")
- Receiving replicas apply the operation locally
- **Requirement**: Reliable causal broadcast (exactly-once, causal order)
- Operations must be commutative (but NOT necessarily idempotent)

### 3.2 CvRDTs (Convergent Replicated Data Types) — State-Based

- Each replica periodically sends its **full state** to other replicas
- Receiving replicas **merge** the incoming state with their local state
- **Requirement**: Merge function must form a join-semilattice (commutative, associative, idempotent)
- Tolerates duplicate delivery, out-of-order delivery, message loss (just resend state)

### 3.3 Comparison

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              Operation-Based (CmRDT)       vs.     State-Based (CvRDT)      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Node A          Node B                  Node A          Node B            │
│   ┌─────┐        ┌─────┐                 ┌─────┐        ┌─────┐           │
│   │ s=5 │        │ s=5 │                 │ s=5 │        │ s=5 │           │
│   └──┬──┘        └──┬──┘                 └──┬──┘        └──┬──┘           │
│      │               │                      │               │              │
│      │ inc(1)        │                      │ inc(1)        │              │
│      ▼               │                      ▼               │              │
│   ┌─────┐           │                   ┌─────┐           │              │
│   │ s=6 │           │                   │ s=6 │           │              │
│   └──┬──┘           │                   └──┬──┘           │              │
│      │               │                      │               │              │
│      │──op:"inc(1)"─▶│                      │──state:{6}──▶│              │
│      │               ▼                      │               ▼              │
│      │            ┌─────┐                   │            ┌─────┐          │
│      │            │ s=6 │                   │            │merge │          │
│      │            └─────┘                   │            │(5,6) │          │
│      │                                      │            │ = 6  │          │
│      │                                      │            └─────┘          │
│                                                                             │
│   Ships: small ops                        Ships: full state                 │
│   Needs: exactly-once,                    Needs: eventual delivery          │
│          causal delivery                  Tolerates: duplicates,            │
│   Bandwidth: LOW                                    reordering             │
│                                           Bandwidth: HIGH                   │
│                                           (but can use delta-state)         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.4 Trade-offs

| Dimension | CmRDT (Op-based) | CvRDT (State-based) |
|-----------|-------------------|----------------------|
| **Bandwidth** | Low (small ops) | High (full state) |
| **Delivery guarantee** | Exactly-once, causal | At-least-once (any) |
| **Infrastructure** | Needs reliable broadcast | Simple gossip works |
| **Duplicate tolerance** | NO — duplicates corrupt state | YES — merge is idempotent |
| **Partition recovery** | Must replay missed ops in order | Just exchange latest state |
| **Implementation complexity** | Higher (delivery guarantees) | Lower (merge function) |

---

## 4. Fundamental CRDT Types

### 4.a G-Counter (Grow-only Counter)

A counter that can only be incremented. Each node maintains its own entry in a vector.

**Structure**: Map of `{node_id → count}`

**Operations**:
- `increment(node_i)`: `counter[i] += 1`
- `value()`: `Σ counter[i]` for all i
- `merge(a, b)`: `∀i: result[i] = max(a[i], b[i])`

```
┌──────────────────────────────────────────────────────────────────────┐
│                    G-Counter: Concurrent Increments                   │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Time ──────────────────────────────────────────────────────▶       │
│                                                                      │
│   Node A: [A:0, B:0, C:0]                                           │
│              │                                                       │
│              │ inc()                                                  │
│              ▼                                                        │
│           [A:1, B:0, C:0]                                            │
│              │                                                       │
│              │ inc()                                                  │
│              ▼                                                        │
│           [A:2, B:0, C:0]  ◄─── merge ─── [A:0, B:0, C:3]          │
│              │                                   ▲                    │
│              ▼                                   │                    │
│           [A:2, B:0, C:3]  (max of each entry)  │                    │
│              │                                   │                    │
│              │    value() = 2+0+3 = 5            │                    │
│                                                  │                    │
│   Node C: [A:0, B:0, C:0]                       │                    │
│              │                                   │                    │
│              │ inc() x 3                         │                    │
│              ▼                                   │                    │
│           [A:0, B:0, C:3] ──────────────────────┘                    │
│                                                                      │
│   After full sync, all nodes: [A:2, B:0, C:3], value = 5            │
└──────────────────────────────────────────────────────────────────────┘
```

**Why merge = max works**: Each node only increments its own slot. Slots are monotonically increasing. Max captures the latest known value for each node. Commutativity: max(a,b) = max(b,a). Idempotency: max(a,a) = a.

---

### 4.b PN-Counter (Positive-Negative Counter)

Supports both increment and decrement by using **two G-Counters**.

```
    PN-Counter = (P, N)     where P = G-Counter for increments
                                    N = G-Counter for decrements
    
    increment(node_i):  P.increment(node_i)
    decrement(node_i):  N.increment(node_i)
    value():            P.value() - N.value()
    merge(a, b):        (P.merge(a.P, b.P), N.merge(a.N, b.N))
```

**Example**:
```
    Node A increments 3 times, decrements 1 time:
        P = [A:3, B:0]    N = [A:1, B:0]    value = 3 - 1 = 2
    
    Node B increments 2 times:
        P = [A:0, B:2]    N = [A:0, B:0]    value = 2 - 0 = 2
    
    Merge:
        P = [A:3, B:2]    N = [A:1, B:0]    value = 5 - 1 = 4
```

---

### 4.c G-Set (Grow-only Set)

The simplest set CRDT. Elements can only be added, never removed.

```
    payload:    Set S
    add(e):     S = S ∪ {e}
    lookup(e):  e ∈ S
    merge(a,b): a ∪ b
```

**Merge = set union** — trivially commutative, associative, idempotent.

**Limitation**: No remove. Once added, an element is permanent.

---

### 4.d 2P-Set (Two-Phase Set)

Extends G-Set by adding a **tombstone set** for removals.

```
    payload:    (A: G-Set, R: G-Set)     // A = add set, R = remove set
    add(e):     A = A ∪ {e}
    remove(e):  pre: e ∈ A              // can only remove if previously added
                R = R ∪ {e}
    lookup(e):  e ∈ A ∧ e ∉ R
    merge(a,b): (a.A ∪ b.A, a.R ∪ b.R)
```

**Critical limitation**: An element removed once can **never be re-added**. The tombstone is permanent. This is "remove-wins" semantics — if there's a concurrent add and remove of the same element, remove wins.

---

### 4.e OR-Set (Observed-Remove Set)

The most practical set CRDT. Solves the re-add problem by tagging each add with a **unique identifier**.

**Key insight**: Remove only removes the **specific tags** that the remover has observed, not the element globally.

```
    payload:    Set of (element, unique_tag) pairs
    
    add(e):     generate unique tag α
                S = S ∪ {(e, α)}
    
    remove(e):  let R = {(e, α) | (e, α) ∈ S}   // all observed tags for e
                S = S \ R                          // remove only those tags
    
    lookup(e):  ∃α : (e, α) ∈ S
    
    merge(a,b): complex — union of adds minus acknowledged removes
```

```
┌──────────────────────────────────────────────────────────────────────┐
│                     OR-Set: Add-Remove-Re-Add                        │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Node A                              Node B                         │
│   ─────────────────                   ─────────────────              │
│                                                                      │
│   add("milk")                                                        │
│   S = {(milk, α₁)}                                                  │
│        │                                                             │
│        │──── sync ────────────────────▶                              │
│        │                              S = {(milk, α₁)}              │
│        │                                     │                       │
│        │                              remove("milk")                 │
│        │                              // sees tag α₁                 │
│        │                              S = {}                          │
│        │                                     │                       │
│   add("milk")  ◀── concurrent ──▶    remove happened                 │
│   S = {(milk, α₁), (milk, α₂)}             │                       │
│        │                                     │                       │
│        │◀─── sync (remove α₁) ───────────────┘                      │
│        │                                                             │
│        ▼                                                             │
│   S = {(milk, α₂)}    ← milk is STILL IN the set!                   │
│                                                                      │
│   The concurrent add (α₂) was NOT observed by the remover,          │
│   so it survives. This is "add-wins" semantics.                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Semantics**: "Add wins" over concurrent remove — the most intuitive behavior for users.

---

### 4.f LWW-Register (Last-Writer-Wins Register)

Simplest register CRDT. Each write is timestamped; highest timestamp wins.

```
    payload:    (value, timestamp)
    
    assign(v):  state = (v, now())
    
    value():    state.value
    
    merge(a,b): if a.timestamp > b.timestamp then a else b
```

**Pros**: Simple, small metadata.
**Cons**: **Loses data** — concurrent writes result in one being silently discarded. Requires synchronized clocks (or logical timestamps with a tiebreaker like node ID).

```
    Node A: assign("red",  t=100)     Node B: assign("blue", t=101)
    
    After merge: value = "blue"  ← "red" is silently lost
```

---

### 4.g MV-Register (Multi-Value Register)

Instead of picking a winner, **keeps all concurrent values** (siblings). Application must resolve.

```
    payload:    Set of (value, version_vector) pairs
    
    assign(v):  state = {(v, vv_incremented)}
    
    value():    {v | (v, _) ∈ state}   // returns ALL concurrent values
    
    merge(a,b): keep values where neither version vector dominates the other
```

Used in **Riak** (sibling values) and **Dynamo** (shopping cart example).

---

### 4.h RGA (Replicated Growable Array)

For **ordered sequences** — the basis of collaborative text editing.

**Key idea**: Each element has a unique ID = (timestamp, node_id). Insert positions are specified relative to a predecessor element, not by index.

```
    Document: "HELLO"
    
    Internal: H(1,A) → E(2,A) → L(3,A) → L(4,A) → O(5,A)
    
    Node A inserts "!" after O:    ...O(5,A) → !(6,A)
    Node B inserts "W" after O:    ...O(5,A) → W(6,B)
    
    Conflict resolution: order by (timestamp DESC, node_id DESC)
    Result: ...O(5,A) → W(6,B) → !(6,A)     "HELLOW!"
    
    (Specific ordering rules vary by implementation)
```

Deletions use **tombstones** — element is marked deleted but remains in the structure to preserve relative ordering.

---

## 5. Advanced CRDTs

### 5.1 Delta-State CRDTs

**Problem**: State-based CRDTs ship the entire state on every sync — wasteful for large objects.

**Solution**: Ship only the **delta** (the state difference since last sync).

```
    Full state sync:     Ship entire state S          (O(n) bandwidth)
    Delta-state sync:    Ship Δ = S_new ⊔ S_old^(-1)  (O(Δ) bandwidth)
    
    ┌──────────┐    delta: {C:5→6}    ┌──────────┐
    │ [A:3,    │ ─────────────────▶   │ [A:3,    │
    │  B:7,    │    (not full state)  │  B:7,    │
    │  C:6]    │                      │  C:5→6]  │
    └──────────┘                      └──────────┘
    
    Properties: Deltas are joinable — can be batched, reordered.
    Falls back to full state sync if delta log is lost.
```

Delta-state CRDTs combine the **bandwidth efficiency** of op-based with the **simplicity** of state-based.

### 5.2 Merkle-CRDTs

Combine Merkle DAGs (content-addressed, immutable) with CRDT semantics. Used in IPFS/libp2p for decentralized collaboration.

- Each operation is a node in a Merkle DAG
- DAG structure provides causal ordering
- Merging = DAG union (naturally idempotent via content addressing)
- Built-in deduplication and integrity verification

### 5.3 Pure CRDTs

Minimize metadata overhead by computing state from the **operation history** rather than maintaining explicit metadata per element. Trade storage for computation.

---

## 6. Real-World Implementations

### 6.1 Redis Enterprise (Active-Active Geo-Replication)

- Built-in CRDT types: counters, strings, sets, sorted sets, lists, hashes
- Uses **OR-Set** semantics for sets, **LWW** for strings
- Active-active: all replicas accept writes simultaneously
- Conflict resolution is automatic and deterministic
- Sub-millisecond local latency with eventual cross-region convergence

### 6.2 Riak

- Native CRDT support: counters (PN-Counter), sets (OR-Set), maps (nested CRDTs), registers (LWW), flags
- Exposes "siblings" (concurrent values) for MV-Register semantics
- CRDTs stored as special bucket types with automatic merge on read-repair

### 6.3 Figma (Real-time Collaborative Design)

- Custom CRDT implementation for design document state
- Chosen over OT for: simpler reasoning, no central server requirement, offline support
- Operations: layer create/delete/reorder, property changes, component overrides
- LWW for most properties, custom logic for structural changes (layer tree)

### 6.4 Apple Notes / iCloud

- CRDT-based sync engine for collaborative editing
- Handles offline edits on multiple devices
- Merges automatically when connectivity is restored

### 6.5 Automerge

- Open-source JSON CRDT library (Rust core, JS/Python/Swift bindings)
- Full JSON document CRDT with text, lists, maps, counters
- Uses RGA variant for text/lists, LWW for object properties
- Supports time-travel, branching, and merging of document histories
- Peer-to-peer: no server required

### 6.6 Yjs

- High-performance CRDT framework optimized for text editing
- Uses YATA algorithm (variant of RGA)
- Extremely compact encoding (often smaller than OT representations)
- Powers many collaborative editors: Tiptap, Lexical, ProseMirror integrations
- 10-100x faster than Automerge for text operations (benchmarks vary by version)

### 6.7 SoundCloud

- G-Counters for play counts and like counts
- Distributed across data centers
- Monotonically increasing counts merge naturally with max

### 6.8 Phoenix LiveView (Elixir)

- CRDT-inspired state replication between server processes
- Distributed PubSub with CRDT merge semantics

### 6.9 Cassandra

- LWW semantics at the cell (column) level
- Each cell has a timestamp; latest timestamp wins on merge
- Not "true" CRDTs in the academic sense, but applies the same principle
- Counter columns use PN-Counter internally

---

## 7. CRDTs vs OT (Operational Transformation)

```
┌────────────────────┬──────────────────────────┬──────────────────────────┐
│ Dimension          │ OT                       │ CRDTs                    │
├────────────────────┼──────────────────────────┼──────────────────────────┤
│ Architecture       │ Central server required  │ Peer-to-peer possible    │
│ Offline support    │ Hard (queue + rebase)    │ Natural (merge on sync)  │
│ Correctness proof  │ Very hard (TP2 puzzle)   │ Formal (lattice theory)  │
│ Implementation     │ Transform functions grow │ Simpler per-type logic   │
│                    │ O(n²) with op types      │                          │
│ History/Undo       │ Complex inverse ops      │ Natural via state DAG    │
│ Metadata overhead  │ Low                      │ Can be high (tombstones) │
│ Bandwidth          │ Low (ops only)           │ Varies (state vs delta)  │
│ Real-time perf     │ Excellent (mature)       │ Excellent (modern impls) │
│ Used by            │ Google Docs, MS Office   │ Figma, Apple Notes,      │
│                    │                          │ Automerge, Yjs           │
└────────────────────┴──────────────────────────┴──────────────────────────┘
```

**Key insight**: OT requires correct transformation functions for every pair of operation types — this is `O(n²)` complexity and historically riddled with bugs (Jupiter, Google Wave). CRDTs avoid this by making convergence a **property of the data type**, not of operation pairing.

**Modern trend**: CRDTs are winning for new systems. OT remains in legacy systems (Google Docs) where it works well with a central server.

---

## 8. Challenges

### 8.1 Metadata Growth

```
    OR-Set after 1M add/remove cycles:
    
    Active elements:     1,000
    Tombstone entries:   999,000    ← 99.9% is garbage metadata!
    
    G-Counter with 10,000 nodes:
    
    Counter value:       42
    Metadata size:       10,000 entries in the vector
```

### 8.2 Garbage Collection

- **Tombstone pruning**: Requires consensus or stability guarantees ("all replicas have seen this remove")
- **Causal stability**: A state is causally stable when all replicas have moved past it — safe to GC
- **Epoch-based GC**: Periodic checkpoints where metadata is compacted
- Trade-off: GC requires some coordination (defeats pure coordination-free ideal)

### 8.3 Limited Expressiveness

Not all data structures have natural CRDT representations:
- **Queues**: FIFO ordering conflicts with commutativity
- **Transactions**: Multi-object atomicity is fundamentally coordination-requiring
- **Constraints**: "Balance ≥ 0" cannot be enforced without coordination
- **Unique constraints**: Uniqueness requires global knowledge

### 8.4 Semantic Conflicts

```
    "Add wins" vs "Remove wins":
    
    Concurrent:  Node A adds "X"  ||  Node B removes "X"
    
    OR-Set (add-wins):   X is in the set     ← user might be confused
    2P-Set (remove-wins): X is NOT in the set ← user might be confused
    
    Neither is "wrong" — it's a semantic choice the designer must make.
```

### 8.5 Intention Preservation

CRDTs guarantee convergence, but not necessarily that the converged state reflects any user's **intent**. Example: two users concurrently edit the same sentence differently — the merge is valid but may be nonsensical.

---

## 9. Architect's Guide

### 9.1 When to Use CRDTs

**Use CRDTs when**:
- Multi-region active-active replication is required
- Offline-first applications (mobile, desktop, IoT)
- Real-time collaboration (editing, design, whiteboarding)
- High availability is more important than linearizability
- Network partitions are expected/frequent
- Latency-sensitive writes (no coordination round-trip)

**Don't use CRDTs when**:
- Strong consistency is required (bank transfers, inventory with hard limits)
- Data model requires cross-object transactions
- The problem fits a leader-based model well
- State space is small enough for simple LWW

### 9.2 Choosing the Right CRDT

```
┌─────────────────────────────────────┬───────────────────────────────┐
│ Use Case                            │ CRDT Type                     │
├─────────────────────────────────────┼───────────────────────────────┤
│ Like count, view count              │ G-Counter                     │
│ Upvote/downvote, stock level        │ PN-Counter                    │
│ Tags, membership, feature flags     │ OR-Set                        │
│ Shopping cart (add/remove items)    │ OR-Set / OR-Map               │
│ User profile (last edit wins)       │ LWW-Register                  │
│ Config with conflict detection      │ MV-Register                   │
│ Collaborative text editing          │ RGA / Yjs / Automerge         │
│ JSON document collaboration         │ Automerge (JSON CRDT)         │
│ Distributed feature flags           │ LWW-Register or Flag CRDT     │
│ Presence / online status            │ LWW-Register with heartbeat   │
│ Geo-replicated cache                │ LWW-Register per key          │
└─────────────────────────────────────┴───────────────────────────────┘
```

### 9.3 Integration Patterns

```
    Pattern 1: CRDT at Storage Layer (Redis Enterprise, Riak)
    ┌────────┐     ┌────────┐     ┌────────────────────┐
    │ App    │────▶│ API    │────▶│ CRDT-aware DB      │
    │ Server │     │ Layer  │     │ (handles merge)    │
    └────────┘     └────────┘     └────────────────────┘
    
    Pattern 2: CRDT in Application Layer (Automerge, Yjs)
    ┌──────────────────┐     ┌────────────┐
    │ App (CRDT logic) │◀───▶│ Sync Layer │◀───▶ Other peers
    │ Automerge/Yjs    │     │ WebSocket  │
    └──────────────────┘     └────────────┘
    
    Pattern 3: CRDT at Edge (CDN/Edge workers)
    ┌────────┐     ┌───────────────┐     ┌──────────┐
    │ Client │────▶│ Edge (CRDT    │────▶│ Origin   │
    │        │     │  merge here)  │     │ (backup) │
    └────────┘     └───────────────┘     └──────────┘
```

### 9.4 Key Design Decisions

1. **Op-based vs State-based**: If you control the transport layer and can guarantee exactly-once delivery → op-based (less bandwidth). Otherwise → state-based or delta-state (simpler, more robust).

2. **Conflict resolution semantics**: Document what "concurrent conflict" means for each field. Make it explicit: add-wins? LWW? multi-value?

3. **Garbage collection strategy**: Plan for metadata growth from day one. Use causal stability or epoch-based compaction.

4. **Clock strategy**: For LWW, use hybrid logical clocks (HLC) — not wall clocks (drift) and not pure logical clocks (no real-time ordering).

5. **Schema evolution**: How do you migrate CRDT types? Versioned merge functions, or drain-and-replace strategies.

---

## Summary

CRDTs are a mathematically rigorous approach to achieving **strong eventual consistency** without coordination. They trade expressiveness and metadata overhead for guaranteed convergence, availability, and partition tolerance. Modern implementations (delta-state, Yjs, Automerge) have largely solved the practical performance concerns, making CRDTs the default choice for collaborative, offline-first, and geo-distributed applications.

```
    The CRDT guarantee:
    
    ┌─────────────────────────────────────────────────────────┐
    │  If two replicas have received the same set of updates  │
    │  (in ANY order, with ANY duplicates, after ANY delay),  │
    │  they are in the SAME state.                            │
    │                                                         │
    │  No coordination. No consensus. No rollback. Always.    │
    └─────────────────────────────────────────────────────────┘
```
