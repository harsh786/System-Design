# Leader Election in Distributed Systems

## 1. Why Leader Election?

In distributed systems, many problems become dramatically simpler when a single node acts as the **coordinator**. Leader election is the process of designating one node among a group as the authoritative decision-maker.

### The Single Coordinator Pattern

```
┌─────────────────────────────────────────────────────────┐
│                    WHY A LEADER?                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Without Leader:              With Leader:              │
│                                                         │
│  N1 ──write──► DB            N1 ──write──┐             │
│  N2 ──write──► DB  CONFLICT! N2 ──write──► Leader ──► DB│
│  N3 ──write──► DB            N3 ──write──┘  (serial)   │
│                                                         │
│  Requires consensus          Single serialization      │
│  on every operation           point, simple ordering    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Core Use Cases

| Use Case | Why Leader Helps | Example |
|----------|-----------------|---------|
| **Serializing writes** | Total ordering without distributed consensus per-op | Kafka partition leader, HDFS NameNode |
| **Coordinating distributed tasks** | Centralized scheduling avoids conflicts | Flink JobManager, YARN ResourceManager |
| **Managing shared resources** | Single arbiter for locks/leases | Chubby, ZooKeeper |
| **Partition assignment** | One brain decides who handles what | Kafka Controller, Elasticsearch Master |
| **Failure detection & recovery** | Coordinated failover decisions | Redis Sentinel, Kubernetes controllers |

### Trade-offs of the Leader Pattern

**Advantages:**
- Simplifies consistency (no per-operation consensus)
- Reduces message complexity (O(1) vs O(n²) per operation)
- Natural serialization point

**Disadvantages:**
- Single point of failure (mitigated by re-election)
- Throughput bottleneck at leader
- Election period = downtime window
- Split-brain risk during partitions

---

## 2. Bully Algorithm

The Bully Algorithm (Garcia-Molina, 1982) is the simplest leader election: **the node with the highest ID wins**.

### Algorithm Steps

1. When a node P detects the leader has failed:
   - P sends **ELECTION** messages to all nodes with higher IDs
2. If P receives no **ANSWER** within timeout:
   - P declares itself leader, sends **COORDINATOR** to all lower-ID nodes
3. If P receives an ANSWER:
   - P waits for a COORDINATOR message (higher node takes over)
4. When a higher-ID node receives an ELECTION:
   - It replies **ANSWER** to sender
   - It starts its own election (sends ELECTION to even higher nodes)

### Message Flow

```
Nodes: N1(id=1), N2(id=2), N3(id=3), N4(id=4), N5(id=5-LEADER, crashed)

Time ──────────────────────────────────────────────────────────►

N1: detects N5 crash
    │
    ├──ELECTION──► N2  (higher ID)
    ├──ELECTION──► N3  (higher ID)
    ├──ELECTION──► N4  (higher ID)
    ├──ELECTION──► N5  (no reply, crashed)
    │
N2: │◄─────────────┘
    ├──ANSWER───► N1   "back off, I'm higher"
    ├──ELECTION──► N3
    ├──ELECTION──► N4
    ├──ELECTION──► N5  (no reply)
    │
N3: │◄─────────────┘
    ├──ANSWER───► N1
    ├──ANSWER───► N2   "back off"
    ├──ELECTION──► N4
    ├──ELECTION──► N5  (no reply)
    │
N4: │◄─────────────┘
    ├──ANSWER───► N1
    ├──ANSWER───► N2
    ├──ANSWER───► N3   "back off"
    ├──ELECTION──► N5  (no reply)
    │
    │  ... timeout waiting for ANSWER from N5 ...
    │
    ├──COORDINATOR──► N1
    ├──COORDINATOR──► N2
    ├──COORDINATOR──► N3
    │
    ▼
   N4 IS THE NEW LEADER
```

### Complexity Analysis

| Metric | Complexity | Notes |
|--------|-----------|-------|
| Messages (worst case) | O(n²) | Lowest node starts election |
| Messages (best case) | O(n) | Highest surviving node starts |
| Time to elect | O(n) rounds | Sequential escalation |
| Failure detection | Timeout-based | Configurable |

### Pseudocode

```
function startElection(self):
    higherNodes = allNodes.filter(n => n.id > self.id)
    
    if higherNodes.isEmpty():
        declareVictory(self)
        return
    
    for node in higherNodes:
        send(ELECTION, node)
    
    waitForAnswer(timeout=T):
        if no ANSWER received:
            declareVictory(self)
        else:
            waitForCoordinator(timeout=2T)
            if no COORDINATOR received:
                startElection(self)  // higher node may have crashed

function declareVictory(self):
    self.isLeader = true
    for node in allNodes.filter(n => n.id < self.id):
        send(COORDINATOR(self.id), node)
