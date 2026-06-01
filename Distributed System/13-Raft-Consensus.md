# 13 — Raft Consensus Algorithm

## 1. Motivation

Paxos (Lamport, 1989) is the foundational consensus algorithm, but its specification is notoriously difficult to understand and even harder to implement correctly. Real systems built on Paxos (Chubby, Spanner) required significant engineering beyond the paper.

**Raft** (Ongaro & Ousterhout, Stanford, 2014) was designed explicitly for **understandability** while providing the same safety guarantees as Multi-Paxos:

- **Agreement**: All non-faulty nodes agree on the same sequence of commands.
- **Validity**: Only proposed values can be decided.
- **Termination**: The system eventually makes progress (liveness, given a stable leader).
- **Fault tolerance**: Tolerates ⌊(n-1)/2⌋ failures in a cluster of n nodes.

The key insight: decompose consensus into independent, understandable sub-problems rather than presenting a monolithic protocol.

---

## 2. Key Decomposition

Raft separates consensus into three nearly-independent sub-problems:

```
┌─────────────────────────────────────────────────────────┐
│                   RAFT CONSENSUS                         │
├───────────────────┬──────────────────┬──────────────────┤
│  Leader Election  │  Log Replication │     Safety       │
│                   │                  │                  │
│  • Who leads?     │  • How to copy   │  • Commitment    │
│  • Term numbers   │    log entries?  │    rules         │
│  • Majority vote  │  • Consistency   │  • Election      │
│                   │    guarantees    │    restriction   │
└───────────────────┴──────────────────┴──────────────────┘
```

Each sub-problem can be understood, reasoned about, and tested independently. This is what makes Raft implementable by mortals.

Additionally, Raft addresses:
- **Log compaction** (snapshotting)
- **Membership changes** (cluster reconfiguration)

---

## 3. Node States

Every node in a Raft cluster is in exactly one of three states:

```
                    ┌──────────────────────────────────────────┐
                    │                                          │
                    ▼                                          │
            ┌─────────────┐    election timeout    ┌──────────┴───┐
 starts ──▶ │  FOLLOWER   │ ─────────────────────▶ │  CANDIDATE   │
 up         └─────────────┘                        └──────────────┘
                    ▲                                  │       │
                    │                                  │       │
                    │  discovers current leader        │       │ receives majority
                    │  or higher term                  │       │ votes
                    │                                  │       │
                    │          election timeout        │       ▼
                    │          (new election)          │  ┌──────────┐
                    │◀─────────────────────────────────┘  │  LEADER  │
                    │                                     └──────────┘
                    │                                          │
                    └──────────────────────────────────────────┘
                          discovers higher term
```

### State Descriptions

| State | Behavior |
|-------|----------|
| **Follower** | Passive. Responds to RPCs from leaders and candidates. If no heartbeat received within election timeout, becomes candidate. |
| **Candidate** | Active. Increments term, votes for self, sends RequestVote RPCs. Wins, loses, or times out. |
| **Leader** | Active. Sends AppendEntries RPCs (heartbeats + log entries). Only one leader per term. Handles all client requests. |

### Invariant: At Most One Leader Per Term

A term is a logical time period. Each term has at most one leader because:
1. A candidate needs majority votes to win.
2. Each node votes for at most one candidate per term.
3. Two majorities in the same cluster must overlap by at least one node.
4. That overlapping node cannot vote for two different candidates in the same term.

```
Time ──────────────────────────────────────────────────────────▶

 Term 1          Term 2          Term 3          Term 4
┌───────────┐   ┌───────────┐   ┌───────┐     ┌───────────────┐
│  Leader A │   │  Leader B │   │ split │     │   Leader C    │
│           │   │           │   │ vote  │     │               │
└───────────┘   └───────────┘   │(no    │     └───────────────┘
                                │leader)│
                                └───────┘
```

---

## 4. Leader Election in Detail

### 4.1 Election Timeout

Each follower maintains a randomized **election timeout** (typically 150–300ms). If no AppendEntries RPC (heartbeat) is received before this timeout expires, the follower assumes the leader has failed and transitions to candidate.

