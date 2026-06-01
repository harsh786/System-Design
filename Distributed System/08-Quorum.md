# Quorum in Distributed Systems

## 1. Definition

A **quorum** is the minimum number of nodes in a distributed system that must acknowledge an operation (read or write) for that operation to be considered successful. It is the fundamental mechanism by which distributed systems achieve consistency without requiring all nodes to respond — balancing the tradeoff between availability, latency, and correctness.

The quorum concept originates from voting systems: just as a legislative body needs a minimum number of members present to conduct business, a distributed system needs a minimum number of nodes to agree before it can safely commit an operation.

**Core Insight:** If you ensure that every write is stored on enough nodes, and every read checks enough nodes, then there must be at least one node that participated in both — guaranteeing the read sees the latest write.

---

## 2. The Quorum Formula

### Parameters

| Symbol | Meaning |
|--------|---------|
| **N** | Total number of replicas (replication factor) |
| **W** | Write quorum — minimum nodes that must acknowledge a write |
| **R** | Read quorum — minimum nodes that must respond to a read |

### The Consistency Condition

```
R + W > N
```

This is the **quorum intersection property**. It guarantees that the set of nodes read from and the set of nodes written to **must overlap by at least one node**.

### Mathematical Proof of Overlap

```
Given:
  - Set of nodes that acknowledged the write:  |Write_Set| >= W
  - Set of nodes contacted during read:        |Read_Set|  >= R
  - Total nodes:                                N

By the Pigeonhole Principle:
  If W + R > N, then Write_Set ∩ Read_Set ≠ ∅

Proof by contradiction:
  Assume Write_Set ∩ Read_Set = ∅ (no overlap)
  Then |Write_Set| + |Read_Set| <= N  (they partition into distinct subsets of N)
  But |Write_Set| >= W and |Read_Set| >= R
  So W + R <= |Write_Set| + |Read_Set| <= N
  This means W + R <= N, contradicting our assumption that R + W > N. ∎

Minimum overlap size = R + W - N
```

### ASCII Diagram: Quorum Overlap

```
                        N = 5 Replicas
    ┌─────────────────────────────────────────────────┐
    │                                                 │
    │   Node1     Node2     Node3     Node4     Node5 │
    │    [A]       [B]       [C]       [D]       [E]  │
    │                                                 │
    └─────────────────────────────────────────────────┘

    W = 3 (write to at least 3 nodes)
    R = 3 (read from at least 3 nodes)

    Write Set (W=3):    {A, B, C}
    Read  Set (R=3):              {C, D, E}
                                   ↑
                              OVERLAP (Node C)
                              
    ┌─────────────────────────────────────────────┐
    │         WRITE QUORUM (W=3)                  │
    │  ┌──────────────────────┐                   │
    │  │  [A]   [B]   [C]    │   [D]    [E]      │
    │  │                 ▲    │                    │
    │  └─────────────────┼────┘                   │
    │                    │                        │
    │              ┌─────┼────────────────────┐   │
    │              │     ▼                    │   │
    │              │  [C]    [D]    [E]       │   │
    │              │  READ QUORUM (R=3)       │   │
    │              └─────────────────────────-┘   │
    │                                             │
    │  Overlap = R + W - N = 3 + 3 - 5 = 1 node  │
    └─────────────────────────────────────────────┘
```

### Why Overlap Ensures Latest Write is Read

```
Timeline:
    
    t0: Client writes value V2 (superseding V1)
         → Write acknowledged by W nodes
         → At least W nodes now hold V2
    
    t1: Client reads
         → Contacts R nodes
         → At least one of these R nodes is in the W set (overlap)
         → That node returns V2
         → Client uses version/timestamp to pick V2 over stale V1
    
    The read MUST see V2 because:
    1. Overlap guarantees at least one node has V2
    2. Version vectors or timestamps let client identify V2 as newer
    3. Read-repair or anti-entropy propagates V2 to stale nodes
```

---

## 3. Common Configurations

### Configuration Analysis

#### N=3, W=2, R=2 (Balanced — Most Common)

```
Overlap = 2 + 2 - 3 = 1 node minimum overlap

    [Node1]     [Node2]     [Node3]
       ✓           ✓                    ← Write (any 2 of 3)
                   ✓           ✓        ← Read  (any 2 of 3)
                   ↑
              GUARANTEED OVERLAP
              
Tolerates: 1 node failure for both reads AND writes
Used by: Cassandra (default QUORUM), Riak
```

#### N=3, W=3, R=1 (Fast Reads, Slow Writes)

```
Overlap = 3 + 1 - 3 = 1 node minimum overlap

    [Node1]     [Node2]     [Node3]
       ✓           ✓           ✓       ← Write (ALL 3 must ACK)
       ✓                                ← Read  (any 1 suffices)
       ↑
    ANY single node has latest data
    
Tolerates: 0 node failures for writes, 2 for reads
Tradeoff: Write availability sacrificed for read speed
Use case: Read-heavy workloads, caching layers, config stores
```

#### N=3, W=1, R=3 (Fast Writes, Slow Reads)