```

### Limitations

1. **Assumes crash-stop model** - no Byzantine failures
2. **No network partition handling** - partitioned highest-ID node might not be reachable by majority
3. **O(n²) messages** - impractical for large clusters
4. **Unfair** - always elects highest ID regardless of suitability
5. **No stability guarantee** - a recovered high-ID node immediately takes over ("bullies" current leader)

---

## 3. Ring Election Algorithm (Chang-Roberts)

Nodes are arranged in a **logical ring**. Election messages travel around the ring, and the highest-ID node encountered becomes leader.

### Algorithm

1. Initiator sends ELECTION(own_id) to its successor on the ring
2. Each node receiving ELECTION(id):
   - If `id > own_id`: forward ELECTION(id) to successor
   - If `id < own_id`: replace with ELECTION(own_id) and forward
   - If `id == own_id`: this node has won! Send COORDINATOR around ring
3. COORDINATOR message travels the full ring to announce the new leader

### Ring Election Flow

```
Logical Ring: N3 → N7 → N2 → N5(crashed) → N4 → N1 → N3

Step 1: N3 detects N5 is dead, starts election
═══════════════════════════════════════════════

    N3 ──ELECTION(3)──► N7
         
Step 2: N7 has higher ID, replaces
═══════════════════════════════════

    N7 ──ELECTION(7)──► N2

Step 3: N2 has lower ID, forwards
══════════════════════════════════

    N2 ──ELECTION(7)──► N4  (skips crashed N5)

Step 4: N4 has lower ID, forwards
══════════════════════════════════

    N4 ──ELECTION(7)──► N1

Step 5: N1 has lower ID, forwards
══════════════════════════════════

    N1 ──ELECTION(7)──► N3

Step 6: N3 has lower ID, forwards
══════════════════════════════════

    N3 ──ELECTION(7)──► N7

Step 7: N7 sees own ID → VICTORY!
══════════════════════════════════

    N7 ──COORDINATOR(7)──► N2 ──► N4 ──► N1 ──► N3 ──► N7 (done)


          ┌───┐     ┌───┐
          │N3 │────►│N7★│  ★ = new leader
          └───┘     └───┘
           ▲          │
           │          ▼
          ┌───┐     ┌───┐
          │N1 │     │N2 │
          └───┘     └───┘
           ▲          │
           │          ▼
          ┌───┐     ┌───┐
          │N4 │◄────│   │  (N5 skipped)
          └───┘     └───┘
```

### Complexity

| Metric | Value |
|--------|-------|
| Messages (worst case) | O(2n) = n for election + n for coordinator |
| Messages (best case) | O(2n) |
| Time | O(2n) hops |

### When to Use

- **Small, stable clusters** (< 20 nodes)
- Nodes have natural ring topology (e.g., consistent hashing ring)
- Message complexity of O(n) is acceptable
- Network is reliable (no partitions)
- Crash-stop failure model

### Limitations

- Single point of failure in the ring (must maintain ring structure)
- Slow for large rings (sequential forwarding)
- Ring maintenance overhead when nodes join/leave
- Same crash-stop assumptions as Bully

---

## 4. Raft Leader Election

Raft (Ongaro & Ousterhout, 2014) provides a **consensus-based** leader election that handles network partitions correctly. It is the gold standard for modern distributed systems.

### Core Concepts

**Terms**: Logical clock that increases monotonically. Each term has at most one leader.

**States**: Each node is in one of: Follower, Candidate, Leader

**Election Timeout**: Randomized timer (e.g., 150-300ms). If a follower doesn't hear from a leader within this window, it starts an election.

### Election Flow

```
┌────────────────────────────────────────────────────────────────┐
│                    RAFT STATE MACHINE                           │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│                    starts up                                    │
│                       │                                        │
│                       ▼                                        │
│   ┌──────────┐  timeout  ┌───────────┐  majority  ┌────────┐ │
│   │ FOLLOWER │──────────►│ CANDIDATE │───votes────►│ LEADER │ │
│   └──────────┘           └───────────┘             └────────┘ │
│        ▲                    │      │                    │      │
│        │                    │      │                    │      │
│        │   discovers        │      │  discovers         │      │
│        │   current leader   │      │  higher term       │      │
│        │◄───────────────────┘      │◄───────────────────┘      │
│        │                           │                           │
│        │      new term             │                           │
│        │◄──────────────────────────┘                           │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### RequestVote RPC

```
RequestVote RPC:
  Arguments:
    term          - candidate's term
    candidateId   - candidate requesting vote
    lastLogIndex  - index of candidate's last log entry
    lastLogTerm   - term of candidate's last log entry

  Results:
    term          - currentTerm, for candidate to update itself
    voteGranted   - true = candidate received vote

  Receiver implementation:
    1. Reply false if term < currentTerm
    2. If votedFor is null or candidateId, AND candidate's log is
       at least as up-to-date as receiver's log, grant vote
```

### Election Timeline

