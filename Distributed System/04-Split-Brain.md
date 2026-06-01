# Split Brain in Distributed Systems

## 1. Definition

**Split brain** is a catastrophic failure mode in distributed systems where a network partition divides a cluster into two or more subclusters, each believing it is the sole authoritative owner of the system's state. Each subcluster continues to accept writes independently, leading to divergent state that may be impossible to reconcile.

```
                        HEALTHY CLUSTER
    ┌─────────────────────────────────────────────────┐
    │                                                 │
    │   [Node A] ◄──────► [Node B] ◄──────► [Node C] │
    │       ▲                                   ▲     │
    │       └───────────────────────────────────┘     │
    │              All nodes in agreement             │
    └─────────────────────────────────────────────────┘

                     SPLIT BRAIN STATE
    ┌──────────────────┐     ╳╳╳╳╳     ┌──────────────────┐
    │  Subcluster 1    │   PARTITION    │  Subcluster 2    │
    │                  │               │                  │
    │  [Node A]◄─►[B]  │    NETWORK    │  [Node C]         │
    │  "I am master"   │     DOWN      │  "I am master"   │
    │  Accepts writes  │               │  Accepts writes  │
    └──────────────────┘               └──────────────────┘
           │                                    │
           ▼                                    ▼
      State: X=100                        State: X=200
              ← DIVERGED! →
```

The term originates from neuroscience — a split-brain patient has severed corpus callosum, causing each hemisphere to operate independently. The analogy is precise: each partition operates with its own "consciousness."

---

## 2. How Split Brain Occurs

### 2.1 Network Partition Scenarios

```
    ┌────────────────────────────────────────────────────────────────┐
    │                    DATA CENTER TOPOLOGY                         │
    │                                                                │
    │   Rack A              Core Switch             Rack B           │
    │  ┌───────┐          ┌───────────┐          ┌───────┐         │
    │  │Node 1 │──────┐   │           │   ┌──────│Node 3 │         │
    │  │Node 2 │──┐   └───│  SW-CORE  │───┘  ┌───│Node 4 │         │
    │  └───────┘  │       │           │      │   └───────┘         │
    │             └───────│     ╳     │──────┘                     │
    │                     │  FAILS!   │                             │
    │                     └───────────┘                             │
    │                                                                │
    │   Result: Rack A nodes cannot reach Rack B nodes              │
    └────────────────────────────────────────────────────────────────┘
```

### 2.2 Common Causes

| Cause | Mechanism | Detection Difficulty |
|-------|-----------|---------------------|
| Switch failure | Total L2/L3 path loss | Medium — monitoring catches it |
| Cable cut | Physical layer break | Easy if monitored |
| Firewall misconfiguration | Rule blocks cluster traffic | Hard — partial connectivity |
| NIC failure | One node loses connectivity | Medium |
| BGP route withdrawal | Inter-DC routing lost | Hard — slow convergence |
| Software bug in network stack | Packets silently dropped | Very Hard |
| GC pause (long STW) | Node appears dead, then revives | Very Hard |
| CPU saturation | Heartbeats delayed beyond timeout | Hard |

### 2.3 Asymmetric Partitions

The most insidious type — connectivity is not symmetric:

```
    ┌─────────────────────────────────────────────────┐
    │          ASYMMETRIC PARTITION                    │
    │                                                 │
    │     [Node A] ─────────────► [Node B]            │
    │         ▲         OK            │               │
    │         │                       │ OK            │
    │         │    ╳╳╳╳╳╳╳╳╳╳╳       ▼               │
    │     [Node C] ◄──── BLOCKED ──── [Node B]        │
    │                                                 │
    │     A → B: OK        B → C: OK                  │
    │     B → A: OK        C → A: BLOCKED             │
    │     A → C: OK        C → B: BLOCKED             │
    │                                                 │
    │  Node C thinks A and B are dead                 │
    │  Nodes A and B think C is dead                  │
    │  But A can still reach C!                       │
    └─────────────────────────────────────────────────┘
```

### 2.4 GC Pauses Causing False Failure Detection

```
    Timeline ─────────────────────────────────────────────►

    Node A (Leader):
    ║══════════╗                              ╔═══════════
    ║ Running  ║  ████████████████████████    ║ Running
    ║ normally ║  █ GC PAUSE (30 sec)  █    ║ "I'm still
    ║══════════╝  █ World stopped      █    ║  leader!"
                  █ No heartbeats sent █    ╚═══════════
                  ████████████████████████
                         ▲
    Node B (Follower):   │
    ║══════════╗         │ timeout!         ╔═══════════
    ║ Follower ║─────────┼─────────────────►║ NEW LEADER
    ║          ║  "A is dead, I'll take over"║ accepts
    ║══════════╝                            ║ writes!
                                            ╚═══════════

    *** TWO LEADERS NOW EXIST ***
    Node A wakes up, still thinks it's leader
    Node B was elected leader during pause
```

---

## 3. The Danger

### 3.1 Dual-Master Writes

When two nodes both accept writes as master, every operation creates potential conflict:

```
    Client 1 ──────► [Master A]          [Master B] ◄────── Client 2
                        │                     │
                        ▼                     ▼
                  INSERT user_id=7      INSERT user_id=7
                  name='Alice'          name='Bob'
                  balance=1000          balance=500
                        │                     │
                        ▼                     ▼
              ┌─────────────────┐   ┌─────────────────┐
              │  DB Partition 1  │   │  DB Partition 2  │
              │                 │   │                 │
              │  user 7: Alice  │   │  user 7: Bob    │
              │  bal: 1000      │   │  bal: 500       │
              └─────────────────┘   └─────────────────┘

    PARTITION HEALS:
    ┌──────────────────────────────────────────────┐
    │  Which state wins?                           │
    │  • user 7 = Alice with $1000?                │
    │  • user 7 = Bob with $500?                   │
    │  • Both? (violates unique constraint)        │
    │  • Neither? (data loss)                      │
    └──────────────────────────────────────────────┘
```

### 3.2 Categories of Damage

**Data Corruption and Divergence:**
- Auto-increment IDs collide across partitions
- Foreign key relationships become inconsistent
- Unique constraints violated (both sides insert same key)
- Sequence gaps or duplicates in event logs

**Resource Conflicts:**
- Two nodes claim the same distributed lock → mutual exclusion violated
- Two schedulers both run the same cron job → duplicate processing
- Two leaders both write to the same shared storage → file corruption

**Inconsistent Client Responses:**
- Client reads from partition A, gets balance=$1000
- Same client reads from partition B, gets balance=$500
- Violates linearizability — the system appears to go backwards in time

### 3.3 Real-World Horror Stories

**GitHub's 2012 MySQL Outage:**
A network partition caused their MySQL cluster to elect a new primary while the old primary was still accepting writes. When the partition healed, they had diverged binlogs. Result: ~5 hours of degraded service, manual data reconciliation, some data permanently lost.

**Azure Storage Outage (2012):**
A network configuration change caused a split-brain in the storage stamp. Both halves of the cluster continued serving requests. Recovery required manual intervention and some customer data was delayed by hours.

**Elasticsearch Production Incidents:**
Before `minimum_master_nodes` was properly understood, many teams lost data when ES clusters split and each half elected its own master, independently accepting indexing operations. Merging diverged Lucene segments is effectively impossible.

---

## 4. Detection Mechanisms

### 4.1 Heartbeat Timeouts and Their Limitations

```
    ┌──────────────────────────────────────────────────────┐
    │  SIMPLE HEARTBEAT DETECTION                          │
    │                                                      │
    │  Node A ──heartbeat──► Node B                        │
    │          (every 1s)                                   │
    │                                                      │
    │  If B doesn't hear from A for 5s → declare A dead   │
    │                                                      │
    │  PROBLEMS:                                           │
    │  ┌────────────────────────────────────────────────┐  │
    │  │ 1. Too short timeout → false positives         │  │
    │  │    (GC pause, network jitter)                  │  │
    │  │                                                │  │
    │  │ 2. Too long timeout → slow detection           │  │
    │  │    (5+ seconds of dual-master operation)       │  │
    │  │                                                │  │
    │  │ 3. Symmetric assumption → misses asymmetric    │  │
    │  │    partitions                                  │  │
    │  │                                                │  │
    │  │ 4. Binary decision → no probability model     │  │
    │  └────────────────────────────────────────────────┘  │
    └──────────────────────────────────────────────────────┘
```

### 4.2 Phi Accrual Failure Detector

Used by Akka, Cassandra, and other systems. Instead of a binary alive/dead decision, it outputs a **suspicion level** (φ) that increases over time without heartbeat.

```
    Suspicion Level (φ)
    │
    │                                          ╱ φ = 12 (definitely dead)
    │                                        ╱
    │                                      ╱
    │                              ╱──────╱ φ = 8 (very likely dead)
    │                            ╱
    │                     ╱─────╱
    │              ╱─────╱        φ = 5 (probably dead)
    │       ╱─────╱
    │╱─────╱                      φ = 3 (suspicious)
    │─────────────────────────── φ = 1 (normal jitter)
    └─────────────────────────────────────────────► Time since
                                                    last heartbeat

    Key insight: Uses HISTORICAL inter-arrival times to build
    a statistical model. Adapts to network conditions.

    P(dead | no heartbeat for t) = 1 - F(t)
    where F is the CDF of the normal distribution fitted
    to historical heartbeat intervals.

    φ = -log10(1 - F(timeSinceLastHeartbeat))
```

**Advantages over fixed timeout:**
- Self-tuning: adapts to network latency variations
- Configurable threshold: application decides acceptable φ
- Probabilistic: allows for gradual response (e.g., stop sending traffic before officially declaring dead)

### 4.3 Network Monitoring

| Method | What It Detects | Limitation |
|--------|----------------|------------|
| ICMP ping | L3 reachability | May be blocked by firewall; doesn't prove app-level connectivity |
| TCP probe | Port reachability | Connection may succeed but app frozen (GC) |
| Application-level heartbeat | Process liveness | Doesn't detect partial network issues |
| Multi-path probing | Asymmetric partitions | Complex to implement |
| Third-party witness | Who is actually isolated | Requires additional infrastructure |

**Multi-path probe pattern:**