```
Overlap = 1 + 3 - 3 = 1 node minimum overlap

    [Node1]     [Node2]     [Node3]
       ✓                                ← Write (any 1 suffices)
       ✓           ✓           ✓        ← Read  (ALL 3 must respond)
       ↑
    Read ALL so you're guaranteed to find the one with latest write

Tolerates: 2 node failures for writes, 0 for reads
Tradeoff: Read availability sacrificed for write speed
Use case: Write-heavy workloads (logging, metrics, event streams)
```

#### N=5, W=3, R=3 (Higher Availability)

```
Overlap = 3 + 3 - 5 = 1 node minimum overlap

    [N1]   [N2]   [N3]   [N4]   [N5]
     ✓      ✓      ✓                    ← Write (any 3 of 5)
                   ✓      ✓      ✓      ← Read  (any 3 of 5)

Tolerates: 2 node failures for both reads AND writes
Used by: Critical systems needing higher fault tolerance
Cost: 5 copies of data, higher storage and network overhead
```

### Comparison Table

```
┌────────────────┬──────────┬──────────┬──────────────┬─────────────┬────────────────┐
│ Configuration  │ Write    │ Read     │ Consistency  │ Write       │ Read           │
│                │ Latency  │ Latency  │ Guarantee    │ Availability│ Availability   │
├────────────────┼──────────┼──────────┼──────────────┼─────────────┼────────────────┤
│ N=3,W=2,R=2   │ Medium   │ Medium   │ Strong       │ Survives 1  │ Survives 1     │
│ (balanced)     │ (2nd     │ (2nd     │ (R+W=4>3)   │ failure     │ failure        │
│                │  fastest)│  fastest)│              │             │                │
├────────────────┼──────────┼──────────┼──────────────┼─────────────┼────────────────┤
│ N=3,W=3,R=1   │ High     │ Low      │ Strong       │ Survives 0  │ Survives 2     │
│ (read-optimized│ (slowest │ (fastest │ (R+W=4>3)   │ failures    │ failures       │
│                │  of 3)   │  of 3)   │              │             │                │
├────────────────┼──────────┼──────────┼──────────────┼─────────────┼────────────────┤
│ N=3,W=1,R=3   │ Low      │ High     │ Strong       │ Survives 2  │ Survives 0     │
│ (write-optimzd)│ (fastest │ (slowest │ (R+W=4>3)   │ failures    │ failures       │
│                │  of 3)   │  of 3)   │              │             │                │
├────────────────┼──────────┼──────────┼──────────────┼─────────────┼────────────────┤
│ N=5,W=3,R=3   │ Medium   │ Medium   │ Strong       │ Survives 2  │ Survives 2     │
│ (high-avail)   │ (3rd     │ (3rd     │ (R+W=6>5)   │ failures    │ failures       │
│                │  fastest)│  fastest)│              │             │                │
├────────────────┼──────────┼──────────┼──────────────┼─────────────┼────────────────┤
│ N=3,W=1,R=1   │ Low      │ Low      │ EVENTUAL     │ Survives 2  │ Survives 2     │
│ (eventual)     │          │          │ (R+W=2<3)   │ failures    │ failures       │
│                │          │          │ NO GUARANTEE │             │                │
└────────────────┴──────────┴──────────┴──────────────┴─────────────┴────────────────┘

Note: "Latency" refers to tail latency — determined by the Nth slowest response
      needed to form the quorum (e.g., W=2 means wait for 2nd response).
```

---

## 4. Strict Quorum

A **strict quorum** requires that operations contact the **actual designated replicas** for a given key — not just any available nodes.

### Properties

- The system has a **fixed, deterministic mapping** from key → set of N replica nodes
- A write MUST be acknowledged by W of those specific N replicas
- A read MUST contact R of those specific N replicas
- Provides **linearizability** when R + W > N (given proper conflict resolution)

### ASCII Diagram: Strict Quorum Operation

```
    Key "user:123" is mapped to replicas: {Node2, Node5, Node7}
    Configuration: N=3, W=2, R=2
    
    CLIENT WRITE (value = "Alice")
    ═══════════════════════════════
    
    Client ──────┬──────────────────────────────────────────┐
                 │                                          │
                 ▼                                          ▼
    ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐
    │  Node2 (replica) │  │  Node5 (replica)  │  │  Node7 (replica) │
    │                  │  │                   │  │                  │
    │  ACK ✓          │  │  ACK ✓            │  │  TIMEOUT ✗       │
    └──────────────────┘  └───────────────────┘  └──────────────────┘
    
    W=2 achieved (Node2 + Node5) → Write SUCCESS
    
    
    CLIENT READ
    ═══════════
    
    Client ──────┬──────────────────────────────────────────┐
                 │                                          │
                 ▼                                          ▼
    ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
    │  Node2 (replica)  │  │  Node5 (replica) │  │  Node7 (replica) │
    │                   │  │                  │  │                  │
    │ Returns "Alice"   │  │  Returns "Alice" │  │  TIMEOUT ✗       │
    │ timestamp: t5     │  │  timestamp: t5   │  │                  │
    └───────────────────┘  └──────────────────┘  └──────────────────┘
    
    R=2 achieved → Read returns "Alice" (latest write guaranteed)

    ┌────────────────────────────────────────────────────────────┐
    │ STRICT QUORUM GUARANTEE:                                   │
    │                                                            │
    │ Because we ONLY contact the designated replicas {2,5,7}:   │
    │ • The overlap property R+W>N is VALID                      │
    │ • No "phantom" nodes can hold stale/different data         │
    │ • Linearizability is achievable                            │
    └────────────────────────────────────────────────────────────┘
```

