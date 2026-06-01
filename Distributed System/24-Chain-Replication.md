# Chain Replication

## 1. Problem Statement

Distributed storage systems require strong consistency with high throughput. Existing approaches have fundamental limitations:

**Primary-Backup Replication:**
- All reads AND writes go through the primary
- Primary becomes a bottleneck under high load
- Primary handles replication, acknowledgment tracking, and client responses
- Read throughput limited to a single node's capacity

**Consensus Protocols (Paxos/Raft):**
- Every write requires acknowledgment from a majority of nodes
- Leader must wait for majority before committing — adds latency
- Complex protocols with election, log compaction, and state management
- Read optimization (read leases, follower reads) adds further complexity

**The Question:** Can we design a replication protocol that achieves:
- Linearizable (strong) consistency
- High write throughput via pipelining
- High read throughput without competing with writes
- Simple failure recovery semantics

**Chain Replication** answers this by arranging nodes in a linear chain, separating write ingestion (HEAD) from read serving (TAIL), and pipelining writes through intermediate nodes.

---

## 2. Core Architecture

### Chain Structure

Nodes are arranged in a strict linear order. Each node knows only its predecessor and successor.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CHAIN TOPOLOGY                               │
└─────────────────────────────────────────────────────────────────────┘

  WRITES                                                        READS
    │                                                             ▲
    ▼                                                             │
┌────────┐      ┌────────┐      ┌────────┐      ┌────────┐      │
│  HEAD  │─────▶│  Node1 │─────▶│  Node2 │─────▶│  TAIL  │──────┘
│        │      │        │      │        │      │        │
│ (first │      │(middle)│      │(middle)│      │ (last  │
│  node) │      │        │      │        │      │  node) │
└────────┘      └────────┘      └────────┘      └────────┘
    │                                                ▲
    │         Data flows downstream ──────▶          │
    │                                                │
    └── Writes enter here          Reads served here ┘
```

### Key Invariants

1. **HEAD** is the sole entry point for writes
2. **TAIL** is the sole entry point for reads
3. Every node stores a replica of the full dataset
4. A write is **committed** only after TAIL has applied it
5. TAIL's state represents the exact set of committed operations

### Object State at Each Node

Each node `i` maintains a set of operations it has applied. The relationship:

```
Hist_TAIL ⊆ Hist_Node2 ⊆ Hist_Node1 ⊆ Hist_HEAD

 HEAD has applied the MOST operations (including pending/uncommitted)
 TAIL has applied only COMMITTED operations
```

The "pending" operations are those applied at HEAD but not yet at TAIL:

```
Pending = Hist_HEAD - Hist_TAIL
```

---

## 3. Write Path

### Write Propagation

```
┌─────────────────────────────────────────────────────────────────────┐
│                       WRITE PATH                                     │
└─────────────────────────────────────────────────────────────────────┘

 Client                HEAD         Node1        Node2        TAIL
   │                    │             │            │            │
   │─── write(K,V) ───▶│             │            │            │
   │                    │             │            │            │
   │                    │── apply ──┐ │            │            │
   │                    │           │ │            │            │
   │                    │◀──────────┘ │            │            │
   │                    │             │            │            │
   │                    │── fwd(K,V)─▶│            │            │
   │                    │             │── apply ─┐ │            │
   │                    │             │          │ │            │
   │                    │             │◀─────────┘ │            │
   │                    │             │            │            │
   │                    │             │── fwd(K,V)▶│            │
   │                    │             │            │── apply ─┐ │
   │                    │             │            │          │ │
   │                    │             │            │◀─────────┘ │
   │                    │             │            │            │
   │                    │             │            │── fwd(K,V)▶│
   │                    │             │            │            │── apply
   │                    │             │            │            │
   │◀───────────────────┼─────────────┼────────────┼─── ACK ───│
   │                    │             │            │            │
   │  Write committed   │             │            │            │

   Time ──────────────────────────────────────────────────────────▶