```
    ┌────────────────────────────────────────────────┐
    │  Each node probes ALL other nodes AND a        │
    │  shared external witness:                      │
    │                                                │
    │  [Node A]──probe──►[Node B]                    │
    │     │ ╲              ▲                         │
    │     │  ╲probe       │probe                    │
    │     │   ╲          │                         │
    │     │    ▼        ╱                          │
    │     │  [Witness]◄╱                            │
    │     │      ▲                                  │
    │     │      │probe                             │
    │  probe     │                                  │
    │     ▼      │                                  │
    │  [Node C]──┘                                  │
    │                                                │
    │  If A can reach Witness but not B:            │
    │    → B is likely isolated (not A)             │
    │  If A cannot reach Witness OR B:              │
    │    → A is likely isolated                     │
    └────────────────────────────────────────────────┘
```

---

## 5. Prevention Strategies

### 5.1 Quorum / Majority Voting

The most fundamental split-brain prevention mechanism. Only the partition containing a **strict majority** (>N/2) of nodes is allowed to operate.

```
    ┌─────────────────────────────────────────────────────────────┐
    │  5-NODE CLUSTER WITH NETWORK PARTITION                       │
    │                                                             │
    │  ┌─────────────────────┐  ╳╳╳  ┌───────────────────────┐  │
    │  │  Partition LEFT      │      │  Partition RIGHT        │  │
    │  │                     │      │                         │  │
    │  │  [A] [B] [C]        │      │  [D] [E]                │  │
    │  │                     │      │                         │  │
    │  │  3 nodes = MAJORITY │      │  2 nodes = MINORITY     │  │
    │  │  (3 > 5/2 = 2.5)   │      │  (2 ≤ 5/2 = 2.5)       │  │
    │  │                     │      │                         │  │
    │  │  ✓ CAN OPERATE      │      │  ✗ MUST STOP            │  │
    │  │  ✓ Elects leader    │      │  ✗ Read-only or halt    │  │
    │  │  ✓ Accepts writes   │      │  ✗ Rejects writes       │  │
    │  └─────────────────────┘      └───────────────────────────┘  │
    │                                                             │
    │  QUORUM = ⌊N/2⌋ + 1 = 3                                    │
    └─────────────────────────────────────────────────────────────┘
```

**Why odd-number clusters:**

```
    Cluster Size │ Quorum │ Tolerated Failures │ Efficiency
    ─────────────┼────────┼────────────────────┼──────────
         3       │   2    │        1           │  33%
         4       │   3    │        1           │  25%  ← SAME as 3!
         5       │   3    │        2           │  40%
         6       │   4    │        2           │  33%  ← SAME as 5!
         7       │   4    │        3           │  43%

    Even-sized clusters waste a node:
    • 4-node cluster tolerates same failures as 3-node
    • 6-node cluster tolerates same failures as 5-node
    • The extra node adds cost but no resilience
```

**Why even-number clusters are dangerous — the 50/50 split:**

```
    4-NODE CLUSTER SPLITS EVENLY:

    ┌──────────────┐    ╳╳╳    ┌──────────────┐
    │  [A] [B]      │          │  [C] [D]      │
    │  2 nodes     │          │  2 nodes     │
    │  2 < 3 (Q)   │          │  2 < 3 (Q)   │
    │              │          │              │
    │  ✗ NO QUORUM │          │  ✗ NO QUORUM │
    └──────────────┘          └──────────────┘

    ENTIRE CLUSTER IS DOWN!
    Neither half can form quorum. Total availability loss.
    With a 5-node cluster, any 2-3 split preserves one functioning half.
```

### 5.2 Fencing (STONITH — Shoot The Other Node In The Head)

Fencing ensures that a node which *might* be operating as a rogue master is **forcibly stopped** before a new master takes over. The philosophy: "It's better to kill a potentially healthy node than risk dual-masters."

```
    ┌────────────────────────────────────────────────────────────┐
    │                    FENCING FLOW                             │
    │                                                            │
    │  1. Failure Detection                                      │
    │     [Node B]: "I haven't heard from A in 10s"             │
    │                                                            │
    │  2. Fencing BEFORE failover                                │
    │     [Node B] ──IPMI power-off──► [Node A's BMC]           │
    │                                                            │
    │  3. Confirmation                                           │
    │     [Node A's BMC]: "Power state: OFF"                    │
    │                                                            │
    │  4. ONLY NOW: Promote                                     │
    │     [Node B]: "I am the new master"                       │
    │                                                            │
    │                                                            │
    │   ┌─────────┐         ┌─────────┐        ┌─────────┐     │
    │   │ Node A  │         │  IPMI/  │        │ Node B  │     │
    │   │(suspect)│         │  BMC    │        │(new ldr)│     │
    │   └────┬────┘         └────┬────┘        └────┬────┘     │
    │        │                   │                   │          │
    │        │                   │◄──Power OFF cmd───│  (2)     │
    │        │                   │                   │          │
    │        │◄──POWER CUT──────│                   │          │
    │        │                   │                   │          │
    │        │   ╳╳╳ DEAD ╳╳╳   │───Confirm OFF────►│  (3)     │
    │        │                   │                   │          │
    │        │                   │                   │──►PROMOTE │
    │                                                    (4)     │
    └────────────────────────────────────────────────────────────┘
```