```
Time ──────────────────────────────────────────────────────────────►

Term 1:  Leader = N1
═══════════════════════════════════════════════════════════════

N1(L): ♥────♥────♥────♥────✗ (crashes)
N2(F): ..heard..heard..heard....timeout!
N3(F): ..heard..heard..heard..........timeout!
N4(F): ..heard..heard..heard..............timeout!
N5(F): ..heard..heard..heard..................timeout!

                              ▲
                              │ election timeout (randomized)
                              │ N2 times out first (shortest timeout)

Term 2:  Election
═══════════════════════════════════════════════════════════════

N2: increments term to 2, votes for self
    │
    ├──RequestVote(term=2, lastLog=(idx=10,term=1))──► N3
    ├──RequestVote(term=2, lastLog=(idx=10,term=1))──► N4
    ├──RequestVote(term=2, lastLog=(idx=10,term=1))──► N5
    │
N3: ◄── grants vote (hasn't voted in term 2, log is not more up-to-date)
N4: ◄── grants vote
N5: ◄── grants vote
    │
    │  N2 has 4 votes (self + N3 + N4 + N5) out of 5 nodes
    │  Majority = 3, so N2 wins!
    │
N2: sends AppendEntries heartbeats as new leader
    │
    ├──♥──► N3
    ├──♥──► N4  
    ├──♥──► N5
    │
    ▼
   N2 IS LEADER FOR TERM 2
```

### Split Vote Handling

```
Scenario: N2 and N3 both timeout simultaneously

Term 2 - SPLIT VOTE:
═══════════════════════════════════════════════════════════════

N2: votes for self, requests votes
    ├──RequestVote──► N4 (votes for N2)
    ├──RequestVote──► N5 (votes for N3, arrived first)
    │
N3: votes for self, requests votes  
    ├──RequestVote──► N4 (already voted for N2, rejects)
    ├──RequestVote──► N5 (votes for N3)
    │
    Results: N2 has 2 votes (self + N4)
             N3 has 2 votes (self + N5)
             Neither has majority (need 3 of 5)

    Both timeout again with NEW random timeouts
    ───────────────────────────────────────────

Term 3 - RESOLVED:
═══════════════════════════════════════════════════════════════

N3: times out first (got shorter random timeout)
    ├──RequestVote(term=3)──► N2 (updates term, votes for N3)
    ├──RequestVote(term=3)──► N4 (votes for N3)
    ├──RequestVote(term=3)──► N5 (votes for N3)
    │
    N3 wins with 4 votes!
```

**Why randomized timeouts work**: The probability of repeated split votes decreases exponentially. With timeout range [T, 2T], the probability that two nodes collide is roughly `broadcastTime / T`, which is typically < 1%.

### Pre-Vote Extension (Raft §9.6)

**Problem**: A partitioned node keeps incrementing its term. When it rejoins, its high term disrupts the current leader.

```
WITHOUT Pre-Vote:
══════════════════

Partition:  [N1-leader, N2, N3]  |  [N4, N5]

N4: timeout → term 3 → election fails (no majority)
    timeout → term 4 → election fails
    timeout → term 5 → election fails
    ...
    timeout → term 99 → election fails

Partition heals:
    N4 sends RequestVote(term=99) to N1
    N1 sees term 99 > its term 2, steps down!
    Unnecessary disruption.

WITH Pre-Vote:
══════════════

N4: timeout → sends PreVote(term=current+1) to all
    No majority responds → does NOT increment term
    Stays at original term

Partition heals:
    N4 rejoins, no term inflation, no disruption
```

**PreVote Rules**:
- Before starting real election, candidate sends PreVote
- Nodes grant PreVote only if they would grant a real vote AND haven't heard from a leader recently
- Only if PreVote succeeds does the node increment term and start real election

---

## 5. ZooKeeper-Based Election

ZooKeeper provides **ephemeral sequential znodes** that enable elegant leader election without implementing consensus yourself.

### Mechanism

1. Each candidate creates an ephemeral sequential znode under an election path
2. The node with the **lowest sequence number** is the leader
3. All others watch the znode **immediately preceding** theirs (not the leader!)
4. When a znode is deleted (node dies), its watcher is notified

### Election Flow

```
ZooKeeper Namespace:
/election/
    ├── candidate-0000000001  (N3 - LEADER, lowest seq)
    ├── candidate-0000000002  (N1 - watches 0001)
    ├── candidate-0000000003  (N5 - watches 0002)
    └── candidate-0000000004  (N2 - watches 0003)


Step 1: Initial State
═══════════════════════════════════════════════════════

  /election/
  ┌──────────────────────┐
  │ candidate-001 → N3 ★ │  ★ = leader (lowest)
  │ candidate-002 → N1   │  watches 001
  │ candidate-003 → N5   │  watches 002
  │ candidate-004 → N2   │  watches 003
  └──────────────────────┘

Step 2: N3 (leader) crashes → ephemeral znode deleted
═══════════════════════════════════════════════════════

  /election/
  ┌──────────────────────┐
  │ ██ candidate-001 ██  │  DELETED (session expired)
  │ candidate-002 → N1 ★ │  notified! now leader (lowest)
  │ candidate-003 → N5   │  watches 002 (no change)
  │ candidate-004 → N2   │  watches 003 (no change)
  └──────────────────────┘

  Only N1 is notified → O(1) notifications!

Step 3: N1 crashes
═══════════════════════════════════════════════════════

  /election/
  ┌──────────────────────┐
  │ ██ candidate-002 ██  │  DELETED
  │ candidate-003 → N5 ★ │  notified! now leader
  │ candidate-004 → N2   │  watches 003 (no change)
  └──────────────────────┘
```