```

### Write Pipeline (Multiple Concurrent Writes)

The power of chain replication is **pipelining** — multiple writes can be in-flight simultaneously at different stages:

```
┌─────────────────────────────────────────────────────────────────────┐
│                   WRITE PIPELINING                                    │
└─────────────────────────────────────────────────────────────────────┘

  Time →    T1         T2         T3         T4         T5

  HEAD:   [Write A]  [Write B]  [Write C]  [Write D]  [Write E]
  Node1:     -       [Write A]  [Write B]  [Write C]  [Write D]
  Node2:     -          -       [Write A]  [Write B]  [Write C]
  TAIL:      -          -          -       [Write A]  [Write B]
                                            ▲
                                            │
                                     A committed at T4
                                     (ACK sent to client)

  At steady state: every time unit, one write commits at TAIL
  Throughput = 1 write per time unit (NOT 1 write per 4 time units)
```

### Write Semantics

1. Client sends `write(obj, value)` to HEAD
2. HEAD applies the update to its local state, appends to pending list
3. HEAD forwards the update to its successor
4. Each intermediate node applies locally and forwards downstream
5. TAIL applies the update — this is the **commit point**
6. TAIL sends ACK directly to the client (not back through the chain)
7. The write is now visible to all future reads

### Write Ordering Guarantee

Because all writes flow through HEAD in a single stream, total ordering of all operations is naturally enforced. No conflicts, no reordering — HEAD serializes everything.

---

## 4. Read Path

### Read Serving at TAIL

```
┌─────────────────────────────────────────────────────────────────────┐
│                        READ PATH                                     │
└─────────────────────────────────────────────────────────────────────┘

 Client                HEAD         Node1        Node2        TAIL
   │                    │             │            │            │
   │                    │             │            │            │
   │─────────────────── read(K) ─────────────────────────────▶│
   │                    │             │            │            │
   │                    │             │            │            │── lookup
   │                    │             │            │            │
   │◀─────────────────── value(K) ───────────────────────────── │
   │                    │             │            │            │
   │                    │             │            │            │

   HEAD, Node1, Node2 are NOT involved in reads at all.
```

### Why This Provides Strong Consistency

- TAIL's state = all committed writes in order
- TAIL never has "dirty" or uncommitted data (writes reach TAIL last)
- Every read at TAIL sees a consistent prefix of all committed operations
- No stale reads are possible — if a write was acknowledged, TAIL has it
- Linearizability: any read after a write's ACK will see that write

### Read-Write Separation

```
┌────────────────────────────────────────────────┐
│           LOAD DISTRIBUTION                     │
├────────────────────────────────────────────────┤
│                                                 │
│   Write clients ──▶ HEAD                        │
│                        │                        │
│                        ▼                        │
│                     [pipeline processing]        │
│                        │                        │
│                        ▼                        │
│   Read clients  ──▶ TAIL                        │
│                                                 │
│   HEAD handles: write ingestion + forwarding    │
│   TAIL handles: read serving + ACK sending      │
│   Middle nodes: only forwarding (low overhead)  │
│                                                 │
└────────────────────────────────────────────────┘
```

No single node handles both read AND write client traffic. This is a major advantage over primary-backup where the primary does everything.

---

## 5. Advantages Over Primary-Backup

### Primary-Backup Bottleneck

```
┌─────────────────────────────────────────────────────────────────────┐
│              PRIMARY-BACKUP vs CHAIN REPLICATION                      │
└─────────────────────────────────────────────────────────────────────┘

  PRIMARY-BACKUP:                      CHAIN REPLICATION:

      ALL reads                             Reads only
      ALL writes                            ───▶ TAIL
         │                                        ▲
         ▼                                        │
    ┌─────────┐                            ┌──────┴──┐
    │ PRIMARY │──┬──▶ Backup1              │  TAIL   │
    │(overload│  │                         └─────────┘
    │   ed!)  │  ├──▶ Backup2                   ▲
    │         │  │                         ┌────┴────┐
    └─────────┘  └──▶ Backup3             │  Node2  │
         │                                 └─────────┘
         │                                      ▲
    PRIMARY must:                          ┌────┴────┐
    - Receive writes                      │  Node1  │
    - Apply writes locally                └─────────┘
    - Replicate to ALL backups                  ▲
    - Wait for ACKs                       ┌────┴────┐
    - Serve ALL reads                     │  HEAD   │◀── Writes only
    - Track replication state             └─────────┘
                                          
                                          HEAD only: receive + forward
                                          Each node: receive + forward
                                          TAIL only: apply + serve reads