**Types of Fencing:**

| Type | Mechanism | Guarantee | Speed |
|------|-----------|-----------|-------|
| Power fencing (IPMI/iLO/DRAC) | Cuts power to entire server | Absolute — hardware off | 5-30s |
| Storage fencing (SCSI-3 PR) | Revokes disk access via persistent reservations | Node can't corrupt shared storage | <1s |
| Network fencing | Disables switch port or VLAN | Node can't communicate | 1-5s |
| Hypervisor fencing | VM power-off via vCenter/libvirt | VM destroyed | 1-5s |
| SBD (Storage-Based Death) | Poison pill on shared disk; node watches and self-terminates | Self-fencing | 1-5s |

**SCSI-3 Persistent Reservations (Storage Fencing):**

```
    ┌─────────────────────────────────────────────────────┐
    │  Shared SAN/Storage                                  │
    │  ┌─────────────────────────────────────────────┐    │
    │  │           LUN (shared disk)                  │    │
    │  │                                             │    │
    │  │  Reservation Key: Node_B_key               │    │
    │  │  Type: Write Exclusive - Registrants Only   │    │
    │  │                                             │    │
    │  │  Registered Keys:                          │    │
    │  │    • Node_B_key  ✓ (can write)             │    │
    │  │    • Node_A_key  ✗ (PREEMPTED/removed)     │    │
    │  └─────────────────────────────────────────────┘    │
    │           ▲                    ▲                     │
    │           │ WRITE OK           │ WRITE REJECTED      │
    │       [Node B]             [Node A]                  │
    │       (new master)         (fenced out)              │
    └─────────────────────────────────────────────────────┘

    Even if Node A is still running, it CANNOT write to storage.
    Any I/O from Node A returns RESERVATION CONFLICT.
```

### 5.3 Witness / Tie-Breaker Nodes

A witness is a lightweight node that doesn't hold data but participates in leader election to break ties.

```
    ┌────────────────────────────────────────────────────────────┐
    │                                                            │
    │   DC-West (Primary)          DC-East (Secondary)          │
    │  ┌───────────────┐          ┌───────────────┐            │
    │  │ [Data Node 1] │          │ [Data Node 3] │            │
    │  │ [Data Node 2] │          │ [Data Node 4] │            │
    │  └───────┬───────┘          └───────┬───────┘            │
    │          │                          │                    │
    │          │         DC-Witness       │                    │
    │          │       ┌───────────┐      │                    │
    │          └───────│ [Witness] │──────┘                    │
    │                  │  (no data)│                            │
    │                  │  votes    │                            │
    │                  │  only     │                            │
    │                  └───────────┘                            │
    │                   (Cloud/3rd DC)                          │
    │                                                            │
    │  If DC-West ╳ DC-East partition:                          │
    │    • DC-West + Witness = 3 votes → MAJORITY (operates)   │
    │    • DC-East alone = 2 votes → minority (stops)          │
    │                                                            │
    │  If DC-West fails entirely:                               │
    │    • DC-East + Witness = 3 votes → MAJORITY (failover)   │
    └────────────────────────────────────────────────────────────┘
```

**Cloud Witness implementations:**
- **Azure:** Cloud Witness for Windows Server Failover Clustering — blob lease in Azure Storage
- **AWS:** Use a small EC2 instance or DynamoDB conditional write as arbitrator
- **On-prem:** Lightweight VM in a third network zone

### 5.4 Lease-Based Leadership

A leader holds a **time-bounded lease** and must renew it before expiry. If it can't renew (network partition, GC pause), it must voluntarily step down.

```
    ┌────────────────────────────────────────────────────────────┐
    │  LEASE-BASED LEADERSHIP PROTOCOL                           │
    │                                                            │
    │  Time ──────────────────────────────────────────────►      │
    │                                                            │
    │  Leader A:                                                 │
    │  ├─── Lease granted (10s) ───┤                             │
    │  │    "I am leader"          │                             │
    │  │    Accepts writes         │ Must renew                  │
    │  │◄── Renew at 5s mark ─────►│ before here                │
    │  │                           │                             │
    │  │   IF renewal fails:       │                             │
    │  │   ┌─────────────────────┐ │                             │
    │  │   │ STEP DOWN           │ │                             │
    │  │   │ Stop accepting      │ │                             │
    │  │   │ writes immediately  │ │                             │
    │  │   └─────────────────────┘ │                             │
    │  │                           ▼                             │
    │  │                     LEASE EXPIRES                        │
    │  │                           │                             │
    │  │                     Other nodes may now                 │
    │  │                     attempt to acquire lease            │
    │                                                            │
    │  CRITICAL INVARIANT:                                       │
    │  Leader stops BEFORE lease expires (safety margin)         │
    │  New leader starts AFTER lease expires                     │
    │  → No overlap of authority                                 │
    └────────────────────────────────────────────────────────────┘
```

**Clock skew problem:** If Leader A's clock runs slow and Leader B's clock runs fast, their lease windows can overlap. Solution: use **bounded clock skew** assumptions or **consensus-based lease** (Raft/Paxos grant the lease, not wall-clock alone).

---

## 6. Recovery from Split Brain

### 6.1 Detecting Diverged State