### Herd Effect Avoidance

**Naive approach** (all watch leader):
```
Leader dies → ALL n-1 nodes wake up → ALL check znodes → ALL but one go back to sleep
= O(n) notifications, O(n) reads = THUNDERING HERD
```

**Correct approach** (watch predecessor):
```
Leader dies → ONLY next-in-line wakes up → checks znodes → becomes leader
= O(1) notifications, O(1) reads
```

### Curator Framework

Apache Curator provides battle-tested leader election recipes:

**LeaderLatch**:
- All participants contend; one becomes leader
- Leader remains until it voluntarily releases or disconnects
- Simpler API: `leaderLatch.await()` blocks until leadership acquired
- Use when: leader holds leadership for entire process lifetime

**LeaderSelector**:
- Callback-based: `takeLeadership()` called when elected
- Leadership automatically released when callback returns
- Supports automatic re-queue (node can be elected again)
- Use when: leadership is for a task, not a role

```java
// LeaderLatch example
LeaderLatch latch = new LeaderLatch(client, "/election/service-a");
latch.start();
latch.await(); // blocks until this node is leader
// ... do leader work ...

// LeaderSelector example  
LeaderSelector selector = new LeaderSelector(client, "/election/service-a",
    new LeaderSelectorListenerAdapter() {
        public void takeLeadership(CuratorFramework client) {
            // this node is now leader
            // leadership released when this method returns
            doLeaderWork();
        }
    });
selector.autoRequeue(); // re-enter election when leadership lost
selector.start();
```

### ZooKeeper Election Properties

| Property | Value |
|----------|-------|
| Consistency | Linearizable (ZAB protocol) |
| Failure detection | Session timeout (ephemeral nodes) |
| Message complexity | O(1) per leadership change |
| Availability | Requires ZK quorum (majority of ZK ensemble) |
| Leader uniqueness | Guaranteed within a ZK session |

---

## 6. etcd-Based Election

etcd provides leader election through its **lease mechanism** combined with **revision-based ordering** and **compare-and-swap** (CAS) transactions.

### Mechanism

1. Each candidate creates a lease with a TTL
2. Candidate attempts to put a key with its lease attached, using CAS (create-only)
3. The key's **revision** determines ordering - lowest revision = leader
4. Leader must periodically refresh its lease (keepalive)
5. If lease expires (leader dies), key is auto-deleted, next candidate wins

### Election Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    etcd Election Flow                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  N1: Grant Lease (TTL=15s) → LeaseID=1001                  │
│      PUT /election/leader value="N1" lease=1001             │
│      IF key does not exist (CreateRevision == 0)            │
│      → SUCCESS (revision=100) → N1 is leader               │
│                                                             │
│  N2: Grant Lease (TTL=15s) → LeaseID=1002                  │
│      PUT /election/leader value="N2" lease=1002             │
│      IF key does not exist → FAILS (key exists)            │
│      → PUT /election/candidates/N2 lease=1002              │
│      → Watch /election/leader for DELETE                    │
│                                                             │
│  N1: KeepAlive every 5s (TTL/3)                            │
│      │──keepalive──► etcd (resets TTL to 15s)              │
│      │──keepalive──► etcd                                  │
│      │──✗ (crash)                                          │
│                                                             │
│  etcd: 15s passes, lease 1001 expires                      │
│        → auto-delete /election/leader                       │
│        → watch fires on N2                                  │
│                                                             │
│  N2: watch triggered, attempts CAS again                   │
│      PUT /election/leader value="N2" lease=1002            │
│      → SUCCESS → N2 is leader                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Revision-Based Ordering

etcd's concurrency package uses a more sophisticated approach:

```
All candidates write to /election/<prefix>/<LeaseID>
Keys are ordered by ModRevision (etcd's global revision counter)

/election/service/1001  revision=100  value="N1"  ← LEADER (lowest rev)
/election/service/1002  revision=101  value="N2"  ← watches rev 100
/election/service/1003  revision=102  value="N3"  ← watches rev 101
```

This mirrors ZooKeeper's sequential znode approach but uses etcd's MVCC revision as the ordering mechanism.

### Key Properties

| Property | Value |
|----------|-------|
| Consistency | Linearizable (Raft-based) |
| Failure detection | Lease TTL expiry |
| Typical TTL | 10-30 seconds |
| KeepAlive frequency | TTL/3 |
| Client library | `go.etcd.io/etcd/client/v3/concurrency` |

---

## 7. Lease-Based Leadership

A **lease** is a time-bounded authority token. The leader holds a lease that must be renewed before expiry; if not renewed, the system assumes the leader is dead.

### Lease Lifecycle