### When Strict Quorum Fails

Strict quorum sacrifices availability for consistency. If more than (N - W) designated replicas are down, writes fail. If more than (N - R) are down, reads fail.

```
    N=3, W=2: If 2 of the 3 designated replicas are down → WRITE FAILS
    
    [Node2: DOWN]     [Node5: DOWN]     [Node7: UP]
         ✗                 ✗                ✓
         
    Only 1 ACK possible < W=2 → Operation REJECTED
    System returns error rather than risk inconsistency
```

---

## 5. Sloppy Quorum

A **sloppy quorum** relaxes the strict requirement. Instead of requiring W/R of the designated replicas, it allows **any W/R reachable nodes** in the cluster to satisfy the quorum — even nodes that aren't the designated replicas for that key.

### Motivation (Dynamo Paper)

Amazon's Dynamo system prioritized availability ("always writable"). During network partitions or node failures, if designated replicas are unreachable, the system writes to **other healthy nodes** as temporary holders.

### How Sloppy Quorum Works

```
    Key "user:123" designated replicas: {Node2, Node5, Node7}
    N=3, W=2, R=2
    
    SCENARIO: Node5 and Node7 are unreachable (network partition)
    
    STRICT QUORUM BEHAVIOR:
    ════════════════════════
    Client → Node2 ✓   Node5 ✗   Node7 ✗
    Only 1 ACK < W=2 → WRITE FAILS ❌
    
    
    SLOPPY QUORUM BEHAVIOR:
    ════════════════════════
    Client → Node2 ✓   Node5 ✗   Node7 ✗
             Node3 ✓ (substitute!)
    
    2 ACKs (Node2 + Node3) >= W=2 → WRITE SUCCEEDS ✓
    Node3 holds data temporarily with a "hint" for Node5 or Node7
    
    ┌─────────────────────────────────────────────────────────┐
    │                    RING TOPOLOGY                         │
    │                                                         │
    │            Node1                                        │
    │           /     \                                       │
    │        Node7     Node2 ◄── designated + available       │
    │  (DOWN) ✗ │       │                                     │
    │           │       │                                     │
    │        Node6     Node3 ◄── SUBSTITUTE (hinted handoff)  │
    │           \     /                                       │
    │            Node5                                        │
    │           (DOWN) ✗                                      │
    │                                                         │
    │  Write goes to Node2 (designated) + Node3 (substitute)  │
    │  Node3 stores hint: "deliver to Node5 when it recovers" │
    └─────────────────────────────────────────────────────────┘
```

### Why R + W > N No Longer Guarantees Consistency

```
    CONSISTENCY VIOLATION SCENARIO:
    ════════════════════════════════
    
    Time T1: Write "V2" with sloppy quorum
    ──────────────────────────────────────
    Designated replicas: {A, B, C}
    A is down → write goes to {B, C, D(substitute)}   W=3 ✓
    
    Time T2: Read with sloppy quorum  
    ──────────────────────────────────
    Designated replicas: {A, B, C}
    C is down → read contacts {A, B, E(substitute)}   R=3 ✓
    
    What does A have? → STALE data (it was down during write!)
    What does B have? → V2 ✓
    What does E have? → No data for this key
    
    Read set:  {A, B, E}
    Write set: {B, C, D}
    Overlap:   {B} ← happens to overlap here, but NOT GUARANTEED
    
    WORSE SCENARIO:
    Write set: {D, E, F} (all substitutes, none designated)
    Read set:  {A, B, C} (all designated, recovered after write)
    Overlap:   ∅  ← EMPTY! Read misses the write entirely!
    
    ┌─────────────────────────────────────────────────────────────┐
    │  SLOPPY QUORUM: R + W > N is meaningless because W and R   │
    │  may contact DIFFERENT sets of nodes with NO overlap.       │
    │                                                             │
    │  Strict:  Guaranteed overlap among fixed N replicas         │
    │  Sloppy:  "N" is elastic — any healthy nodes count         │
    │           → No intersection guarantee → No consistency     │
    └─────────────────────────────────────────────────────────────┘
```

### Hinted Handoff

When a substitute node accepts a write on behalf of an unavailable replica, it stores a **hint** — metadata indicating who the intended recipient is. Once the intended node recovers, the hint is "handed off":

```
    Node3 (substitute) holds:
    ┌─────────────────────────────────────┐
    │  Key: "user:123"                    │
    │  Value: "Alice"                     │
    │  Timestamp: t5                      │
    │  Hint: "intended for Node5"         │
    └─────────────────────────────────────┘
    
    When Node5 comes back online:
    Node3 → Node5: "Here's data that belongs to you"
    Node5 stores the data
    Node3 deletes the hint
```

### Strict vs. Sloppy: Summary