The randomization is critical: it ensures that in most cases, only one follower times out first and wins the election before others start competing.

### 4.2 Term Numbers

Terms act as a **logical clock** for the cluster:

- Every RPC includes the sender's current term.
- If a node receives an RPC with a higher term, it immediately updates its term and reverts to follower.
- If a node receives an RPC with a stale (lower) term, it rejects the RPC.
- Candidates increment the term when starting an election.

### 4.3 RequestVote RPC

```
RequestVote RPC:
┌─────────────────────────────────┐
│  term           - candidate's term
│  candidateId    - who is requesting
│  lastLogIndex   - index of candidate's last log entry
│  lastLogTerm    - term of candidate's last log entry
└─────────────────────────────────┘

Response:
┌─────────────────────────────────┐
│  term           - responder's current term (for candidate to update)
│  voteGranted    - true if vote given
└─────────────────────────────────┘
```

**Vote granting rules:**
1. Candidate's term ≥ voter's current term.
2. Voter has not already voted for another candidate in this term (or voted for this candidate).
3. Candidate's log is **at least as up-to-date** as voter's log (safety restriction — see §6).

### 4.4 Election Process — Timing Diagram

```
Time ─────────────────────────────────────────────────────────────▶

Node A (Follower):  ──────[timeout]──▶ Candidate (term=2)
                                       │
                                       ├── RequestVote ──▶ Node B
                                       ├── RequestVote ──▶ Node C
                                       ├── RequestVote ──▶ Node D
                                       └── RequestVote ──▶ Node E
                                       
Node B:  ◀── RequestVote ── grants vote ──▶ (term=2, voteGranted=true)
Node C:  ◀── RequestVote ── grants vote ──▶ (term=2, voteGranted=true)
Node D:  ◀── RequestVote ── grants vote ──▶ (term=2, voteGranted=true)
Node E:  ◀── RequestVote ── (hasn't responded yet)

Node A receives 3 votes + self = 4/5 majority → becomes LEADER (term=2)
         │
         ├── AppendEntries (heartbeat) ──▶ Node B
         ├── AppendEntries (heartbeat) ──▶ Node C
         ├── AppendEntries (heartbeat) ──▶ Node D
         └── AppendEntries (heartbeat) ──▶ Node E
```

### 4.5 Split Vote Resolution

If two candidates start elections simultaneously and split the vote (neither gets majority), both time out. Each picks a **new random timeout** and retries. The randomization makes repeated splits astronomically unlikely.

```
Term 5 (split vote):
  Node A: candidate, gets votes from B       (2/5 - not majority)
  Node C: candidate, gets votes from D       (2/5 - not majority)
  Node E: hasn't voted yet / network delay

  Both timeout → increment to term 6
  Node A: new random timeout = 230ms
  Node C: new random timeout = 170ms  ← times out first, wins term 6
```

### 4.6 Pre-Vote Optimization (Raft §9.6)

**Problem**: A partitioned node repeatedly times out, increments its term, and when it rejoins, its inflated term disrupts the cluster (forces leader to step down even though cluster was healthy).

**Solution — PreVote phase**: Before incrementing its term, a candidate sends a PreVote RPC. It only proceeds to a real election if a majority responds that they *would* vote for it. A node with a current leader that's still sending heartbeats will not grant a PreVote.

```
PreVote flow:
  Node X (partitioned, term=5, rejoins cluster at term=3):
  
  WITHOUT PreVote:
    X starts election term=6 → forces leader (term=3) to step down → disruption
  
  WITH PreVote:
    X sends PreVote(term=6) → other nodes have active leader → reject
    X does NOT increment term → no disruption
```

Implemented in etcd/raft, TiKV, and most production systems.

---

## 5. Log Replication

### 5.1 Log Structure

Each log entry contains:

```
┌────────┬──────┬─────────────────┐
│ Index  │ Term │    Command      │
├────────┼──────┼─────────────────┤
│   1    │  1   │  SET x = 1      │
│   2    │  1   │  SET y = 9      │
│   3    │  1   │  SET x = 2      │
│   4    │  2   │  SET z = 3      │
│   5    │  3   │  SET x = 5      │
│   6    │  3   │  DEL y          │
└────────┴──────┴─────────────────┘
         commitIndex = 5
```