```
Time ──────────────────────────────────────────────────────────────────►

LEADER N1:
├─── acquire lease (TTL=10s) ───┤
│                               │
│  lease valid                  │ renew at T-3s
│◄─────────────────────────────►│
│                               │
│         ├── renewed (TTL reset to 10s) ──────────┤
│         │                                        │
│         │  lease valid                           │ renew at T-3s
│         │◄──────────────────────────────────────►│
│         │                                        │
│         │              ├── renewed ──────────────────────┤
│         │              │                                 │
│         │              │        N1 CRASHES ✗             │
│         │              │              │                  │
│         │              │              │   lease expires  │
│         │              │              │◄────────────────►│
│                                                          │
│                                              LEADERSHIP VACANT
│                                                          │
│                                              N2 acquires new lease
│                                              ├──────────────────────

TIMELINE:
═════════════════════════════════════════════════════════════════════

  ┌─acquire──┬──────valid──────┬─renew─┬──────valid──────┬─expire─┐
  │          │                 │       │                 │        │
  t=0       t=0              t=7     t=7              t=14    t=17
             └─── TTL=10s ────┘        └─── TTL=10s ────┘
                                                         ▲
                                                    leader died at t=12
                                                    lease expires at t=17
                                                    (5s detection delay)
```

### Clock Skew Problem

```
DANGEROUS SCENARIO:
═══════════════════

Real Time:    0────────5────────10────────15────────20
              │        │         │         │         │

Leader N1:    ├──lease──────────►|  (thinks lease valid until t=10)
(clock OK)    │  renewed at t=0  |
              │                  |

Follower N2:  │                  |
(clock +3s    │        ┌────────►| N2's clock says t=13 (lease expired!)
 ahead)       │        │ "lease  | N2 thinks it can become leader
              │        │ expired"| 
              │        │         |
              BOTH THINK THEY ARE LEADER from t=7 to t=10 (N2's view)!

SOLUTION: Leader must stop acting as leader BEFORE lease expires
          Follower must wait AFTER lease expires before taking over

  Leader stops:    lease_end - clock_drift - safety_margin
  Follower starts: lease_end + clock_drift + safety_margin
```

### Fencing Tokens

**Problem**: A slow/paused leader (GC pause, network delay) might still act on stale authority after its lease expired and a new leader was elected.

```
FENCING TOKEN SOLUTION:
═══════════════════════

Leader N1: lease granted, fencing_token = 33
           │
           │──── write(token=33) ──────────────────────────► Storage
           │                                                     │
           │  GC PAUSE (30 seconds!)                             │
           │  zzz...                                             │
           │                                                     │
           │         Meanwhile: lease expires                    │
           │         N2 becomes leader, fencing_token = 34       │
           │              │                                      │
           │              │── write(token=34) ──────────────► Storage
           │              │                                      │
           │  GC PAUSE ENDS                                      │ token=34
           │                                                     │ stored
           │── write(token=33) ─────────────────────────────►  REJECTED!
           │                                                  token 33 < 34
           │
           ▼
   Storage rejects any write with token < highest seen token

┌──────────────────────────────────────────────────────────┐
│  FENCING TOKEN RULE:                                     │
│  Every protected resource tracks the highest token seen. │
│  Requests with lower tokens are REJECTED.                │
│  Token = monotonically increasing (epoch/term/revision)  │
└──────────────────────────────────────────────────────────┘
```

### Implementation Considerations

| Parameter | Recommended | Rationale |
|-----------|-------------|-----------|
| Lease TTL | 10-30s | Balances detection speed vs. false positives |
| Renewal interval | TTL/3 | Allows 2 retries before expiry |
| Clock sync | NTP with max drift | Bound on clock skew |
| Safety margin | 2 × max_clock_drift | Prevents overlap |
| Fencing token source | Consensus system's term/epoch | Guaranteed monotonic |

---

## 8. Consensus-Based Election (Paxos)

### Basic Paxos for Single-Value Election

Paxos elects a leader by achieving consensus on "who is the leader" as a single value:

```
PAXOS LEADER ELECTION (simplified):
════════════════════════════════════

Phase 1a - PREPARE:
  N3 (wants to be leader): sends Prepare(n=5) to all

Phase 1b - PROMISE:
  N1: Promise(n=5, no prior accepted) → N3
  N2: Promise(n=5, no prior accepted) → N3
  N4: Promise(n=5, no prior accepted) → N3
  
  N3 has majority promises (3 of 5)

Phase 2a - ACCEPT:
  N3: sends Accept(n=5, value="N3") to all

Phase 2b - ACCEPTED:
  N1: Accepted(n=5, "N3") → all
  N2: Accepted(n=5, "N3") → all
  N4: Accepted(n=5, "N3") → all

  Majority accepted → N3 is leader
```

### Multi-Paxos Stable Leader Optimization

Running full Paxos for every operation is expensive. **Multi-Paxos** optimizes by having a **stable leader** (distinguished proposer):