```
┌──────────────────┬────────────────────────┬────────────────────────────┐
│ Property         │ Strict Quorum          │ Sloppy Quorum              │
├──────────────────┼────────────────────────┼────────────────────────────┤
│ Nodes contacted  │ Only designated N      │ Any healthy node in cluster│
│ R+W>N guarantees │ Consistency (lineariz.)│ Nothing (no real overlap)  │
│ Availability     │ Lower (fixed set)      │ Higher (flexible set)      │
│ Durability       │ Data on correct nodes  │ Data may be on temp nodes  │
│ Use case         │ Strong consistency     │ "Always writable" systems  │
│ Examples         │ Cassandra QUORUM       │ Dynamo, Riak (default)     │
└──────────────────┴────────────────────────┴────────────────────────────┘
```

---

## 6. Quorum in Different Contexts

### 6.1 Read/Write Quorum (Data Replication)

Used in replicated databases where data is written to multiple nodes.

```
    ┌─────────────────────────────────────────────────────────┐
    │                 READ/WRITE QUORUM                        │
    │                                                         │
    │  Purpose: Ensure readers see latest writes              │
    │  Mechanism: R + W > N overlap                           │
    │  Conflict resolution: Timestamps, version vectors       │
    │                                                         │
    │  Systems: Cassandra, DynamoDB, Riak, Voldemort          │
    │                                                         │
    │  Client                                                 │
    │    │                                                    │
    │    ├──write──► Replica1 (ACK) ┐                         │
    │    ├──write──► Replica2 (ACK) ├─► W=2 satisfied         │
    │    └──write──► Replica3 (...)  ┘                         │
    │                                                         │
    └─────────────────────────────────────────────────────────┘
```

### 6.2 Consensus Quorum (Leader Election)

Used in consensus protocols (Raft, Paxos) where a single value must be agreed upon.

```
    ┌─────────────────────────────────────────────────────────┐
    │                CONSENSUS QUORUM                          │
    │                                                         │
    │  Purpose: Agree on a single value/leader                │
    │  Mechanism: Strict majority (⌊N/2⌋ + 1)                │
    │  Why majority: Two majorities ALWAYS overlap            │
    │                                                         │
    │  N=5 cluster: Majority = 3                              │
    │                                                         │
    │  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐         │
    │  │ N1  │  │ N2  │  │ N3  │  │ N4  │  │ N5  │         │
    │  │Vote │  │Vote │  │Vote │  │     │  │     │         │
    │  │ A   │  │ A   │  │ A   │  │     │  │     │         │
    │  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘         │
    │     3 votes for A = MAJORITY → A is leader             │
    │                                                         │
    │  Key insight: No two different leaders can both get     │
    │  a majority simultaneously (pigeonhole principle)       │
    │                                                         │
    │  Systems: Raft, Paxos, ZAB (ZooKeeper), etcd           │
    └─────────────────────────────────────────────────────────┘
```

### 6.3 Split-Brain Prevention

```
    ┌─────────────────────────────────────────────────────────┐
    │              SPLIT-BRAIN PREVENTION                      │
    │                                                         │
    │  Network partition splits cluster into two groups:       │
    │                                                         │
    │  Partition A          │         Partition B              │
    │  ┌────┐ ┌────┐       │         ┌────┐ ┌────┐          │
    │  │ N1 │ │ N2 │       │         │ N4 │ │ N5 │          │
    │  └────┘ └────┘       │         └────┘ └────┘          │
    │       ┌────┐         │                                  │
    │       │ N3 │         │                                  │
    │       └────┘         │                                  │
    │                      │                                  │
    │  Size: 3 (MAJORITY)  │         Size: 2 (minority)      │
    │  Can elect leader ✓  │         Cannot elect leader ✗   │
    │  Can accept writes ✓ │         Rejects writes ✗        │
    │                      │                                  │
    │  GUARANTEE: At most ONE partition can have majority     │
    │  → At most ONE leader → No split-brain                 │
    └─────────────────────────────────────────────────────────┘
```

---

## 7. Failure Tolerance

### General Formulas

```
Given N replicas, W write quorum, R read quorum:

  Maximum write failures tolerated:  N - W
  Maximum read failures tolerated:   N - R
  Maximum failures for BOTH:         min(N-W, N-R)
  
  For majority quorum (W = R = ⌊N/2⌋ + 1):
    Failures tolerated = ⌊(N-1)/2⌋
    
    N=3: tolerates 1 failure
    N=5: tolerates 2 failures
    N=7: tolerates 3 failures
```

### Failure Scenarios

```
┌───────────────┬───────────┬──────────┬───────────────┬──────────────────────┐
│ Configuration │ N-W       │ N-R      │ Both OK if    │ System behavior      │
│               │ (write    │ (read    │ failures <=   │ under max failures   │
│               │  survives)│  survives│               │                      │
├───────────────┼───────────┼──────────┼───────────────┼──────────────────────┤
│ N=3,W=2,R=2  │ 1         │ 1        │ 1             │ Balanced             │
│ N=3,W=3,R=1  │ 0         │ 2        │ 0             │ Writes fragile       │
│ N=3,W=1,R=3  │ 2         │ 0        │ 0             │ Reads fragile        │
│ N=5,W=3,R=3  │ 2         │ 2        │ 2             │ Highly available     │
│ N=5,W=4,R=2  │ 1         │ 3        │ 1             │ Read-optimized       │
│ N=7,W=4,R=4  │ 3         │ 3        │ 3             │ Mission-critical     │
└───────────────┴───────────┴──────────┴───────────────┴──────────────────────┘
```