- **Index**: Position in the log (monotonically increasing).
- **Term**: The term when the entry was created (used for consistency checks).
- **Command**: The state machine command to apply.

### 5.2 AppendEntries RPC

```
AppendEntries RPC:
┌────────────────────────────────────────────────────────┐
│  term              - leader's term                      │
│  leaderId          - so followers can redirect clients  │
│  prevLogIndex      - index of entry preceding new ones  │
│  prevLogTerm       - term of prevLogIndex entry         │
│  entries[]         - log entries to append (empty = heartbeat) │
│  leaderCommit      - leader's commitIndex               │
└────────────────────────────────────────────────────────┘

Response:
┌────────────────────────────────────────────────────────┐
│  term              - responder's term                   │
│  success           - true if follower matched prevLog   │
└────────────────────────────────────────────────────────┘
```

### 5.3 Replication Flow

```
Client          Leader (S1)         S2          S3          S4          S5
  │                 │                │           │           │           │
  │── SET x=7 ────▶│                │           │           │           │
  │                 │                │           │           │           │
  │                 │─── Append to local log     │           │           │
  │                 │    [idx=7, term=3, SET x=7]│           │           │
  │                 │                │           │           │           │
  │                 │──AppendEntries─▶           │           │           │
  │                 │──AppendEntries──────────────▶          │           │
  │                 │──AppendEntries──────────────────────────▶          │
  │                 │──AppendEntries──────────────────────────────────────▶
  │                 │                │           │           │           │
  │                 │◀──── success ──┘           │           │           │
  │                 │◀──── success ──────────────┘           │           │
  │                 │                            (2 + self = 3/5 majority)
  │                 │                │           │           │           │
  │                 │─── COMMIT entry (advance commitIndex)  │           │
  │                 │─── Apply to state machine  │           │           │
  │                 │                │           │           │           │
  │◀── OK (x=7) ───┤                │           │           │           │
  │                 │                │           │           │           │
  │                 │── next heartbeat includes leaderCommit=7           │
  │                 │    (followers apply committed entries)             │
```

### 5.4 Log Matching Property

Raft maintains two invariants:

1. **If two entries in different logs have the same index and term, they store the same command.** (Leaders create at most one entry per index per term.)

2. **If two entries in different logs have the same index and term, all preceding entries are identical.** (AppendEntries consistency check via prevLogIndex/prevLogTerm.)

### 5.5 Handling Log Inconsistencies

After a leader change, followers may have:
- **Missing entries** (follower was down)
- **Extra uncommitted entries** (from a deposed leader)
- **Both** (missing some, has extraneous others)

The leader's log is authoritative. It repairs followers by finding the latest matching entry and overwriting everything after.

```
Leader Log (term 3):
  [1:1] [2:1] [3:1] [4:2] [5:3] [6:3] [7:3]

Follower A (was down):
  [1:1] [2:1] [3:1] [4:2]
  
  Repair: Leader sends entries 5,6,7 → follower appends

Follower B (stale leader entries):
  [1:1] [2:1] [3:1] [4:2] [5:2] [6:2]
                                 ▲
                     These are from old term 2, never committed

  Repair: Leader's AppendEntries with prevLogIndex=4, prevLogTerm=2
          Follower deletes entries 5,6 and appends leader's 5,6,7

Follower C (worst case - missed entries AND has stale ones):
  [1:1] [2:1] [3:1] [4:3] [5:3]
                      ▲
           Diverges at index 4 (term 3 vs leader's term 2)

  Repair: Leader decrements nextIndex until match found at index 3
          Follower deletes 4,5 and receives leader's 4,5,6,7
```

### 5.6 nextIndex Backtracking

The leader maintains `nextIndex[i]` for each follower — the next log index to send. On rejection, it decrements:

```
Leader's view of Follower C:
  nextIndex[C] = 8  →  AppendEntries(prevLogIndex=7) → rejected
  nextIndex[C] = 7  →  AppendEntries(prevLogIndex=6) → rejected
  nextIndex[C] = 6  →  AppendEntries(prevLogIndex=5) → rejected
  ...
  nextIndex[C] = 4  →  AppendEntries(prevLogIndex=3, prevLogTerm=1) → success!
  
  Now send entries 4,5,6,7 → follower overwrites and catches up
```

**Optimization**: Follower returns `conflictTerm` and `conflictIndex` in rejection, allowing leader to skip entire conflicting terms in one round-trip.

---

## 6. Safety Properties

### 6.1 Election Restriction

A candidate can only win an election if its log is **at least as up-to-date** as a majority of nodes.

"Up-to-date" comparison:
1. Compare last log entry terms. Higher term wins.
2. If terms equal, longer log wins.

```
Comparison examples:

  Candidate A: last entry (index=5, term=3)
  Voter B:     last entry (index=7, term=2)
  
  A wins: term 3 > term 2, so A is "more up-to-date"
  B grants vote to A.

  Candidate X: last entry (index=5, term=3)
  Voter Y:     last entry (index=6, term=3)
  
  Y wins: same term, Y has longer log
  Y does NOT grant vote to X.
```

This ensures any elected leader contains all committed entries from previous terms.

### 6.2 Leader Completeness Property

**If a log entry is committed in a given term, that entry will be present in the logs of all leaders for all higher-numbered terms.**

Proof sketch:
- A committed entry was replicated to a majority.
- A new leader must receive votes from a majority.
- The two majorities overlap by at least one node.
- The election restriction ensures the new leader's log includes all committed entries.

### 6.3 State Machine Safety

**If a server has applied a log entry at a given index to its state machine, no other server will ever apply a different log entry for that index.**

This follows from:
- Log Matching Property (same index+term = same command)
- Leader Completeness (committed entries survive leader changes)
- Leaders never overwrite their own logs

### 6.4 Commitment Rule for Previous Terms

A subtle safety issue: a leader cannot commit entries from previous terms by merely counting replicas. It must commit an entry from its **own** term first, which implicitly commits all preceding entries.

```
Dangerous scenario (prevented by Raft):

  Time 1: Leader (term 2) creates entry at index 3
  Time 2: Entry replicated to S1, S2 (not yet majority)
  Time 3: Leader crashes
  Time 4: New leader (term 3) has entry at index 3 from term 2
           Replicates it to S3 (now on majority: S1, S2, S3)
           CAN IT COMMIT? NO! Not safe yet.
  
  Why? Another node might have a different entry at index 3 from term 2
  and could win election (if it has a higher-term entry elsewhere).
  
  Solution: Leader in term 3 must first commit an entry FROM term 3.
  Once a term-3 entry is committed, all preceding entries are
  implicitly committed (Log Matching Property).
```

---

## 7. Log Compaction (Snapshotting)

### 7.1 Problem

Without compaction, the log grows forever. Replaying millions of entries on restart is impractical.

### 7.2 Snapshot Approach

Each node independently takes a snapshot of the state machine at a committed index, then discards all log entries up to that index.

```
BEFORE SNAPSHOT:
┌────────────────────────────────────────────────────────────────┐
│ Log: [1:1][2:1][3:1][4:2][5:2][6:3][7:3][8:3][9:3][10:3]     │
│                                                    ▲           │
│                                              commitIndex=10    │
│ State machine: {x=5, y=2, z=9}                                │
└────────────────────────────────────────────────────────────────┘

AFTER SNAPSHOT (at index 7):
┌────────────────────────────────────────────────────────────────┐
│ Snapshot:                                                      │
│ ┌───────────────────────────────────┐                          │
│ │ lastIncludedIndex = 7             │                          │
│ │ lastIncludedTerm  = 3             │                          │
│ │ state = {x=3, y=2, z=9}          │  [8:3][9:3][10:3]       │
│ │ cluster config at index 7         │    ▲                     │
│ └───────────────────────────────────┘    │                     │
│                                     retained log               │
└────────────────────────────────────────────────────────────────┘
```

### 7.3 InstallSnapshot RPC

When a follower is so far behind that the leader has already discarded the entries it needs, the leader sends its snapshot:

```
InstallSnapshot RPC:
┌─────────────────────────────────────────┐
│  term                                    │
│  leaderId                                │
│  lastIncludedIndex                       │
│  lastIncludedTerm                        │
│  offset          (byte offset in chunk)  │
│  data[]          (snapshot chunk)        │
│  done            (last chunk?)           │
└─────────────────────────────────────────┘
```

The follower replaces its entire state machine with the snapshot and discards any log entries covered by it.

```
Leader                              Slow Follower
  │                                      │
  │  AppendEntries(prevLogIndex=50)      │
  │ ────────────────────────────────────▶│  Rejected! Follower only has up to 10
  │                                      │
  │  Leader's log starts at 40 (snapshotted 1-39)
  │  Cannot send entries 11-39!
  │                                      │
  │  InstallSnapshot(lastIncluded=39)    │
  │ ────────────────────────────────────▶│  Follower installs snapshot
  │                                      │  Follower now at index 39
  │  AppendEntries(40, 41, 42, ...)      │
  │ ────────────────────────────────────▶│  Normal replication resumes
```

---

## 8. Membership Changes

### 8.1 The Problem

Changing cluster membership (adding/removing nodes) is dangerous because different nodes may see different configurations at the same time, potentially allowing two independent majorities (split brain).

### 8.2 Joint Consensus (Raft Paper Approach)

Two-phase approach:

```
Phase 1: C_old → C_{old,new} (joint configuration)
  - Decisions require majority of BOTH old AND new configs
  - No split brain possible

Phase 2: C_{old,new} → C_new
  - Once committed, switch to new config

Timeline:
┌──────────┐    ┌─────────────────┐    ┌──────────┐
│  C_old   │───▶│  C_{old,new}    │───▶│  C_new   │
│ {A,B,C}  │    │ {A,B,C}∩{B,C,D}│    │ {B,C,D}  │
└──────────┘    └─────────────────┘    └──────────┘
```

### 8.3 Single-Server Changes (Simpler)

Adopted by etcd and most production systems. Only add or remove one server at a time. Safety argument: any majority of the old config overlaps with any majority of the new config when they differ by exactly one node.

```
{A, B, C} → add D → {A, B, C, D} → remove A → {B, C, D}

Old majority (2/3) and new majority (3/4) must overlap:
  Old has 3 nodes, majority=2
  New has 4 nodes, majority=3
  2 + 3 = 5 > 4 (total unique nodes) → must overlap ✓
```

### 8.4 Cold-Start Problem

On initial cluster bootstrap, there's no existing leader to propose configuration changes. Solutions:
- Bootstrap with a known initial configuration.
- Use an external coordination service for initial discovery.
- Designate one node as the initial leader that commits the first config entry.

---

## 9. Linearizable Reads

By default, Raft only guarantees linearizable writes. Reads from the leader could return stale data if the leader has been deposed but doesn't know it yet.

### 9.1 ReadIndex

1. Leader records current commitIndex as `readIndex`.
2. Leader sends a heartbeat to confirm it's still leader (gets majority ack).
3. Leader waits until its state machine has applied up to `readIndex`.
4. Leader serves the read.

Cost: one round of heartbeats per read (or batched).

### 9.2 Lease-Based Reads

If the leader received heartbeat acks within the last `election_timeout / 2`, it can assume it's still leader (no other node could have timed out and won yet).

```
Timeline:
  Leader sends heartbeat at T=0
  Gets majority ack at T=5ms
  Lease valid until T = 0 + (election_timeout / 2) = 75ms
  
  Read at T=30ms → serve directly, no extra RPC needed
  Read at T=80ms → lease expired, must use ReadIndex
```

**Trade-off**: Depends on bounded clock drift. If clocks skew beyond bounds, stale reads are possible. Most production systems accept this risk.

### 9.3 Follower Reads

Followers can serve reads too:
1. Follower asks leader for current `readIndex`.
2. Follower waits until its own applied index ≥ `readIndex`.
3. Follower serves the read from its local state.

Reduces leader load; useful for read-heavy workloads.

---

## 10. Real-World Implementations