```
MULTI-PAXOS OPTIMIZATION:
═════════════════════════

Full Paxos per operation:          Multi-Paxos with stable leader:
                                   
  Client → Prepare → Promise       Client → Accept → Accepted
          → Accept  → Accepted              (Phase 1 skipped!)
  = 4 message delays                = 2 message delays

The leader is the "distinguished proposer":
- Only the leader proposes
- Leader can skip Phase 1 for consecutive slots
  (reuses its proposal number across slots)
- If another node tries to propose, it must use higher proposal number
  → current leader detects and steps down

┌─────────────────────────────────────────────────────┐
│  MULTI-PAXOS STEADY STATE:                          │
│                                                     │
│  Client──►Leader──Accept(slot=i)──►Acceptors        │
│                 ◄─Accepted(slot=i)──                │
│           Leader──Accept(slot=i+1)──►Acceptors      │
│                 ◄─Accepted(slot=i+1)──              │
│                                                     │
│  No Prepare/Promise needed once leader established! │
│  Amortizes election cost over many operations.      │
└─────────────────────────────────────────────────────┘
```

### Leader as Distinguished Proposer

- All clients send requests to the leader
- Leader assigns sequence numbers (log slots)
- If leader fails, any node can start Phase 1 with higher proposal number
- First node to get a majority of Promises becomes new leader
- **Dueling proposers** risk: two nodes alternately pre-empting each other → randomized backoff

---

## 9. Challenges

### Network Partitions Causing Dual Leaders

```
SPLIT-BRAIN SCENARIO:
═════════════════════

Before partition:
  [N1-leader, N2, N3, N4, N5]  ← N1 is leader

Network partition:
  [N1-leader, N2]  |  [N3, N4, N5]
       minority    |     majority

Right side elects new leader:
  [N1-leader, N2]  |  [N3-NEW-LEADER, N4, N5]

TWO LEADERS! Both think they're in charge.

SOLUTIONS:
══════════
1. Majority quorum: N1 can't commit (only 2/5 nodes), effectively demoted
2. Fencing tokens: N3's token > N1's, storage rejects N1's writes
3. Leader must verify quorum before acting (read lease)
4. Epoch/term numbers: higher term wins all conflicts
```

### GC Pauses

```
PROBLEM:
════════

Time:     0     5     10    15    20    25    30    35
          │     │     │     │     │     │     │     │
Leader:   ├─ok──┤─GC PAUSE─────────────────────┤─ok─┤
                      │                         │
                      │ World stopped.          │ Resumes.
                      │ No heartbeats sent.     │ Thinks it's
                      │ No lease renewed.       │ still leader!
                      │                         │
Followers:            │ timeout... new leader!  │
                      │                         │
                      ▼                         ▼
              New leader elected         OLD leader sends
              at t=15                    stale commands!

MITIGATIONS:
- Fencing tokens (most robust)
- Leader checks lease validity AFTER every GC-susceptible operation
- Use languages/runtimes with predictable pause behavior
- Cooperative GC scheduling (pause only when not leader-critical)
```

### Clock Skew with Lease-Based Approaches

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Leader clock slow | Thinks lease valid longer than it is | Use conservative renewal (TTL/3) |
| Follower clock fast | Takes over before lease truly expired | Wait extra safety margin |
| NTP jump | Sudden large adjustment | Use monotonic clocks for timeouts |
| Leap seconds | Clock jumps backward | Monotonic clock immune |

### Byzantine Failures

Standard leader election assumes crash-stop (nodes either work correctly or crash). Byzantine failures break these assumptions:

- Compromised leader sends conflicting commands to different nodes
- Node lies about its ID to win Bully election  
- Node claims to have a lease it doesn't hold

**Solution**: Byzantine Fault Tolerant (BFT) consensus (PBFT, HotStuff) - requires 3f+1 nodes to tolerate f Byzantine faults, significantly more expensive.

---

## 10. Real-World Implementations

### Apache Kafka

**ZooKeeper-based Controller Election (legacy)**:
- One broker becomes the **Controller** via ZK ephemeral node `/controller`
- Controller handles partition assignment, replica management, broker lifecycle
- On controller failure: ZK session expires → ephemeral node deleted → other brokers race to create it

**KRaft Mode (Raft-based, current)**:
- Eliminates ZooKeeper dependency
- Dedicated controller quorum (typically 3-5 nodes) running Raft
- Active controller = Raft leader
- Metadata stored as Raft log (event-sourced)
- Faster failover (no ZK session timeout delay)

```
KAFKA KRAFT ARCHITECTURE:
═════════════════════════

  ┌─────────────────────────────────────┐
  │         Controller Quorum           │
  │                                     │
  │  ┌────┐    ┌────┐    ┌────┐        │
  │  │ C1 │◄──►│ C2 │◄──►│ C3 │  Raft  │
  │  │(L) │    │(F) │    │(F) │        │
  │  └────┘    └────┘    └────┘        │
  │     │                               │
  └─────│───────────────────────────────┘
        │ metadata updates
        ▼
  ┌──────────┐ ┌──────────┐ ┌──────────┐
  │ Broker 1 │ │ Broker 2 │ │ Broker 3 │
  │(partitions)│(partitions)│(partitions)│
  └──────────┘ └──────────┘ └──────────┘
```

### Elasticsearch

**Zen Discovery (legacy, pre-7.x)**:
- Ping-based discovery with configurable `minimum_master_nodes`
- Split-brain prone if `minimum_master_nodes` misconfigured
- Required manual setting: `(master_eligible_nodes / 2) + 1`