### Availability Calculation

```
If each node has independent availability p (e.g., p = 0.99):

P(quorum of W out of N succeeds) = Σ C(N,k) * p^k * (1-p)^(N-k)  for k = W to N

Example: N=3, W=2, p=0.99
  P(write succeeds) = C(3,2)*0.99²*0.01¹ + C(3,3)*0.99³*0.01⁰
                     = 3*0.9801*0.01 + 1*0.970299
                     = 0.029403 + 0.970299
                     = 0.999702  (99.97% available)
                     
  vs. requiring ALL nodes (W=3):
  P = 0.99³ = 0.970299 (97.03%)
  
  vs. single node (W=1):
  P = 1 - (1-0.99)³ = 1 - 0.000001 = 0.999999 (99.9999%)
  
  Quorum provides a middle ground between "all must respond" and "any one suffices"
```

---

## 8. Multi-Datacenter Quorum

### The Challenge

```
    ┌─────────────────┐              ┌─────────────────┐
    │   DC-East       │   ~80ms RTT  │   DC-West       │
    │                 │◄────────────►│                 │
    │  N1  N2  N3    │              │  N4  N5  N6    │
    │                 │              │                 │
    └─────────────────┘              └─────────────────┘
    
    If quorum requires nodes in BOTH DCs:
    → Every write pays cross-DC latency (~80-200ms)
    → If inter-DC link fails, NO writes possible
```

### LOCAL_QUORUM vs EACH_QUORUM

```
    ┌──────────────────────────────────────────────────────────────────┐
    │                        LOCAL_QUORUM                               │
    │                                                                  │
    │  Write acknowledged when quorum reached in LOCAL DC only         │
    │  Replication to remote DC happens asynchronously                 │
    │                                                                  │
    │  ┌────────────────────┐           ┌────────────────────┐        │
    │  │   DC-East (LOCAL)  │           │   DC-West (REMOTE) │        │
    │  │                    │           │                    │        │
    │  │  Client──►N1 ✓    │   async   │   N4 (eventually)  │        │
    │  │           N2 ✓    ├──────────►│   N5 (eventually)  │        │
    │  │           N3      │           │   N6 (eventually)  │        │
    │  │                    │           │                    │        │
    │  │  LOCAL_QUORUM=2 ✓ │           │                    │        │
    │  └────────────────────┘           └────────────────────┘        │
    │                                                                  │
    │  Latency: LOW (intra-DC only, ~1-5ms)                           │
    │  Consistency: Strong within DC, eventual across DCs              │
    │  Risk: Data loss if local DC fails before async replication      │
    └──────────────────────────────────────────────────────────────────┘
    
    ┌──────────────────────────────────────────────────────────────────┐
    │                        EACH_QUORUM                                │
    │                                                                  │
    │  Write acknowledged when quorum reached in EACH DC               │
    │                                                                  │
    │  ┌────────────────────┐           ┌────────────────────┐        │
    │  │   DC-East          │           │   DC-West          │        │
    │  │                    │           │                    │        │
    │  │  Client──►N1 ✓    │    sync   │   N4 ✓            │        │
    │  │           N2 ✓    ├──────────►│   N5 ✓            │        │
    │  │           N3      │           │   N6               │        │
    │  │                    │           │                    │        │
    │  │  Quorum=2 ✓       │           │   Quorum=2 ✓      │        │
    │  └────────────────────┘           └────────────────────┘        │
    │                                                                  │
    │  Latency: HIGH (cross-DC RTT, ~80-200ms)                        │
    │  Consistency: Strong across ALL DCs                              │
    │  Durability: Survives entire DC failure                          │
    └──────────────────────────────────────────────────────────────────┘
```

### Cassandra NetworkTopologyStrategy

```
    Replication: {'DC-East': 3, 'DC-West': 3}
    Total N = 6 (3 per DC)
    
    Consistency Levels:
    ┌─────────────────┬───────────────────────────────────────────────┐
    │ Level           │ Behavior                                      │
    ├─────────────────┼───────────────────────────────────────────────┤
    │ ONE             │ 1 node anywhere                               │
    │ LOCAL_ONE       │ 1 node in local DC                            │
    │ QUORUM          │ ⌊6/2⌋+1 = 4 nodes across ALL DCs             │
    │ LOCAL_QUORUM    │ ⌊3/2⌋+1 = 2 nodes in LOCAL DC                │
    │ EACH_QUORUM    │ ⌊3/2⌋+1 = 2 nodes in EACH DC                 │
    │ ALL             │ All 6 nodes                                   │
    └─────────────────┴───────────────────────────────────────────────┘
    
    Recommended production setup:
    - Writes:  LOCAL_QUORUM (low latency, tolerate 1 local failure)
    - Reads:   LOCAL_QUORUM (strong local consistency)
    - Result:  Each DC independently consistent
    - Tradeoff: Brief cross-DC inconsistency window
```