| System | Use of Raft | Notes |
|--------|-------------|-------|
| **etcd** | All metadata storage for Kubernetes | Single Raft group, reference implementation of Raft in Go |
| **CockroachDB** | One Raft group per range (~64MB) | 100K+ concurrent Raft groups, Multi-Raft optimization |
| **TiKV (TiDB)** | Multi-Raft for distributed KV | Raft per region, leader transfer for load balancing |
| **Consul** | Service catalog + KV store | HashiCorp/raft library |
| **RabbitMQ** | Quorum Queues | Raft for replicated queue state (replaced mirrored queues) |
| **Kafka (KRaft)** | Metadata quorum | Replaces ZooKeeper dependency (KIP-500) |
| **InfluxDB** | Metadata coordination | Enterprise clustering |
| **ScyllaDB** | Schema changes (Raft-based) | Topology and DDL operations |
| **YugabyteDB** | Raft per tablet | DocDB layer, similar to CockroachDB |
| **Dgraph** | Raft per group | Distributed graph DB |

### etcd Deep Dive

```
Kubernetes Architecture with etcd:

  kube-apiserver ─────▶ etcd (Raft Leader)
       │                     │
       │                     ├── etcd Follower 1
       │                     └── etcd Follower 2
       │
       ├── kubelet
       ├── kube-scheduler
       └── kube-controller-manager

All cluster state (pods, services, configmaps, secrets)
stored as key-value pairs in etcd via Raft consensus.
```

### Multi-Raft (CockroachDB / TiKV)

```
┌─────────────────────────────────────────────────────────┐
│                    Node 1                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │
│  │Range 1  │  │Range 5  │  │Range 9  │  │Range 12 │   │
│  │(Leader) │  │(Follower│  │(Leader) │  │(Follower│   │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │
├─────────────────────────────────────────────────────────┤
│                    Node 2                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │
│  │Range 1  │  │Range 5  │  │Range 9  │  │Range 12 │   │
│  │(Follower│  │(Leader) │  │(Follower│  │(Leader) │   │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │
├─────────────────────────────────────────────────────────┤
│                    Node 3                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │
│  │Range 1  │  │Range 5  │  │Range 9  │  │Range 12 │   │
│  │(Follower│  │(Follower│  │(Follower│  │(Follower│   │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │
└─────────────────────────────────────────────────────────┘

Each range is an independent Raft group.
Leaders are distributed across nodes for load balancing.
Single RPC transport layer multiplexes all groups.
```

---

## 11. Performance Optimizations

### 11.1 Batching

Accumulate multiple client requests and replicate them in a single AppendEntries RPC. Amortizes the cost of disk fsync and network round-trips.

```
Without batching: 1 entry/RPC × 1000 clients = 1000 RPCs/round
With batching:    100 entries/RPC × 10 RPCs = same 1000 entries, 100x fewer RPCs
```

### 11.2 Pipelining

Don't wait for follower to acknowledge batch N before sending batch N+1. Send multiple in-flight AppendEntries in parallel.

```
Leader ──[batch1]──▶ Follower
Leader ──[batch2]──▶ Follower    (sent before ack of batch1)
Leader ──[batch3]──▶ Follower    (sent before ack of batch2)
       ◀──[ack1]─── Follower
       ◀──[ack2]─── Follower
       ◀──[ack3]─── Follower
```

### 11.3 Parallel Appending

Followers append to disk in parallel. The leader doesn't need to wait for its own disk write before sending AppendEntries — it can replicate to followers concurrently with its own append.

```
                    ┌── Leader disk write ──────────┐
  Client request ──┤                                ├── commit (whichever later)
                    └── Follower replication ───────┘
                         (parallel, not sequential)
```

### 11.4 Witness Replicas

Nodes that participate in voting (count toward majority) but don't store the full log/state. They only store metadata sufficient to vote correctly. Reduces storage costs for large datasets.

### 11.5 Multi-Raft Optimizations

When running thousands of Raft groups on one node:
- **Shared transport**: Single TCP connection between nodes multiplexes all groups.
- **Combined heartbeats**: One message carries heartbeats for all groups between two nodes.
- **Batched disk writes**: Combine log appends from multiple groups into a single fsync.