**New Election Algorithm (7.x+)**:
- Based on Raft-like consensus (not pure Raft)
- Automatic quorum management
- No `minimum_master_nodes` setting needed
- Voting configuration managed automatically
- Faster election, stronger consistency guarantees

### Redis Sentinel

```
REDIS SENTINEL LEADER ELECTION FOR FAILOVER:
═════════════════════════════════════════════

Step 1: Sentinel detects master failure (SDOWN → ODOWN)
Step 2: Sentinel that detects failure requests to be failover leader
Step 3: Uses Raft-like voting among sentinels
Step 4: Elected sentinel performs failover (promotes replica)

  ┌──────────┐     ┌──────────┐     ┌──────────┐
  │Sentinel 1│     │Sentinel 2│     │Sentinel 3│
  └────┬─────┘     └────┬─────┘     └────┬─────┘
       │                 │                 │
       │ "master down!"  │                 │
       │                 │                 │
       ├──vote-for-me───►│                 │
       ├──vote-for-me────────────────────►│
       │                 │                 │
       │◄──granted───────┤                 │
       │◄──granted─────────────────────────┤
       │                                   
       │ Majority! I lead the failover     
       │                                   
       ├──SLAVEOF NO ONE──► Replica R2     
       │ (promotes R2 to master)           
       │                                   
       ├──SLAVEOF R2──► other replicas     
```

### Kubernetes

**Leader Election for Controllers/Scheduler**:
- Uses **Lease objects** (coordination.k8s.io/v1 API)
- Controller acquires lease via optimistic concurrency (resourceVersion)
- Must renew before `leaseDurationSeconds` expires
- Other candidates watch and attempt acquisition after `renewDeadline + retryPeriod`

```yaml
apiVersion: coordination.k8s.io/v1
kind: Lease
metadata:
  name: kube-scheduler
  namespace: kube-system
spec:
  holderIdentity: "scheduler-node-1"
  leaseDurationSeconds: 15
  acquireTime: "2024-01-15T10:00:00Z"
  renewTime: "2024-01-15T10:00:05Z"
  leaseTransitions: 3
```

**Key Parameters**:
- `--leader-elect=true`
- `--leader-elect-lease-duration=15s`
- `--leader-elect-renew-deadline=10s`
- `--leader-elect-retry-period=2s`

### Google Chubby

- Paxos-based lock service (5 replicas, one master)
- Provides **advisory and sequencer-based locks** for leader election
- Clients acquire a lock file to become leader
- Lock includes a **sequencer** (fencing token) to prevent stale leaders
- Used internally by BigTable, GFS, MapReduce for master election
- Lock delay: Chubby waits ~seconds before allowing new lock acquisition (prevents thrashing)

### Apache Flink

- **JobManager** leader election for high availability
- Supports ZooKeeper or Kubernetes-based election
- Standby JobManagers recover from checkpointed state
- Leader stores metadata in distributed storage (HDFS/S3)

### HDFS NameNode Active/Standby

```
HDFS HA WITH ZKFC:
══════════════════

  ┌─────────┐          ┌─────────┐
  │ Active  │          │ Standby │
  │NameNode │          │NameNode │
  └────┬────┘          └────┬────┘
       │                     │
  ┌────┴────┐          ┌────┴────┐
  │  ZKFC   │          │  ZKFC   │
  │(monitor)│          │(monitor)│
  └────┬────┘          └────┬────┘
       │                     │
       └──────────┬──────────┘
                  │
           ┌──────┴──────┐
           │  ZooKeeper  │
           │  Ensemble   │
           │             │
           │ /ha-nn/     │
           │  ActiveLock │
           └─────────────┘

ZKFC (ZooKeeper Failover Controller):
1. Monitors local NameNode health
2. Maintains ZK session
3. Active ZKFC holds ephemeral lock in ZK
4. If Active NN fails:
   - ZKFC detects via health check
   - Releases ZK lock (or session expires)
   - Standby's ZKFC acquires lock
   - FENCES old Active (via SSH or shared storage)
   - Promotes Standby to Active
```

---

## 11. Anti-Patterns and Pitfalls

### Anti-Pattern 1: Leader Election Without Fencing

```
WRONG:
  if (iAmLeader()) {
      // 30 seconds pass (GC, network, swap)
      writeToDatabase(data);  // STALE LEADER!
  }

RIGHT:
  token = acquireLeadership();  // get fencing token
  // ... 
  writeToDatabase(data, token); // storage validates token
```

### Anti-Pattern 2: Ignoring Clock Skew

```
WRONG:
  leaseExpiry = currentTime + 10s;
  // Assumes all clocks agree on "now"

RIGHT:
  // Leader: stop acting as leader BEFORE lease expires
  leaderDeadline = leaseExpiry - MAX_CLOCK_DRIFT - SAFETY_MARGIN;
  
  // Follower: wait AFTER lease should have expired
  followerStart = leaseExpiry + MAX_CLOCK_DRIFT + SAFETY_MARGIN;
```

### Anti-Pattern 3: Not Handling Split-Brain During Election