### Three-DC Setup

```
    ┌──────────┐        ┌──────────┐        ┌──────────┐
    │ DC-US    │        │ DC-EU    │        │ DC-APAC  │
    │          │        │          │        │          │
    │ N1 N2 N3│◄──────►│ N4 N5 N6│◄──────►│ N7 N8 N9│
    │          │  100ms │          │  150ms │          │
    └──────────┘        └──────────┘        └──────────┘
    
    RF = {'US': 3, 'EU': 3, 'APAC': 3}, Total N = 9
    
    EACH_QUORUM write: Need 2 ACKs from US + 2 from EU + 2 from APAC
    → Latency = max(intra-US, RTT-to-EU, RTT-to-APAC) ≈ 150ms
    
    LOCAL_QUORUM write: Need 2 ACKs from local DC only
    → Latency ≈ 2-5ms (intra-DC)
```

---

## 9. Real-World Implementations

### Apache Cassandra

```java
// Write with QUORUM consistency
session.execute(
    QueryBuilder.insertInto("users")
        .value("id", userId)
        .value("name", "Alice")
        .setConsistencyLevel(ConsistencyLevel.QUORUM)
);

// Read with LOCAL_QUORUM
session.execute(
    QueryBuilder.select().from("users")
        .where(eq("id", userId))
        .setConsistencyLevel(ConsistencyLevel.LOCAL_QUORUM)
);
```

```
Cassandra Consistency Levels:
┌─────────────────┬────────────────────────────────────────────────────┐
│ Level           │ Nodes required                                     │
├─────────────────┼────────────────────────────────────────────────────┤
│ ANY             │ 1 (including hinted handoff) — sloppy quorum      │
│ ONE             │ 1 replica                                          │
│ TWO             │ 2 replicas                                         │
│ THREE           │ 3 replicas                                         │
│ QUORUM          │ ⌊N/2⌋ + 1 across all DCs                          │
│ LOCAL_QUORUM    │ ⌊local_N/2⌋ + 1 in coordinator's DC              │
│ EACH_QUORUM    │ ⌊local_N/2⌋ + 1 in EACH DC                       │
│ ALL             │ All N replicas                                     │
└─────────────────┴────────────────────────────────────────────────────┘

Strong consistency recipe: Write QUORUM + Read QUORUM (or LOCAL_ variants)
```

### Amazon DynamoDB

```
DynamoDB uses quorum internally:
- Replication factor N = 3 (fixed, not configurable)
- Writes always go to all 3 replicas
- "Eventually consistent read": R=1 (any replica)
- "Strongly consistent read":   R=2 (majority quorum)

┌─────────────────────────────────────────────────────────────┐
│  DynamoDB Internal Architecture                             │
│                                                             │
│  Write: Client → Leader → 2 of 3 replicas ACK (W=2)        │
│  Eventually consistent read: 1 replica (may be stale)      │
│  Strongly consistent read: leader ensures latest (R=2)      │
│                                                             │
│  R+W = 2+2 = 4 > 3 = N ✓ (strong consistency achievable)  │
└─────────────────────────────────────────────────────────────┘
```

### MongoDB

```javascript
// Write with majority concern
db.users.insertOne(
  { name: "Alice" },
  { writeConcern: { w: "majority", wtimeout: 5000 } }
);

// Read with majority read concern (linearizable reads)
db.users.find({ name: "Alice" }).readConcern("majority");
```

```
MongoDB Write Concern:
  w: 1         → Acknowledged by primary only
  w: "majority" → Acknowledged by majority of replica set
  w: N         → Acknowledged by N members
  
MongoDB Read Concern:
  "local"       → Returns local data (may be rolled back)
  "majority"    → Returns data committed to majority
  "linearizable"→ Reflects all successful majority writes (strongest)
  
Replica Set (N=3):  Primary + 2 Secondaries
  w:"majority" = 2 nodes must ACK
  Tolerates 1 node failure for writes
```

### Raft Consensus

```
Raft uses strict majority quorum for ALL decisions:

  Quorum = ⌊N/2⌋ + 1 (always majority)
  
  ┌─────────────────────────────────────────────────────────┐
  │  RAFT LOG REPLICATION                                   │
  │                                                         │
  │  Leader receives client write                           │
  │    │                                                    │
  │    ├── AppendEntries → Follower1  (ACK ✓)             │
  │    ├── AppendEntries → Follower2  (ACK ✓)             │
  │    ├── AppendEntries → Follower3  (timeout)            │
  │    └── AppendEntries → Follower4  (ACK ✓)             │
  │                                                         │
  │  Leader + 3 ACKs = 4 out of 5 ≥ majority(3)           │
  │  → Entry COMMITTED                                     │
  │  → Applied to state machine                            │
  │  → Response sent to client                             │
  │                                                         │
  │  Leader Election:                                       │
  │  Candidate needs votes from majority to become leader  │
  │  N=5 → needs 3 votes (including self-vote)             │
  └─────────────────────────────────────────────────────────┘
  
  Used by: etcd, CockroachDB, TiKV, Consul
```

### ZooKeeper (ZAB Protocol)