```

### Throughput Comparison

| Metric | Primary-Backup | Chain Replication |
|--------|---------------|-------------------|
| Write bandwidth at primary/HEAD | Full object data × N replicas | Full object data × 1 (forward to next only) |
| Network out from primary/HEAD | O(N × data_size) | O(1 × data_size) |
| Read load at primary/HEAD | All read traffic | Zero read traffic |
| Pipelining | Limited (must track N acks) | Natural (fire-and-forget to next) |
| Steady-state throughput | Limited by primary's outbound bandwidth | Limited by slowest link in chain |

### Key Insight: Network Bandwidth Distribution

In Primary-Backup with 5 replicas, the primary must send the write to all 4 backups:
- Primary outbound: `4 × data_size`

In Chain Replication with 5 nodes, each node sends to exactly one successor:
- Each node outbound: `1 × data_size`

The replication work is **distributed evenly** across all nodes.

---

## 6. Failure Handling

Chain replication requires a **Configuration Manager** (external coordination service like ZooKeeper, etcd, or Chubby) that:
- Monitors node health (heartbeats/leases)
- Detects failures
- Reconfigures the chain
- Notifies clients of new HEAD/TAIL

### 6a. HEAD Failure

```
┌─────────────────────────────────────────────────────────────────────┐
│                    HEAD FAILURE                                       │
└─────────────────────────────────────────────────────────────────────┘

  BEFORE:
  ┌────────┐      ┌────────┐      ┌────────┐      ┌────────┐
  │  HEAD  │─────▶│  Node1 │─────▶│  Node2 │─────▶│  TAIL  │
  │   ✗    │      │        │      │        │      │        │
  └────────┘      └────────┘      └────────┘      └────────┘
      │
      ╳ CRASH!


  AFTER (Node1 promoted to HEAD):
                  ┌────────┐      ┌────────┐      ┌────────┐
                  │NEW HEAD│─────▶│  Node2 │─────▶│  TAIL  │
                  │(Node1) │      │        │      │        │
                  └────────┘      └────────┘      └────────┘

  Recovery:
  1. Config Manager detects HEAD failure
  2. Node1 (HEAD's successor) is promoted to new HEAD
  3. Clients are notified to send writes to new HEAD
  4. Some pending writes at old HEAD may be lost (never reached Node1)
     → These writes were NEVER acknowledged to client (safe to lose)
  5. Any write that reached Node1 continues propagating normally
```

**Correctness:** Writes that were at old HEAD but hadn't reached Node1 were never committed (never reached TAIL), so no ACK was sent to client. The client will timeout and retry to the new HEAD. No data loss of committed data.

### 6b. TAIL Failure

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TAIL FAILURE                                       │
└─────────────────────────────────────────────────────────────────────┘

  BEFORE:
  ┌────────┐      ┌────────┐      ┌────────┐      ┌────────┐
  │  HEAD  │─────▶│  Node1 │─────▶│  Node2 │─────▶│  TAIL  │
  │        │      │        │      │        │      │   ✗    │
  └────────┘      └────────┘      └────────┘      └────────┘
                                                       │
                                                       ╳ CRASH!


  AFTER (Node2 promoted to TAIL):
  ┌────────┐      ┌────────┐      ┌────────┐
  │  HEAD  │─────▶│  Node1 │─────▶│NEW TAIL│
  │        │      │        │      │(Node2) │
  └────────┘      └────────┘      └────────┘

  Recovery:
  1. Config Manager detects TAIL failure
  2. Node2 (TAIL's predecessor) is promoted to new TAIL
  3. Node2 commits all writes it has applied (they are now committed)
  4. Clients are notified to read from new TAIL
  5. Future ACKs come from new TAIL
```

**Correctness:** Node2's state is a superset of old TAIL's state (Node2 forwarded everything TAIL had, plus possibly more). Promoting Node2 to TAIL may commit some writes that were pending — this is safe because those writes are in the correct order and were going to be committed anyway.

### 6c. Middle Node Failure

```
┌─────────────────────────────────────────────────────────────────────┐
│                  MIDDLE NODE FAILURE                                  │
└─────────────────────────────────────────────────────────────────────┘

  BEFORE:
  ┌────────┐      ┌────────┐      ┌────────┐      ┌────────┐
  │  HEAD  │─────▶│  Node1 │─────▶│  Node2 │─────▶│  TAIL  │
  │        │      │   ✗    │      │        │      │        │
  └────────┘      └────────┘      └────────┘      └────────┘
                      │
                      ╳ CRASH!


  AFTER (HEAD linked directly to Node2):
  ┌────────┐                       ┌────────┐      ┌────────┐
  │  HEAD  │──────────────────────▶│  Node2 │─────▶│  TAIL  │
  │        │                       │        │      │        │
  └────────┘                       └────────┘      └────────┘

  Recovery:
  1. Config Manager detects Node1 failure
  2. HEAD's successor pointer updated to Node2
  3. HEAD must REPLAY writes that Node1 received but may not have
     forwarded to Node2
  4. HEAD knows which writes it sent to Node1 (sent list)
  5. Node2 knows which writes it received (received list)
  6. HEAD replays: sent_to_Node1 - received_by_Node2
```

**The Replay Problem:**
```
  HEAD's sent list:    [W1, W2, W3, W4, W5]  (sent to Node1)
  Node2's received:    [W1, W2, W3]           (received from Node1)
  
  Gap: [W4, W5] — Node1 crashed after receiving but before forwarding
  
  HEAD must resend [W4, W5] directly to Node2
```

### Failure Detection and Fencing

```
┌─────────────────────────────────────────────────────────────────────┐
│              CONFIGURATION MANAGER ROLE                               │
└─────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────┐
                    │  Configuration Mgr  │
                    │  (ZooKeeper/etcd)   │
                    └──────────┬──────────┘
                               │
                    Monitors health via
                    heartbeats/leases
                               │
              ┌────────┬───────┼───────┬────────┐
              ▼        ▼       ▼       ▼        ▼
          ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
          │ HEAD │ │  N1  │ │  N2  │ │  N3  │ │ TAIL │
          └──────┘ └──────┘ └──────┘ └──────┘ └──────┘

  Config Manager responsibilities:
  ┌──────────────────────────────────────────────┐
  │ • Detect node failures (timeout on heartbeat)│
  │ • Fence failed nodes (revoke leases/keys)    │
  │ • Update chain membership                    │
  │ • Notify predecessor/successor of changes    │
  │ • Notify clients of HEAD/TAIL changes        │
  │ • Coordinate node additions                  │
  └──────────────────────────────────────────────┘
```

---

## 7. CRAQ (Chain Replication with Apportioned Queries)

### The Problem with Basic Chain Replication

Read throughput is limited to TAIL's capacity. With a 5-node chain, 4 nodes are idle for reads — wasteful.

### CRAQ Insight

Allow reads at ANY node, but maintain strong consistency by checking with TAIL when uncertain.

### Version Tracking

Each node stores multiple versions of an object:

```
  Node state for key K:
  ┌─────────────────────────────────┐
  │  Version 5: value="E" [CLEAN]   │  ← latest, committed
  │  Version 4: value="D" [CLEAN]   │
  │  Version 3: value="C" [CLEAN]   │
  └─────────────────────────────────┘

  When a write propagates through but hasn't reached TAIL yet:
  ┌─────────────────────────────────┐
  │  Version 6: value="F" [DIRTY]   │  ← applied but uncommitted
  │  Version 5: value="E" [CLEAN]   │  ← last known committed
  └─────────────────────────────────┘
```

### CRAQ Read Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CRAQ READ ALGORITHM                               │
└─────────────────────────────────────────────────────────────────────┘

  Case 1: Latest version at node is CLEAN
  ─────────────────────────────────────────
  Client          Node2 (any node)
    │                │
    │── read(K) ───▶│
    │                │── check latest version of K
    │                │   latest = v5 [CLEAN]
    │◀── value(v5) ──│
    │                │
    │  Served immediately! No TAIL contact needed.


  Case 2: Latest version at node is DIRTY
  ─────────────────────────────────────────
  Client          Node2              TAIL
    │                │                 │
    │── read(K) ───▶│                 │
    │                │── check latest version of K
    │                │   latest = v6 [DIRTY]
    │                │                 │
    │                │── version_query(K) ──▶│
    │                │                 │── latest committed = v5
    │                │◀── reply(v5) ────│
    │                │                 │
    │◀── value(v5) ──│                 │
    │                │                 │


  Case 3: Commit propagation (TAIL marks versions clean)
  ──────────────────────────────────────────────────────
  When TAIL commits version v6, it sends ACK back through chain.
  Each node receiving the ACK marks v6 as CLEAN and garbage-collects
  older versions.
```

### CRAQ Commit Propagation

```
┌─────────────────────────────────────────────────────────────────────┐
│               CRAQ COMMIT NOTIFICATION                                │
└─────────────────────────────────────────────────────────────────────┘

  HEAD         Node1        Node2        TAIL
    │             │            │            │
    │             │            │            │── commits v6
    │             │            │            │
    │             │            │◀── ACK(v6)─│
    │             │            │            │
    │             │            │── mark v6 CLEAN
    │             │            │── delete v1..v5
    │             │            │            │
    │             │◀── ACK(v6)─│            │
    │             │            │            │
    │             │── mark v6 CLEAN         │
    │             │── delete v1..v5         │
    │             │            │            │
    │◀── ACK(v6)─│            │            │
    │             │            │            │
    │── mark v6 CLEAN                      │
    │── delete v1..v5                      │
```

### CRAQ Read Distribution

```
┌─────────────────────────────────────────────────────────────────────┐
│              CRAQ READ LOAD DISTRIBUTION                              │
└─────────────────────────────────────────────────────────────────────┘

  Basic Chain Replication:         CRAQ:

  Read clients                     Read clients
       │                           │  │  │  │  │
       │                           ▼  ▼  ▼  ▼  ▼
       │                         ┌──┐┌──┐┌──┐┌──┐┌──┐
       │                         │H ││N1││N2││N3││T │
       ▼                         └──┘└──┘└──┘└──┘└──┘
  ┌────────┐
  │  TAIL  │  ← single point     All 5 nodes serve reads!
  │  ONLY  │     of read          Read throughput: ~5x improvement
  └────────┘     throughput       (for read-heavy, mostly-clean workloads)
```

### CRAQ Consistency Modes

CRAQ supports both strong and eventual consistency:
- **Strong:** Always check TAIL if dirty (default, as described above)
- **Eventual:** Return latest local version even if dirty (higher throughput, weaker guarantees)

---

## 8. Comparison with Other Replication Strategies

### Quantitative Comparison

| Aspect | Chain Replication | Primary-Backup | Paxos/Raft |
|--------|------------------|----------------|------------|
| **Write latency** | Sum of N hops (sequential) | 1 hop to all (parallel) | Majority response time |
| **Write throughput** | High (pipelining) | Limited by primary bandwidth | Moderate |
| **Read latency** | 1 hop (TAIL) | 1 hop (primary) | 1 hop (leader, or lease) |
| **Read throughput** | Single node (TAIL) or all (CRAQ) | Single node (primary) | Leader or stale followers |
| **Network load on leader/HEAD** | 1× data to successor | (N-1)× data to all backups | (N-1)× data to all |
| **Consistency** | Linearizable (free) | Linearizable (primary reads) | Linearizable (leader reads) |
| **Min nodes for f failures** | f + 1 | f + 1 | 2f + 1 |
| **Failure detection** | External (Config Mgr) | External or built-in | Built-in (leader election) |
| **Reconfiguration** | Simple (link repair) | Re-elect primary | Leader election protocol |
| **Write ordering** | HEAD serializes | Primary serializes | Log consensus |

### Latency Analysis

```
  Chain (4 nodes):     HEAD ──▶ N1 ──▶ N2 ──▶ TAIL
                       Write latency = 3 × inter-node RTT

  Primary-Backup:      PRIMARY ──┬──▶ B1 ──▶ ACK
  (wait all)                     ├──▶ B2 ──▶ ACK
                                 └──▶ B3 ──▶ ACK
                       Write latency = 1 × RTT (parallel, wait for all)

  Raft (5 nodes):      LEADER ──┬──▶ F1 ──▶ ACK
  (wait majority)                ├──▶ F2 ──▶ ACK  ← commit after 2 ACKs
                                 ├──▶ F3
                                 └──▶ F4
                       Write latency = 1 × RTT (parallel, wait majority)
```

**Chain has higher write latency but higher throughput due to pipelining.**

### Throughput Analysis

```
  Assume: each node can process B bytes/sec of network I/O

  Primary-Backup (3 replicas):
    Primary outbound: 2 × W (sends to 2 backups)
    Max write throughput: B / 2

  Chain (3 nodes):
    Each node outbound: 1 × W (sends to next only)
    Max write throughput: B / 1 = B
    
    2× improvement in write throughput!

  For N replicas:
    Primary-Backup throughput: B / (N-1)
    Chain throughput: B / 1 = B (constant!)
```

---

## 9. Real-World Implementations

### HDFS (Hadoop Distributed File System)

HDFS uses a chain-like **pipeline replication** for data blocks:

```
  Client ──▶ DataNode1 ──▶ DataNode2 ──▶ DataNode3
              (first)       (second)       (third)

  - Client streams 64KB packets to first DataNode
  - Each DataNode forwards to next while writing locally
  - ACK travels back: DN3 → DN2 → DN1 → Client
  - Pipeline provides high write throughput for large files
  - Replication factor typically 3
```

### Microsoft Azure Storage

- Uses chain replication within a **stamp** (storage cluster)
- Each extent (large append-only blob) is replicated via chain
- Stream layer uses chain replication for durability
- Partition layer sits above, manages metadata
- Intra-stamp: chain replication; inter-stamp: async geo-replication

### FAWN-KV (Fast Array of Wimpy Nodes)

- Chain replication on low-power embedded nodes
- Each node: Atom processor + flash storage
- Key-value store with chains of 3 nodes per key range
- Optimized for random reads on flash (energy-efficient)
- Demonstrated: 350 key-value queries per joule

### HyperDex

- Uses **value-dependent chaining**: chain membership determined by the value of secondary attributes
- Enables efficient searches on non-primary key attributes
- Different chains for different attribute subspaces
- Hyperspace hashing maps objects to points in multi-dimensional space

### Ceph (RADOS)

- PG (Placement Group) replication uses a chain-like approach
- Primary receives write, forwards to replicas in sequence
- ACK after all replicas confirm
- Called "primary-copy" but the forwarding resembles chain topology
- Recovery: PG peering protocol to reconcile state

### Amazon EBS (Elastic Block Store)

- Block-level chain replication for volume replicas
- Two replicas in same AZ, writes propagated in chain
- Low latency requirements (sub-millisecond for block I/O)
- Integrated with EC2 for consistent snapshots

### Object Storage Systems (S3-like)

- Large object writes often use pipeline/chain approach
- Object split into chunks, each chunk replicated via chain
- Erasure coding may replace pure replication for cold data
- Chain provides ordering guarantees during writes

---

## 10. Configuration Management

### Chain Membership Management

```
┌─────────────────────────────────────────────────────────────────────┐
│           CONFIGURATION MANAGEMENT ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────┐
  │        Configuration Manager              │
  │        (ZooKeeper / etcd)                 │
  │                                           │
  │  Stores:                                  │
  │  • Chain membership: [H, N1, N2, T]      │
  │  • Node health status                    │
  │  • Current HEAD identity                 │
  │  • Current TAIL identity                 │
  │  • Epoch/version number                  │
  └──────────────┬───────────────────────────┘
                 │
        ┌────────┼────────┬──────────┐
        │        │        │          │
        ▼        ▼        ▼          ▼
     ┌──────┐┌──────┐┌──────┐  ┌────────┐
     │ HEAD ││  N1  ││ TAIL │  │Clients │
     └──────┘└──────┘└──────┘  └────────┘

  All participants watch for configuration changes.
  Epoch numbers prevent split-brain during transitions.
```

### Adding a Node

```
┌─────────────────────────────────────────────────────────────────────┐
│                ADDING A NODE TO THE CHAIN                             │
└─────────────────────────────────────────────────────────────────────┘

  Step 1: Insert new node as new TAIL (easiest position)

  BEFORE:
  ┌────────┐      ┌────────┐      ┌────────┐
  │  HEAD  │─────▶│  Node1 │─────▶│  TAIL  │
  └────────┘      └────────┘      └────────┘

  Step 2: New node begins state transfer from old TAIL
  ┌────────┐      ┌────────┐      ┌────────┐      ┌────────┐
  │  HEAD  │─────▶│  Node1 │─────▶│old TAIL│╌╌╌╌▶│NEW NODE│
  └────────┘      └────────┘      │(still  │ state│(catching│
                                   │serving)│ xfer │  up)    │
                                   └────────┘      └────────┘

  Step 3: Once caught up, new node becomes TAIL
  ┌────────┐      ┌────────┐      ┌────────┐      ┌────────┐
  │  HEAD  │─────▶│  Node1 │─────▶│  Node2 │─────▶│NEW TAIL│
  └────────┘      └────────┘      │(former │      │        │
                                   │ tail)  │      │        │
                                   └────────┘      └────────┘

  During state transfer:
  • Old TAIL continues serving reads and committing writes
  • Old TAIL forwards committed writes to new node
  • Once new node is fully caught up → atomic switchover
  • Config Manager updates TAIL pointer
```

### Fencing

When a node is removed from the chain, it must be **fenced** — prevented from acting on stale state:

- Revoke its lease in the configuration manager
- Network-level fencing (firewall rules, STONITH)
- Epoch-based fencing: all messages carry an epoch; nodes reject messages from old epochs
- Storage fencing: revoke access to shared storage if applicable

---

## 11. Architect's Guide

### When Chain Replication Excels

| Scenario | Why Chain Works |
|----------|----------------|
| Write-heavy workloads | Pipelining gives constant throughput regardless of replica count |
| Strong consistency required | Linearizability is inherent, not bolted on |
| Large object writes | Pipeline amortizes latency over streaming |
| Append-only / log-structured data | Natural fit for sequential propagation |
| Read-write separation possible | Different clients can target HEAD vs TAIL |
| Predictable latency needed | No leader election disruptions (external config mgr) |

### When to Prefer Other Approaches

| Scenario | Better Choice | Why |
|----------|--------------|-----|
| Ultra-low write latency | Primary-Backup (parallel) | Chain adds sequential hop latency |
| Network partitions common | Raft/Paxos | Built-in partition tolerance, no external dependency |
| Self-managing clusters | Raft | No external config manager needed |
| Read-heavy, consistency relaxable | Leaderless (Dynamo) | All nodes serve reads/writes |
| Geographic distribution | Multi-leader / CRDTs | Chain across regions = enormous latency |
| Very large clusters (100+ nodes) | Partitioned chains | Single long chain = high tail latency |

### Design Decisions

**Chain Length:**
- Longer chain = more durability (more copies) but higher write latency
- Typical: 3-5 nodes per chain
- Sweet spot: 3 nodes (HEAD, 1 middle, TAIL) for most workloads

**Partitioning + Chain:**
```
  Key space partitioned into ranges, each range gets its own chain:

  Range [A-F]: HEAD1 → N1 → TAIL1
  Range [G-M]: HEAD2 → N2 → TAIL2
  Range [N-S]: HEAD3 → N3 → TAIL3
  Range [T-Z]: HEAD4 → N4 → TAIL4

  Nodes can participate in multiple chains in different roles:
  • Server X is HEAD for range [A-F] but TAIL for range [G-M]
  • Distributes load evenly across the cluster
```

**CRAQ vs Basic Chain:**
- Use CRAQ when read throughput is critical and most reads hit clean data
- Basic chain is simpler and sufficient when write rate is high (most versions are dirty anyway)
- CRAQ's version-query to TAIL adds complexity and potential latency for dirty reads

### Failure Tolerance Formula

```
  Chain of N nodes tolerates (N-1) sequential failures
  (as long as at least 1 node survives)

  BUT: during reconfiguration, durability is temporarily reduced
  
  Example: 3-node chain
  • Normal: tolerates 2 failures (data on all 3)
  • After 1 failure: now 2-node chain, tolerates 1 more failure
  • Must add replacement node quickly to restore durability
```

### Summary

Chain Replication offers a compelling alternative to traditional replication protocols by:

1. **Separating concerns** — writes at HEAD, reads at TAIL
2. **Distributing network load** — each node forwards to exactly one successor
3. **Providing free linearizability** — TAIL's state is the committed state by definition
4. **Enabling pipelining** — multiple writes in-flight simultaneously
5. **Simplifying reasoning** — total order from single HEAD entry point

The trade-off is higher write latency (sequential hops) and dependence on an external configuration manager. For systems where throughput matters more than per-operation latency, and where strong consistency is non-negotiable, chain replication is an excellent architectural choice.

---

## References

- van Renesse, R. & Schneider, F.B. (2004). "Chain Replication for Supporting High Throughput and Availability"
- Terrace, J. & Freedman, M.J. (2009). "Object Storage on CRAQ: High-throughput chain replication for read-mostly workloads"
- HDFS Architecture Guide — Apache Hadoop Documentation
- Azure Storage: A Highly Available Cloud Storage Service with Strong Consistency (SOSP 2011)
- Andersen, D.G. et al. (2009). "FAWN: A Fast Array of Wimpy Nodes"