```
WRONG:
  // No quorum check after becoming leader
  becomeLeader();
  startServingRequests();  // might be in minority partition!

RIGHT:
  becomeLeader();
  if (!canReachMajority()) {
      stepDown();
      return;
  }
  startServingRequests();
```

### Anti-Pattern 4: Fixed Election Timeouts

```
WRONG:
  electionTimeout = 500ms;  // same for all nodes → split votes!

RIGHT:
  electionTimeout = 500ms + random(0, 500ms);  // randomized
```

### Anti-Pattern 5: Leader Doing Too Much

```
WRONG:
  // Leader processes all reads AND writes
  // → bottleneck, slow failover (lots of state to transfer)

RIGHT:
  // Leader only coordinates writes
  // Reads served by any replica (with appropriate consistency)
  // Minimal leader state for fast failover
```

### Anti-Pattern 6: Lease Renewal on Same Thread as Work

```
WRONG:
  while (isLeader) {
      doExpensiveWork();      // takes 12 seconds
      renewLease();           // too late! lease was 10s!
  }

RIGHT:
  // Background thread/goroutine for lease renewal
  go renewLeaseLoop(ctx, lease, interval=3s);
  
  while (isLeader) {
      doExpensiveWork();
  }
```

---

## 12. Architect's Guide: Choosing an Election Mechanism

### Decision Matrix

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ELECTION MECHANISM DECISION TREE                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Do you already have a coordination service (ZK/etcd/Consul)?          │
│  ├── YES → Use its built-in election (ZK ephemeral nodes / etcd lease) │
│  └── NO                                                                 │
│       │                                                                 │
│       ├── Do you need strong consistency (linearizable)?               │
│       │   ├── YES → Raft (embed library: etcd/raft, hashicorp/raft)   │
│       │   └── NO                                                        │
│       │       │                                                         │
│       │       ├── Is cluster small and stable (< 10 nodes)?            │
│       │       │   ├── YES → Bully or Ring algorithm                    │
│       │       │   └── NO → Lease-based with external store             │
│       │       │                                                         │
│       └── Running on Kubernetes?                                        │
│           └── YES → Kubernetes Lease objects                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Comparison Table

| Mechanism | Consistency | Complexity | Failure Detection | Partition Safety | Best For |
|-----------|-------------|-----------|-------------------|-----------------|----------|
| Bully | Weak | Simple | Timeout | None | Educational, tiny clusters |
| Ring | Weak | Simple | Timeout | None | Ring topologies |
| Raft | Strong (linearizable) | Moderate | Heartbeat + term | Quorum-safe | Embedded consensus |
| ZooKeeper | Strong (linearizable) | External dep | Session timeout | Quorum-safe | JVM ecosystem |
| etcd | Strong (linearizable) | External dep | Lease TTL | Quorum-safe | Cloud-native/K8s |
| Lease-based | Depends on store | Simple | TTL expiry | Needs fencing | Loose coordination |
| Paxos | Strong | Complex | Proposal timeout | Quorum-safe | Academic, custom systems |

### Requirements Checklist

Before choosing, answer:

1. **What's the acceptable election time?** (ms → Raft; seconds → ZK/etcd; minutes → manual)
2. **What happens during election?** (reads stall? writes stall? full outage?)
3. **How many candidates?** (3-7 → Raft; hundreds → ZK/etcd with watchers)
4. **Existing infrastructure?** (ZK already deployed? K8s? etcd?)
5. **Language ecosystem?** (JVM → ZK/Curator; Go → etcd; any → Raft libraries)
6. **Can you tolerate false positives?** (aggressive timeout = fast failover but flapping)
7. **Do you need fencing?** (always yes for writes to external storage)

### Architecture Patterns

**Pattern: Consensus Group as Election Service**
```
Use a small Raft/Paxos group (3-5 nodes) to elect leaders
for a much larger fleet of workers.

  ┌─────────────────────┐
  │  Election Service   │
  │  (3 nodes, Raft)    │ ← provides leader election as-a-service
  └──────────┬──────────┘
             │
    ┌────────┼────────┐
    ▼        ▼        ▼
 Service  Service  Service   ← 100s of instances, one is leader
```

**Pattern: Hierarchical Election**
```
Global leader → Regional leaders → Shard leaders

Reduces blast radius: regional partition only affects that region's leader
```

**Pattern: Leader + Standby with Warm Cache**
```
  Active Leader: full state in memory, serving requests
  Standby: tailing the log, maintaining warm cache
  
  Failover: standby has state ready, near-instant promotion
  (Used by: HDFS NameNode, PostgreSQL streaming replication)
```

---

## Summary

Leader election is not a single algorithm but a **spectrum of trade-offs**:

- **Simplicity** (Bully) vs. **Correctness** (Raft/Paxos)
- **Speed of detection** vs. **False positive rate**
- **Self-contained** (embedded Raft) vs. **External dependency** (ZK/etcd)

The universal truth: **a leader is only as safe as its fencing mechanism**. Without fencing tokens, any leader election is vulnerable to stale leaders causing split-brain writes. Design the fencing boundary first, then choose the election mechanism.