When a partition heals, the system must detect that divergence occurred:

```
    ┌────────────────────────────────────────────────────────────┐
    │  PARTITION HEALS — DIVERGENCE DETECTION                    │
    │                                                            │
    │  Node A (was master in left partition):                    │
    │    Epoch: 5                                                │
    │    Last LSN: 10042                                         │
    │    WAL: ...→10040→10041→10042                              │
    │                                                            │
    │  Node B (was master in right partition):                   │
    │    Epoch: 5  (SAME! — split brain occurred)                │
    │    Last LSN: 10038                                         │
    │    WAL: ...→10035→10036→10037→10038                        │
    │                                                            │
    │  Detection signals:                                        │
    │    • Same epoch, different WAL contents after branch point │
    │    • Timeline/history divergence (PostgreSQL timeline IDs) │
    │    • Vector clock conflicts                                │
    │    • Merkle tree root hash mismatch                        │
    └────────────────────────────────────────────────────────────┘
```

### 6.2 Merge Strategies

| Strategy | When to Use | Risk |
|----------|-------------|------|
| **Last-Writer-Wins (LWW)** | Stateless caches, non-critical data | Silent data loss |
| **Manual reconciliation** | Financial data, critical state | Slow, requires human |
| **Application-level merge** | CRDTs, domain-specific logic | Complex to implement |
| **Discard minority partition** | Partition had no quorum (shouldn't have accepted writes) | Data loss for rogue writes |
| **Keep both (multi-value)** | Shopping carts (Amazon Dynamo style) | Pushes complexity to client |

**Conflict resolution decision tree:**

```
    Partition heals
         │
         ▼
    Did both sides accept writes?
         │
    ┌────┴────┐
    │YES      │NO → Simple: catch up the
    │         │     stale side from the
    │         │     authoritative side
    ▼
    Can conflicts be automatically resolved?
         │
    ┌────┴────┐
    │YES      │NO
    │         │
    ▼         ▼
    Apply     Flag for manual review.
    merge     Alert on-call engineer.
    rules     Provide diff of diverged state.
    (CRDTs,
    LWW,
    app logic)
```

### 6.3 Data Reconciliation Approaches

**Timeline-based (PostgreSQL/Patroni):**
- Each promotion creates a new timeline ID
- After partition heals, the "losing" node rewinds its WAL to the branch point
- Replays from the winning timeline
- Writes on the losing timeline are lost (but logged for audit)

**Vector clocks (Dynamo-style):**
- Each write carries a vector clock
- Conflicting versions are stored as siblings
- Application resolves on next read

**CRDTs (Conflict-Free Replicated Data Types):**
- Data structures designed so concurrent operations commute
- G-Counter, PN-Counter, OR-Set, LWW-Register
- Merge is always possible without data loss
- Limitation: not all data models can be expressed as CRDTs

---

## 7. Real-World Case Studies

### 7.1 Elasticsearch — Multiple Master Split Brain

**The Problem:**
ES uses a master-eligible node election. Before v7, if `minimum_master_nodes` was misconfigured, a network partition could result in two separate masters, each independently accepting index operations.

```
    ┌─────────────────────────────────────────────────────────┐
    │  ES CLUSTER (5 nodes, minimum_master_nodes=1 — BAD!)    │
    │                                                         │
    │  ┌──────────────┐    ╳╳╳    ┌──────────────────┐       │
    │  │ Node1(master)│           │ Node3            │       │
    │  │ Node2        │           │ Node4            │       │
    │  │              │           │ Node5(new master)│       │
    │  │ Indexes docs │           │ Indexes docs    │       │
    │  └──────────────┘           └──────────────────┘       │
    │                                                         │
    │  FIX: minimum_master_nodes = (N/2) + 1 = 3            │
    │  ES 7.0+: Automatic with voting configuration          │
    └─────────────────────────────────────────────────────────┘
```

**Resolution in ES 7+:** Replaced Zen Discovery with a proper Raft-like consensus protocol. Cluster automatically manages voting configuration. Split brain is structurally impossible with the new implementation.

### 7.2 Kafka — Controller Split Brain and Epoch Fencing

**The Problem:**
Kafka has a single controller broker responsible for partition leadership. If the controller appears dead (GC pause), ZooKeeper elects a new controller. The old one may wake up and issue stale commands.

**Solution — Epoch-based fencing (Controller Epoch):**

```
    ┌────────────────────────────────────────────────────────────┐
    │  KAFKA CONTROLLER FENCING                                  │
    │                                                            │
    │  Controller A (epoch=5) ──GC pause──► appears dead         │
    │                                                            │
    │  ZooKeeper elects Controller B (epoch=6)                   │
    │                                                            │
    │  Controller A wakes up, sends:                             │
    │    LeaderAndIsrRequest(epoch=5, ...)                       │
    │                                                            │
    │  Broker receives request:                                  │
    │    "Current controller epoch is 6, got request with 5"    │
    │    → REJECT (stale controller)                            │
    │                                                            │
    │  Controller B sends:                                       │
    │    LeaderAndIsrRequest(epoch=6, ...)                       │
    │    → ACCEPT                                                │
    │                                                            │
    │  Epoch monotonically increases. Old controller's           │
    │  commands are permanently fenced out.                      │
    └────────────────────────────────────────────────────────────┘
```

**KRaft (Kafka Raft, ZooKeeper-less):**
In Kafka 3.3+, the controller quorum uses Raft consensus directly, eliminating ZooKeeper as a dependency and providing stronger split-brain protection through log-based consensus.

### 7.3 PostgreSQL — Patroni's Approach

Patroni uses a **DCS (Distributed Configuration Store)** like etcd/ZooKeeper/Consul to manage leader election with TTL-based leases:

```
    ┌────────────────────────────────────────────────────────────┐
    │  PATRONI SPLIT BRAIN PREVENTION                            │
    │                                                            │
    │  [Primary PG]──heartbeat──►[etcd cluster]◄──[Replica PG]  │
    │       │                        │                  │        │
    │       │  Holds leader key      │                  │        │
    │       │  with 30s TTL          │                  │        │
    │       │                        │                  │        │
    │  If Primary loses etcd:        │                  │        │
    │    1. Cannot renew leader key  │                  │        │
    │    2. TTL expires (30s)        │                  │        │
    │    3. Primary DEMOTES SELF     │                  │        │
    │       (pg_ctl promote → off)   │                  │        │
    │    4. Replica acquires key     │                  │        │
    │    5. Replica promotes         │                  │        │
    │                                                            │
    │  WATCHDOG INTEGRATION:                                     │
    │  If Patroni process crashes on primary, Linux watchdog     │
    │  reboots the server (hardware fencing equivalent)          │
    └────────────────────────────────────────────────────────────┘
```

**Key insight:** Patroni makes the primary *continuously prove* it deserves to be primary. No proof → automatic demotion.

### 7.4 MongoDB — Replica Set Elections

MongoDB uses a Raft-inspired protocol for replica set elections:

- **Odd-number voting members** (1, 3, 5, 7 — max 7 voters)
- **Election requires strict majority** of votes
- **Term numbers** (epochs) fence stale primaries
- **Write concern `majority`** ensures writes survive failover

```
    ┌──────────────────────────────────────────────────────┐
    │  MONGODB REPLICA SET (3 members)                     │
    │                                                      │
    │  [Primary]◄────────►[Secondary]◄────────►[Secondary] │
    │   term=5              term=5              term=5     │
    │                                                      │
    │  Partition isolates primary:                         │
    │                                                      │
    │  [Primary]     ╳╳╳    [Secondary]◄────►[Secondary]  │
    │   term=5               term=5           term=5      │
    │   steps down           elects new primary           │
    │   (no majority)        (has majority: 2/3)          │
    │                        term=6                       │
    │                                                      │
    │  Old primary with term=5 rejects writes:            │
    │  "I don't have majority, switching to secondary"    │
    └──────────────────────────────────────────────────────┘
```

### 7.5 etcd / ZooKeeper — Consensus Prevents Split Brain

These systems use Raft (etcd) or ZAB (ZooKeeper) consensus protocols which make split brain **structurally impossible** by construction:

```
    ┌────────────────────────────────────────────────────────────┐
    │  WHY RAFT PREVENTS SPLIT BRAIN                             │
    │                                                            │
    │  Fundamental rule: A leader must replicate a log entry     │
    │  to a MAJORITY before committing it.                       │
    │                                                            │
    │  5-node cluster, partition splits 2|3:                     │
    │                                                            │
    │  ┌─────────┐  ╳╳╳  ┌─────────────────────┐               │
    │  │ A, B    │       │ C (leader), D, E    │               │
    │  │         │       │                     │               │
    │  │ Cannot  │       │ Replicates to D,E   │               │
    │  │ elect   │       │ = 3 nodes = majority│               │
    │  │ leader  │       │ → commits OK        │               │
    │  │ (need 3)│       │                     │               │
    │  └─────────┘       └─────────────────────┘               │
    │                                                            │
    │  Even if A or B was the old leader:                       │
    │  • Cannot commit (can't reach majority)                   │
    │  • Client writes TIMEOUT (not silently accepted!)         │
    │  • After partition heals, A/B catch up from C's log       │
    │                                                            │
    │  No data divergence possible.                             │
    └────────────────────────────────────────────────────────────┘
```

### 7.6 Redis Sentinel — Quorum-Based Failover

```
    ┌────────────────────────────────────────────────────────────┐
    │  REDIS SENTINEL ARCHITECTURE                               │
    │                                                            │
    │  [Sentinel 1]    [Sentinel 2]    [Sentinel 3]             │
    │       │               │               │                   │
    │       ▼               ▼               ▼                   │
    │  [Redis Master] ─── repl ──► [Redis Replica]              │
    │                                                            │
    │  Failover requires:                                        │
    │  1. SDOWN: One sentinel thinks master is down             │
    │  2. ODOWN: quorum sentinels agree (e.g., 2/3)            │
    │  3. Sentinel leader election (Raft-like)                  │
    │  4. Leader sentinel performs failover                     │
    │                                                            │
    │  Split-brain risk:                                         │
    │  If old master is partitioned but still accepts writes    │
    │  → Use min-replicas-to-write=1 to prevent this           │
    │    (master refuses writes if no replica is connected)     │
    └────────────────────────────────────────────────────────────┘
```

**`min-replicas-to-write`** is Redis's built-in split-brain protection: the master stops accepting writes if it can't replicate to at least N replicas. A partitioned master with no reachable replicas becomes read-only.

### 7.7 GitHub's 2012 Outage

**Timeline:**
1. Network maintenance caused a brief partition between MySQL primary and replicas
2. Automated failover promoted a replica to primary
3. Old primary came back online and was still accepting writes (automation bug)
4. Two primaries operated simultaneously for several minutes
5. Application wrote to both — auto-increment IDs diverged, foreign keys broke
6. Manual intervention required to identify "winning" primary
7. Diverged writes on the losing primary had to be manually replayed or discarded
8. ~5 hours of degraded service

**Lessons:**
- Fencing must happen BEFORE promotion, not after
- "Demote old primary" is not sufficient — it must be forcibly killed
- Auto-increment collisions are a clear signal of split brain
- Monitoring should alert on duplicate primary detection

---

## 8. Network Partition Taxonomy

### 8.1 Complete Partition

Every node in group A cannot communicate with any node in group B.

```
    ┌──────────────────┐         ┌──────────────────┐
    │  Group A         │  ╳╳╳╳╳  │  Group B         │
    │                  │         │                  │
    │  [1]◄──►[2]     │  TOTAL  │  [3]◄──►[4]     │
    │   ▲      ▲      │  BREAK  │   ▲      ▲      │
    │   └──────┘      │         │   └──────┘      │
    │  Internal OK     │         │  Internal OK     │
    └──────────────────┘         └──────────────────┘

    Properties:
    • Symmetric: A can't reach B, B can't reach A
    • Clean: No ambiguity about partition membership
    • Quorum works well here
```

### 8.2 Partial Partition

Some cross-partition communication works, but not all paths.

```
    ┌────────────────────────────────────────────────────┐
    │  PARTIAL PARTITION                                  │
    │                                                    │
    │  [Node 1] ◄─────────────────────► [Node 2]        │
    │      ▲                                ▲           │
    │      │                                │           │
    │      │ OK                             │ OK        │
    │      │                                │           │
    │      ▼         ╳╳╳ BROKEN ╳╳╳         ▼           │
    │  [Node 3] ◄─────────────────────► [Node 4]        │
    │      ▲                                ▲           │
    │      │ OK                             │ OK        │
    │      ▼                                ▼           │
    │  [Node 5] ◄─────────────────────► [Node 6]        │
    │                    OK                             │
    │                                                    │
    │  Only the 3↔4 link is broken.                     │
    │  Every other pair can communicate.                │
    │  Quorum still works (all nodes see majority).     │
    │  But: 3 routes through 4 are broken.             │
    └────────────────────────────────────────────────────┘
```

### 8.3 Asymmetric Partition

Connectivity is directional — A can reach B, but B cannot reach A.

```
    ┌────────────────────────────────────────────────────┐
    │  ASYMMETRIC PARTITION                              │
    │                                                    │
    │  [Node A] ════════════► [Node B]                   │
    │           packets flow                            │
    │                                                    │
    │  [Node A] ◄╳╳╳╳╳╳╳╳╳╳╳ [Node B]                   │
    │           blocked (e.g., firewall                 │
    │           rule, asymmetric routing)               │
    │                                                    │
    │  Node A's perspective: "B is alive (I see ACKs    │
    │    from established connections but new           │
    │    connections from B fail)"                      │
    │                                                    │
    │  Node B's perspective: "A is dead (no responses   │
    │    to my probes)"                                │
    │                                                    │
    │  This is the HARDEST partition to handle:         │
    │  • Heartbeat direction matters                   │
    │  • B may try to elect itself leader              │
    │  • A doesn't know it's been declared dead        │
    └────────────────────────────────────────────────────┘
```

**Causes of asymmetric partitions:**
- Stateful firewall rules (allow established, block new)
- Unidirectional fiber failure
- NIC with working TX but broken RX (or vice versa)
- Asymmetric routing where forward/return paths differ

---

## 9. Architect's Playbook

### Design Patterns to Prevent and Handle Split Brain

#### Pattern 1: Consensus-First Architecture

```
    DO:  All coordination through consensus system
    ┌─────────────────────────────────────────────┐
    │  [App Nodes] ──► [etcd/ZK] ──► [Decision]  │
    │                                             │
    │  Leader election: consensus-based           │
    │  Config changes: consensus-based            │
    │  Membership: consensus-based                │
    └─────────────────────────────────────────────┘

    DON'T: Ad-hoc peer-to-peer failure detection
    ┌─────────────────────────────────────────────┐
    │  [Node A]──"are you alive?"──►[Node B]      │
    │     │                                       │
    │     └──"B is dead, I'm taking over"         │
    │        (DANGEROUS without fencing!)          │
    └─────────────────────────────────────────────┘
```

#### Pattern 2: Fence-Then-Promote (Never Promote Without Fencing)

```
    CORRECT ORDER:
    1. Detect failure        ──► "Node A might be dead"
    2. FENCE Node A          ──► "Node A is DEFINITELY stopped"
    3. Promote Node B        ──► "Node B is the new leader"

    WRONG ORDER:
    1. Detect failure        ──► "Node A might be dead"
    2. Promote Node B        ──► "Node B is leader... but so is A?"
    3. Try to fence Node A   ──► TOO LATE — both accepted writes
```

#### Pattern 3: Self-Fencing / Cooperative Demotion

Nodes must be programmed to **voluntarily step down** when they cannot prove they have authority:

```python
# Pseudocode for self-fencing leader
while True:
    lease = renew_lease(ttl=10s)
    if lease.failed():
        # IMMEDIATELY stop serving writes
        demote_to_readonly()
        close_all_client_connections()
        log.critical("Lost lease, self-demoting")
        break
    sleep(lease.ttl / 3)  # Renew at 1/3 of TTL
```

#### Pattern 4: Monotonic Epoch/Term Fencing Tokens

Every leader election increments a monotonic counter. All operations carry this token. Services reject operations with stale tokens.

```
    ┌────────────────────────────────────────────────────────┐
    │  FENCING TOKEN PATTERN                                 │
    │                                                        │
    │  Leader A (token=33) ──write(token=33)──► [Storage]    │
    │                                              │         │
    │  A partitioned, B elected with token=34      │         │
    │                                              │         │
    │  Leader B (token=34) ──write(token=34)──► [Storage]    │
    │                                              │         │
    │  A comes back:                               │         │
    │  Leader A (token=33) ──write(token=33)──► [Storage]    │
    │                                              │         │
    │  Storage: "Seen token 34, rejecting 33"     │         │
    │           → REJECTED                         │         │
    └────────────────────────────────────────────────────────┘
```

#### Pattern 5: Multi-Datacenter Quorum Placement

```
    ┌────────────────────────────────────────────────────────────┐
    │  RECOMMENDED: 3-DC deployment (2+2+1 or 3+2+2)            │
    │                                                            │
    │   DC-A (primary)     DC-B (secondary)    DC-C (witness)   │
    │  ┌──────────────┐  ┌──────────────┐   ┌────────────┐     │
    │  │ Node 1       │  │ Node 3       │   │ Node 5     │     │
    │  │ Node 2       │  │ Node 4       │   │ (witness)  │     │
    │  └──────────────┘  └──────────────┘   └────────────┘     │
    │                                                            │
    │  Any single DC failure → remaining 2 DCs have majority    │
    │  DC-A down: nodes 3,4,5 = 3/5 = majority ✓               │
    │  DC-B down: nodes 1,2,5 = 3/5 = majority ✓               │
    │  DC-C down: nodes 1,2,3,4 = 4/5 = majority ✓             │
    │                                                            │
    │  ANTI-PATTERN: 2-DC deployment (no witness)               │
    │  DC-A ╳ DC-B → neither has majority → total outage        │
    └────────────────────────────────────────────────────────────┘
```

#### Pattern 6: Defense in Depth

No single mechanism is sufficient. Layer multiple protections:

```
    ┌────────────────────────────────────────────┐
    │  LAYER 1: Consensus (Raft/Paxos)          │ ← Structural prevention
    │  LAYER 2: Lease-based leadership          │ ← Time-bounded authority
    │  LAYER 3: Fencing tokens (epochs)         │ ← Stale command rejection
    │  LAYER 4: STONITH/power fencing           │ ← Hardware guarantee
    │  LAYER 5: Application-level guards        │ ← Last line of defense
    │           (e.g., min-replicas-to-write)   │
    └────────────────────────────────────────────┘
```

#### Checklist for Split-Brain Resilient Design

- [ ] **Odd number of voter nodes** (3, 5, or 7)
- [ ] **Quorum requirement for all writes** (not just elections)
- [ ] **Fencing mechanism deployed and tested** (test it regularly!)
- [ ] **Leader lease with voluntary step-down**
- [ ] **Monotonic epoch/term in all leader commands**
- [ ] **Storage-layer fencing tokens** (reject stale writes)
- [ ] **Multi-path failure detection** (not just one heartbeat channel)
- [ ] **Witness node in third failure domain**
- [ ] **Monitoring: alert on multiple leaders** (dual-primary detection)
- [ ] **Runbook: tested recovery procedure for split-brain events**
- [ ] **Regular chaos testing** (partition injection in staging)
- [ ] **Client-side awareness** (retry with leader discovery, not blind retry)

---

## Summary

| Approach | Prevents Split Brain? | Requires Extra Infra? | Complexity |
|----------|----------------------|----------------------|------------|
| Quorum voting | Yes (structural) | No | Low |
| STONITH fencing | Yes (physical) | Yes (BMC/IPMI) | Medium |
| Witness node | Yes (tie-breaking) | Yes (3rd site) | Low |
| Lease-based leadership | Yes (time-bounded) | Consensus store | Medium |
| Fencing tokens/epochs | Mitigates (stale rejection) | No | Low |
| CRDTs | No (tolerates it) | No | High |
| `min-replicas-to-write` | Mitigates | No | Low |

**The fundamental law:** In a distributed system, you cannot distinguish "slow" from "dead." Split brain exists because of this ambiguity. Every solution above is a different approach to making a safe decision under this uncertainty — either by requiring majority agreement, physically killing the ambiguous node, or bounding the time window of uncertainty with leases.