---

## 12. Raft vs Paxos

| Dimension | Raft | Multi-Paxos |
|-----------|------|-------------|
| **Understandability** | Designed for it; clear decomposition | Notoriously difficult |
| **Leader** | Strong leader required | Flexible; can be leaderless |
| **Log gaps** | No gaps allowed | Allows gaps (out-of-order commit) |
| **Reconfiguration** | Built into protocol | Separate problem |
| **Implementation** | Many correct implementations exist | Few correct implementations |
| **Theoretical efficiency** | Slightly more messages (no gaps) | Optimal in theory |
| **Practical throughput** | Comparable with optimizations | Comparable |
| **Leader election** | Explicit protocol with terms | Less specified |
| **Log divergence** | Leader overwrites followers | More complex resolution |
| **Read optimization** | ReadIndex / leases well-studied | Similar approaches exist |
| **Adoption (2024)** | Dominant in new systems | Legacy (Chubby, Spanner internals) |

**Key insight**: Raft sacrifices some theoretical flexibility (no log gaps, strong leader) for massive gains in implementability and operational predictability.

---

## 13. Architect's Guide

### When to Embed Raft

**Use Raft when you need:**
- Replicated state machine for metadata (config, leader election, distributed locks)
- Strong consistency for a relatively small dataset (< tens of GB)
- Coordination primitive within a larger system

**Don't use Raft when:**
- You need high-throughput data replication (use chain replication or async replication)
- Dataset is too large for single Raft group (use Multi-Raft, but that's complex)
- Eventual consistency is acceptable (use gossip, CRDTs)
- You can use an existing system (etcd, Consul) instead of embedding

### Library Choices

| Library | Language | Used By | Notes |
|---------|----------|---------|-------|
| **etcd/raft** | Go | etcd, CockroachDB, TiKV | Battle-tested, low-level (you provide transport + storage) |
| **hashicorp/raft** | Go | Consul, Nomad, Vault | Higher-level, easier to integrate, includes transport |
| **Dragonboat** | Go | — | Multi-Raft focused, high performance, pipelining built in |
| **openraft** | Rust | Databend, Chunkserver | Modern, async Rust, well-typed |
| **Apache Ratis** | Java | Apache Ozone | Java ecosystem |
| **nuraft** | C++ | ClickHouse Keeper | LinkedIn-originated |
| **lraft** | C | — | Minimal, embedded |

### Decision Framework

```
Do you need consensus?
├── No → Use eventual consistency (gossip, CRDTs)
├── Yes → Can you use an existing service?
│         ├── Yes → Use etcd / Consul / ZooKeeper
│         └── No (latency, coupling, control) → Embed a library
│               ├── Go → etcd/raft (control) or hashicorp/raft (convenience)
│               ├── Rust → openraft
│               ├── Java → Apache Ratis
│               ├── C++ → nuraft
│               └── Multi-Raft needed? → Dragonboat
```

### Operational Considerations

- **Cluster size**: 3 nodes (tolerate 1 failure) or 5 nodes (tolerate 2). 7 is rarely worth it (diminishing returns, more replication overhead).
- **Disk**: Raft requires fsync on every commit. Use fast SSDs. Separate Raft WAL from data disk.
- **Network**: Latency between nodes directly impacts commit latency (leader must wait for majority). Co-locate in same region/AZ.
- **Monitoring**: Track election count, log lag per follower, commit latency p99, snapshot frequency.
- **Backpressure**: If followers can't keep up, leader must slow down or risk unbounded memory growth from buffered entries.

---

## References

1. Ongaro, D. & Ousterhout, J. (2014). *In Search of an Understandable Consensus Algorithm*. USENIX ATC.
2. Ongaro, D. (2014). *Consensus: Bridging Theory and Practice*. PhD Dissertation, Stanford.
3. Howard, H. et al. (2015). *Raft Refloated: Do We Have Consensus?* ACM SIGOPS.
4. etcd/raft source: https://github.com/etcd-io/raft
5. Raft visualization: https://raft.github.io