```
ZooKeeper Atomic Broadcast:
  - All writes go through the leader
  - Leader proposes to all followers
  - Write committed when majority ACK (including leader)
  
  Ensemble size    Quorum    Failures tolerated
  ─────────────    ──────    ──────────────────
  3                2         1
  5                3         2
  7                4         3
  
  ZooKeeper recommends ODD ensemble sizes:
  - N=3 and N=4 both tolerate 1 failure → N=3 is more efficient
  - N=5 and N=6 both tolerate 2 failures → N=5 is more efficient
```

### CockroachDB

```
CockroachDB: Raft-per-Range architecture

  Data is split into ranges (~512MB each)
  Each range is a Raft group with 3-5 replicas
  
  ┌────────────────────────────────────────────────────┐
  │  Table: users                                      │
  │                                                    │
  │  Range1 [a-m]        Range2 [n-z]                 │
  │  ┌─────────────┐     ┌─────────────┐              │
  │  │ Raft Group  │     │ Raft Group  │              │
  │  │ N1(L) N3 N5 │     │ N2(L) N4 N6 │              │
  │  │ Quorum: 2/3 │     │ Quorum: 2/3 │              │
  │  └─────────────┘     └─────────────┘              │
  │                                                    │
  │  Each range independently:                         │
  │  - Elects its own leader                          │
  │  - Replicates via Raft                            │
  │  - Commits with majority quorum                   │
  └────────────────────────────────────────────────────┘
```

---

## 10. Quorum Intersection Property — Formal Treatment

### Formal Definition

Let S be a set of N nodes. A **quorum system** Q is a collection of subsets of S (called quorums) such that:

```
∀ Q1, Q2 ∈ Q:  Q1 ∩ Q2 ≠ ∅   (Intersection Property)
```

Every pair of quorums must share at least one node.

### Proof: Majority Quorums Satisfy Intersection Property

```
Theorem: If |Q| > N/2 for all Q ∈ Q, then any two quorums intersect.

Proof:
  Let Q1, Q2 be any two quorums with |Q1| > N/2 and |Q2| > N/2.
  Suppose Q1 ∩ Q2 = ∅.
  Then |Q1 ∪ Q2| = |Q1| + |Q2| > N/2 + N/2 = N.
  But Q1 ∪ Q2 ⊆ S and |S| = N.
  Contradiction. Therefore Q1 ∩ Q2 ≠ ∅.  ∎
  
  Minimum intersection size:
  |Q1 ∩ Q2| ≥ |Q1| + |Q2| - N > N/2 + N/2 - N = 0
  
  For R + W > N:
  |Read_Q ∩ Write_Q| ≥ R + W - N ≥ 1
```

### Implications for Linearizability

```
Linearizability requires:
  1. Every read returns the value of the most recent write
  2. Operations appear to take effect at a single point in time

Quorum intersection enables this:
  
  Write operation at time t:
    - Assigns timestamp t to value V
    - Writes V with timestamp t to W nodes
    
  Read operation at time t' > t:
    - Contacts R nodes
    - At least one node in R has V with timestamp t (by intersection)
    - Returns value with highest timestamp
    - If no concurrent writes → returns V → linearizable!
    
  CAVEAT: Quorum alone is NOT sufficient for linearizability.
  Also needed:
    - Unique, totally-ordered timestamps
    - No concurrent conflicting writes without resolution
    - OR: a consensus protocol to serialize writes
    
  Quorum intersection is NECESSARY but not SUFFICIENT for linearizability.
  It provides the foundation on which linearizable protocols are built.
```

### Generalized Quorum Systems

```
Beyond majority quorums, other valid quorum systems exist:

1. GRID QUORUM:
   Arrange N nodes in a √N × √N grid.
   Quorum = any full row + any full column
   Size = 2√N - 1 (much smaller than majority for large N)
   
   ┌───┬───┬───┐
   │ A │ B │ C │  ← Row quorum
   ├───┼───┼───┤
   │ D │ E │ F │
   ├───┼───┼───┤
   │ G │ H │ I │
   └───┴───┴───┘
         ↑
     Column quorum
   
   Read quorum: {A,B,C,B,E,H} (row 1 + column 2) 
   Write quorum: {D,E,F,A,E,I} (row 2 + column 3... wait, must intersect)
   Any row+column combination intersects any other → valid quorum system!
   
2. WEIGHTED QUORUM:
   Assign weights to nodes (e.g., powerful nodes get higher weight)
   Quorum = any subset whose total weight exceeds threshold
   
3. HIERARCHICAL QUORUM:
   Nodes organized in tree; quorum = majority at each level
```

---

## 11. Architect's Guide

### Decision Framework

```
┌─────────────────────────────────────────────────────────────────────┐
│                    QUORUM CONFIGURATION DECISION TREE                │
│                                                                     │
│  What is your PRIMARY requirement?                                  │
│  │                                                                  │
│  ├─► Strong Consistency                                             │
│  │     │                                                            │
│  │     ├─► Single DC: N=3, W=2, R=2 (or Raft-based system)        │
│  │     └─► Multi-DC: EACH_QUORUM or consensus (CockroachDB/Spanner)│
│  │                                                                  │
│  ├─► High Availability (always writable)                            │
│  │     │                                                            │
│  │     ├─► Accept eventual consistency: N=3, W=1, R=1              │
│  │     └─► With some consistency: Sloppy quorum + read repair      │
│  │                                                                  │
│  ├─► Low Read Latency                                               │
│  │     └─► N=3, W=3, R=1 (or W=2, R=1 with eventual consistency)  │
│  │                                                                  │
│  ├─► Low Write Latency                                              │
│  │     └─► N=3, W=1, R=3 (or LOCAL_QUORUM in multi-DC)            │
│  │                                                                  │
│  └─► Survive DC Failure                                             │
│        └─► N≥5 across 3+ DCs, EACH_QUORUM or Raft with cross-DC   │
│            replicas                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Workload-Based Recommendations

```
┌────────────────────────┬────────────────────────┬──────────────────────────┐
│ Workload Pattern       │ Recommended Config     │ Rationale                │
├────────────────────────┼────────────────────────┼──────────────────────────┤
│ OLTP (balanced R/W)    │ N=3, W=2, R=2         │ Balanced consistency     │
│                        │ LOCAL_QUORUM           │ and performance          │
├────────────────────────┼────────────────────────┼──────────────────────────┤
│ Read-heavy (95% reads) │ N=3, W=3, R=1         │ Reads hit single node;   │
│ e.g., product catalog  │ or N=3,W=2,R=1(event.)│ all nodes always current │
├────────────────────────┼────────────────────────┼──────────────────────────┤
│ Write-heavy (logging)  │ N=3, W=1, R=3         │ Writes fast; reads rare  │
│ e.g., event streams    │ or W=1,R=1 (eventual) │ and can be slower        │
├────────────────────────┼────────────────────────┼──────────────────────────┤
│ Financial transactions │ Raft/Paxos consensus  │ Linearizability required │
│ e.g., bank transfers   │ (CockroachDB, Spanner)│ Quorum alone insufficient│
├────────────────────────┼────────────────────────┼──────────────────────────┤
│ Shopping cart (Dynamo)  │ Sloppy quorum, W=1    │ Always writable, merge   │
│ e.g., "add to cart"    │ conflict resolution   │ conflicts on read        │
├────────────────────────┼────────────────────────┼──────────────────────────┤
│ Global user profiles   │ LOCAL_QUORUM per DC   │ Low latency local reads  │
│ e.g., social media     │ async cross-DC repl.  │ accept brief staleness   │
└────────────────────────┴────────────────────────┴──────────────────────────┘
```

### Common Pitfalls

```
1. ASSUMING SLOPPY QUORUM = STRONG CONSISTENCY
   Sloppy quorum with R+W>N does NOT guarantee overlap.
   If you need consistency, use STRICT quorum.

2. IGNORING TAIL LATENCY
   Quorum latency = time for the Wth/Rth SLOWEST response.
   P99 latency of quorum ≈ P99 of slowest required node.
   Mitigation: Send to all N, take first W/R responses.

3. FORGETTING ABOUT CONCURRENT WRITES
   Quorum ensures you READ the latest write, but if two writes
   are concurrent (neither completed before the other started),
   you need conflict resolution (LWW, vector clocks, CRDTs).

4. EVEN-NUMBERED CLUSTERS
   N=4 with majority quorum = 3. Same fault tolerance as N=3 (1 failure).
   You're paying for an extra replica with no availability benefit.
   Always prefer ODD N for consensus systems.

5. CROSS-DC QUORUM WITHOUT NEED
   Using EACH_QUORUM when LOCAL_QUORUM suffices adds 100ms+ to every write.
   Only use EACH_QUORUM when you need guaranteed cross-DC durability.

6. NOT ACCOUNTING FOR READ REPAIR
   After a quorum read returns stale + fresh values, READ REPAIR
   updates stale nodes. Without it, you rely on anti-entropy alone
   (which may have significant delay).
```

### Monitoring and Operational Concerns

```
Key metrics to monitor:
  - Quorum achievement rate (% of operations meeting quorum)
  - Quorum latency (time to achieve W or R responses)
  - Replica divergence (how stale are the slowest replicas?)
  - Hinted handoff queue depth (sloppy quorum only)
  - Read repair rate (frequency of stale data encountered)
  
Alerting thresholds:
  - Quorum failures > 0.1% → investigate node health
  - P99 quorum latency > 2x baseline → possible network issue
  - Hinted handoff queue growing → replica may be permanently down
```

---

## Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                     QUORUM AT A GLANCE                           │
│                                                                 │
│  Core formula:        R + W > N                                 │
│  Core guarantee:      Read quorum ∩ Write quorum ≠ ∅            │
│  Core tradeoff:       Consistency vs. Availability vs. Latency  │
│                                                                 │
│  Strict quorum:       Fixed replica set → true consistency      │
│  Sloppy quorum:       Any healthy nodes → true availability     │
│  Consensus quorum:    Majority → single agreed value            │
│                                                                 │
│  Rule of thumb:       Start with N=3, W=2, R=2                  │
│                       Tune based on measured workload            │
└─────────────────────────────────────────────────────────────────┘
```
