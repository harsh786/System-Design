# Lease Mechanism in Distributed Systems

## 1. Problem Statement

In distributed systems, mutual exclusion is essential for coordinating access to shared resources. Traditional locks provide this, but suffer from a fatal flaw: **if the lock holder crashes, the lock is held forever**.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    THE DISTRIBUTED LOCK PROBLEM                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Client A              Lock Server              Client B              │
│  ────────              ───────────              ────────              │
│      │                      │                      │                  │
│      │── ACQUIRE_LOCK ─────►│                      │                  │
│      │◄── GRANTED ──────────│                      │                  │
│      │                      │                      │                  │
│      │  [performs work]     │                      │                  │
│      │                      │                      │                  │
│      ╳ ← CRASH!            │                      │                  │
│                             │                      │                  │
│   (never releases)         │◄── ACQUIRE_LOCK ─────│                  │
│                             │                      │                  │
│                             │── DENIED (locked) ──►│                  │
│                             │                      │                  │
│                             │   ┌──────────────────────────┐         │
│                             │   │ Client B BLOCKED FOREVER │         │
│                             │   │ Lock is PERMANENTLY STUCK│         │
│                             │   └──────────────────────────┘         │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

**The fundamental question**: How do we provide time-bounded mutual exclusion that self-heals on failures, without requiring manual intervention?

Scenarios where this problem manifests:
- Leader election: elected leader crashes, no new leader can emerge
- File write locks: writer crashes mid-write, file locked permanently
- Resource reservation: reserved resource never released
- Session management: orphaned sessions consume server resources indefinitely

---

## 2. Definition

> **A lease is a time-bounded contract between a server (lessor) and a client (lessee). The server promises to honor the lease terms until expiry. The client must renew before expiry to maintain the contract.**

The concept was formally introduced by Cary Gray and David Cheriton in their 1989 paper *"Leases: An Efficient Fault-Tolerant Mechanism for Distributed File Cache Consistency"*.

```
┌────────────────────────────────────────────────────────────────┐
│                       LEASE CONTRACT                             │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│   LESSOR (Server)                    LESSEE (Client)            │
│   ┌─────────────┐                   ┌─────────────┐            │
│   │             │                   │             │            │
│   │  Grants     │── lease_id ──────►│  Holds      │            │
│   │  Tracks     │── expiry_time ───►│  Renews     │            │
│   │  Enforces   │── permissions ───►│  Operates   │            │
│   │             │                   │             │            │
│   └─────────────┘                   └─────────────┘            │
│                                                                  │
│   Server's Promise:                  Client's Obligation:       │
│   • Honor lease terms until expiry   • Renew before expiry      │
│   • Not grant conflicting lease      • Cease operations on      │
│     while active                       expiry                   │
│   • Track lease state                • Not assume validity      │
│                                        after expiry             │
│                                                                  │
│   Duration: T seconds (configured per use case)                 │
│   Renewal: Client must request renewal before T elapses         │
│   Expiry: Automatic — no explicit release required              │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

A lease can be thought of as a **self-destructing permission slip**. Unlike a lock that persists until released, a lease continuously decays toward invalidity. Only active renewal keeps it alive.

---

## 3. Core Properties

### 3.1 Time-Bounded: Expires Automatically

```
    Lease Granted                    Lease Expires
         │                                │
         ▼                                ▼
    ─────┼════════════════════════════════┼─────────── time
         │◄──── Lease Duration (TTL) ────►│
         │                                │
         │   LEASE VALID: holder has      │  LEASE EXPIRED:
         │   exclusive rights             │  anyone can acquire
```

- No deadlocks possible: every lease has a finite lifetime
- System self-heals: maximum blocking time = lease duration
- Bounded unavailability: worst-case wait = one lease period

### 3.2 Holder Must Renew Before Expiry

```
    T=0          T=15         T=30         T=45         T=60
     │            │            │            │            │
     ▼            ▼            ▼            ▼            ▼
     ┼════════════┼════════════┼════════════┼════════════┼
     │            │            │            │            │
  GRANT        RENEW        RENEW        RENEW       EXPIRES
  (TTL=30s)   (TTL=30s)    (TTL=30s)    (TTL=30s)   (if not
               extends to   extends to   extends to   renewed)
               T=45         T=60         T=75
```

- Renewal is the heartbeat proving liveness
- Failure to renew = presumed dead
- Renewal should happen well before expiry (typically at TTL/2)

### 3.3 After Expiry: Anyone Can Acquire

This is the key self-healing property. No coordinator needed to "break" a stuck lock.

### 3.4 Fault-Tolerant

| Failure Mode              | Behavior                                    |
|---------------------------|---------------------------------------------|
| Client crashes            | Lease expires → resource freed              |
| Network partition         | Lease expires → resource freed              |
| Client GC pause           | If pause > TTL → lease expires              |
| Server crashes            | On recovery: check stored leases + time     |
| Clock drift               | Addressed via safety margins                |

---

## 4. Lease Algorithm

### 4.1 Protocol Steps

```
┌──────────────────────────────────────────────────────────────────────┐
│                      LEASE PROTOCOL                                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│   Client                              Server                          │
│   ──────                              ──────                          │
│      │                                   │                            │
│  ┌───┤  1. REQUEST_LEASE(resource_id)    │                            │
│  │   │─────────────────────────────────►│                            │
│  │   │                                   │  [check: is resource       │
│  │   │                                   │   currently leased?]       │
│  │   │                                   │                            │
│  │   │  2. GRANT(lease_id, expiry, tok)  │  [if free: grant]         │
│  │   │◄─────────────────────────────────│  [if taken: reject]        │
│  │   │                                   │                            │
│  │   │  3. PERFORM OPERATIONS           │                            │
│  │   │     (while now < expiry - margin) │                            │
│  │   │                                   │                            │
│  │   │  4. RENEW_LEASE(lease_id)         │  [at T/2 interval]        │
│  │   │─────────────────────────────────►│                            │
│  │   │                                   │  [extend expiry]           │
│  │   │  5. RENEWED(new_expiry)           │                            │
│  │   │◄─────────────────────────────────│                            │
│  │   │                                   │                            │
│  │   │  ... repeat 3-5 ...              │                            │
│  │   │                                   │                            │
│  │   │  6. RELEASE_LEASE(lease_id)       │  [optional: early release]│
│  │   │─────────────────────────────────►│                            │
│  └───┤                                   │  [mark resource free]      │
│      │                                   │                            │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 Lease Lifecycle Timeline

```
 Client A                    Server                     Client B
    │                          │                           │
    │──── REQUEST(R1) ────────►│                           │
    │                          │                           │
    │◄─── GRANT ──────────────│                           │
    │     lease_id=L1          │                           │
    │     expiry=T+30          │                           │
    │     token=42             │                           │
    │                          │                           │
    │  ┌─ WORKING ──┐         │                           │
    │  │  read/write │         │                           │
    │  │  resource   │         │◄──── REQUEST(R1) ────────│
    │  └─────────────┘         │                           │
    │                          │──── REJECTED ────────────►│
    │                          │     (lease active)         │
    │                          │                           │
    │──── RENEW(L1) ─────────►│         (T+15)            │
    │◄─── RENEWED ────────────│                           │
    │     expiry=T+45          │                           │
    │                          │                           │
    │  ┌─ WORKING ──┐         │                           │
    │  │  continue   │         │                           │
    │  └─────────────┘         │                           │
    │                          │                           │
    ╳ CRASH                    │                           │
                               │                           │
    (no renewal)               │         (T+45)            │
                               │  [lease L1 expired]       │
                               │                           │
                               │◄──── REQUEST(R1) ────────│
                               │                           │
                               │──── GRANT ───────────────►│
                               │     lease_id=L2           │
                               │     expiry=T+75           │
                               │     token=43              │
                               │                           │
```

### 4.3 Server-Side Data Structure

```python
class LeaseManager:
    def __init__(self):
        self.leases = {}              # resource_id -> LeaseInfo
        self.expiry_heap = []         # min-heap of (expiry_time, resource_id)
        self.next_token = 0           # monotonically increasing fencing token

    def request_lease(self, resource_id, client_id, duration):
        self._expire_stale_leases()

        if resource_id in self.leases:
            existing = self.leases[resource_id]
            if existing.expiry > current_time():
                return REJECTED  # Still active

        self.next_token += 1
        expiry = current_time() + duration
        lease = LeaseInfo(
            lease_id=generate_id(),
            resource_id=resource_id,
            client_id=client_id,
            expiry=expiry,
            fencing_token=self.next_token
        )
        self.leases[resource_id] = lease
        heappush(self.expiry_heap, (expiry, resource_id))
        return GRANTED(lease)

    def renew_lease(self, lease_id, resource_id, client_id, duration):
        lease = self.leases.get(resource_id)
        if not lease or lease.lease_id != lease_id:
            return REJECTED
        if lease.client_id != client_id:
            return REJECTED
        if lease.expiry < current_time():
            return EXPIRED  # Too late

        lease.expiry = current_time() + duration
        heappush(self.expiry_heap, (lease.expiry, resource_id))
        return RENEWED(lease.expiry)

    def _expire_stale_leases(self):
        now = current_time()
        while self.expiry_heap and self.expiry_heap[0][0] <= now:
            expiry, resource_id = heappop(self.expiry_heap)
            lease = self.leases.get(resource_id)
            if lease and lease.expiry <= now:
                del self.leases[resource_id]
```

---

## 5. Lease vs Lock

### 5.1 Conceptual Difference

```
┌─────────────────────────────────────────────────────────────────┐
│                    LOCK (Traditional)                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ACQUIRE ══════════════════════════════════════════ RELEASE      │
│      │                                                  │        │
│      │◄────────── HELD INDEFINITELY ───────────────────►│        │
│      │                                                  │        │
│   If holder crashes: ════════════════════════════════════════►∞   │
│                       STUCK FOREVER (or until manual fix)         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    LEASE (Time-Bounded)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│   GRANT ═══════╗  RENEW ═══════╗  RENEW ═══════╗  EXPIRES       │
│      │         ║     │         ║     │         ║     │          │
│      │◄─ TTL ─►║     │◄─ TTL ─►║     │◄─ TTL ─►║     │          │
│      │         ║     │         ║     │         ║     │          │
│   If holder crashes: ═══════════════════╗                        │
│                                         ║ EXPIRES AUTOMATICALLY  │
│                                         ╚═══► resource freed     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Property Comparison

| Property                  | Traditional Lock           | Lease                              |
|---------------------------|----------------------------|------------------------------------|
| Duration                  | Infinite (until release)   | Finite (TTL)                       |
| Expiry                    | Never (explicit release)   | Automatic at TTL                   |
| Crash recovery            | Manual intervention        | Self-healing (wait for expiry)     |
| Deadlock possible         | Yes                        | No (time-bounded)                  |
| Network partition          | Permanent block            | Bounded block (max TTL)            |
| Complexity                | Simple acquire/release     | Renewal logic needed               |
| Overhead                  | Low (no heartbeats)        | Moderate (periodic renewals)       |
| Safety after holder crash | Unsafe (lock stuck)        | Safe (expires)                     |
| Liveness                  | Poor (can block forever)   | Good (bounded wait)                |
| Split-brain risk          | Low (once acquired)        | Higher (clock skew can cause dual) |
| Needs fencing token       | Ideally yes                | **Absolutely yes**                 |

### 5.3 The Identity

```
    Lease ≈ Lock + Timeout + Renewal Protocol + Fencing Token
```

A lease is NOT simply "a lock with a timeout." It includes:
- Formal contract semantics (server promises, client obligations)
- Renewal protocol (heartbeat mechanism)
- Fencing tokens (monotonic counters for safety)
- Defined behavior on all failure modes

---

## 6. Clock Skew Problem

### 6.1 The Danger

In distributed systems, clocks are **never perfectly synchronized**. This creates a fundamental safety hazard with leases.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CLOCK SKEW DANGER                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  SCENARIO 1: Client clock is AHEAD of server                         │
│  ─────────────────────────────────────────────                       │
│                                                                       │
│  Server clock:  ──────────────[T=100: expires]──────────────         │
│                                     │                                 │
│  Client clock:  ───────[T=100: thinks expired]──────────────         │
│                              │                                        │
│                              ▼                                        │
│                   Client STOPS EARLY                                  │
│                   (safe but reduces availability)                     │
│                                                                       │
│                                                                       │
│  SCENARIO 2: Client clock is BEHIND server  ⚠️  DANGEROUS            │
│  ──────────────────────────────────────────                          │
│                                                                       │
│  Server clock:  ──────────────[T=100: expires]──────────────         │
│                                     │                                 │
│  Client clock:  ──────────────────────────[T=100: thinks valid]──    │
│                                                  │                    │
│                                                  ▼                    │
│  Server has ALREADY granted lease to Client B!                       │
│  But Client A still thinks its lease is valid!                       │
│                                                                       │
│       ┌─────────────────────────────────────────┐                    │
│       │  TWO CLIENTS THINK THEY HOLD THE LEASE  │                    │
│       │  ──► DATA CORRUPTION / SPLIT BRAIN      │                    │
│       └─────────────────────────────────────────┘                    │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Detailed Clock Skew Timeline

```
                    Server Time
                    ──────────────────────────────────────────────►
                    T=0        T=50       T=100      T=150

  Server:           │══════════════════════│
                    Grant to A             Lease expires
                    (TTL=100)              Grant to B ═══════════

  Client A          │══════════════════════════════│
  (clock behind     Grant                         A thinks lease
   by 30s):                                       is still valid!
                                                  ↕
                                           OVERLAP PERIOD
                                           Both A and B operate!
                                                  ↕
  Client B:                                │══════════════════════
                                           Granted lease
                                           Starts operating

  RESULT:  ┌────────────────────────────────────────┐
           │  MUTUAL EXCLUSION VIOLATED!            │
           │  A and B both writing to resource      │
           │  between server T=100 and T=130        │
           └────────────────────────────────────────┘
```

### 6.3 Solutions

**Solution 1: Safety Margin (Client-Side Early Expiry)**

```
  Actual lease duration:    ═══════════════════════════ (30 seconds)
  Client's usable window:  ═══════════════════════     (30 - margin)
                                                  │
                                            safety margin
                                            (e.g., 5 seconds)

  Rule: Client considers lease expired at (expiry - safety_margin)
  This absorbs clock skew up to `safety_margin` seconds.
```

**Solution 2: Use Duration, Not Absolute Time**

```
  Instead of:  "Lease expires at timestamp 1700000100"
  Use:         "Lease valid for 30 seconds from grant"

  Client starts local timer at moment of receiving grant.
  No dependency on synchronized absolute clocks.
  Still vulnerable to: GC pauses, process suspension.
```

**Solution 3: Fencing Tokens (The Real Solution)**

```
  Even with clock skew, safety is guaranteed if the resource
  itself validates fencing tokens:

  Client A: token=42, writes with token=42
  Client B: token=43, writes with token=43

  Resource/Storage layer:
    if incoming_token < last_seen_token:
        REJECT operation   ← This catches stale lease holders
```

---

## 7. Lease Types

### 7.1 Write Lease

Only the lease holder is permitted to write to the resource.

```
  Client A (write lease holder)     Storage
       │                               │
       │── WRITE(data, token=42) ─────►│  ✓ Accepted
       │                               │
  Client B (no lease)                  │
       │── WRITE(data, token=41) ─────►│  ✗ Rejected (stale token)
       │                               │
```

**Use cases**: HDFS file writes, exclusive blob access, leader writes

### 7.2 Read Lease

Server guarantees the data will NOT be modified during the lease period. Clients can cache data locally with confidence.

```
  ┌─────────────────────────────────────────────────────────────┐
  │                     READ LEASE                               │
  ├─────────────────────────────────────────────────────────────┤
  │                                                              │
  │  Server grants read lease for resource R to Client A        │
  │                                                              │
  │  Server's promise: "I will NOT allow writes to R until      │
  │  this read lease expires or is explicitly released."         │
  │                                                              │
  │  Client A can cache R locally without checking server.      │
  │                                                              │
  │  If a writer arrives:                                       │
  │    Option 1: Writer waits until read leases expire          │
  │    Option 2: Server revokes read leases (callback)          │
  │    Option 3: Writer fails immediately                       │
  │                                                              │
  └─────────────────────────────────────────────────────────────┘
```

**Use cases**: DNS TTL, distributed caches, Chubby read caching

### 7.3 Advisory Lease

Not enforced by the server — purely a hint for coordination. Clients cooperate voluntarily.

```
  Advisory lease = "I intend to work on this"
  Other clients can still access the resource.
  Purpose: reduce contention, avoid duplicate work.
```

**Use cases**: File edit hints (Google Docs showing "User X is editing"), work queue deduplication

### 7.4 Master Lease

Grants leadership authority for a bounded time period. The master lease holder acts as the coordinator/leader.

```
  ┌──────────────────────────────────────────────────────┐
  │  Node A: Master (lease valid T=0 to T=30)            │
  │  ─────────────────────────────────────               │
  │  • Accepts client requests                           │
  │  • Coordinates writes                                │
  │  • Replicates to followers                           │
  │                                                      │
  │  Nodes B, C: Followers                               │
  │  ─────────────────────                               │
  │  • Forward requests to master                        │
  │  • If master lease expires → election triggered      │
  │                                                      │
  └──────────────────────────────────────────────────────┘
```

**Use cases**: Chubby master, Bigtable tablet server master, Kubernetes leader election

---

## 8. Lease Renewal Patterns

### 8.1 Periodic Renewal at T/2

The standard pattern: renew at half the lease duration.

```
  TTL = 30 seconds
  Renewal interval = 15 seconds (TTL/2)

  T=0         T=15        T=30        T=45        T=60
   │           │           │           │           │
   ▼           ▼           ▼           ▼           ▼
   GRANT       RENEW       RENEW       RENEW       RENEW
   │═══════════│═══════════│═══════════│═══════════│
   expiry=30   expiry=45   expiry=60   expiry=75   expiry=90

  Why T/2?
  • Gives one full retry window before expiry
  • If renewal at T/2 fails, still have T/2 time to retry
  • Balances between freshness and network overhead
```

### 8.2 Grace Period for Network Jitter

```
  ┌─────────────────────────────────────────────────────────┐
  │  Lease TTL: 30s                                          │
  │  Renewal at: 15s (T/2)                                   │
  │  Grace period: 5s                                        │
  │                                                          │
  │  Timeline:                                               │
  │  ═══════════════════════════════╪═════╪                  │
  │  0         15        25        30    35                  │
  │            │         │         │     │                   │
  │         attempt    last      nominal grace              │
  │         renewal    chance    expiry  expires             │
  │                    before                                │
  │                    giving up                             │
  │                                                          │
  │  Server may extend grace period for in-flight renewals  │
  └─────────────────────────────────────────────────────────┘
```

### 8.3 Exponential Backoff on Renewal Failure

```python
def renewal_loop(lease, base_interval):
    consecutive_failures = 0
    max_failures = 3  # Give up threshold

    while lease.is_active():
        sleep(base_interval)

        try:
            renew(lease)
            consecutive_failures = 0
        except RenewalFailed:
            consecutive_failures += 1

            if consecutive_failures >= max_failures:
                lease.invalidate()
                cease_all_operations()
                return

            # Retry with backoff (but don't exceed remaining time)
            backoff = min(
                base_interval * (2 ** consecutive_failures),
                lease.time_remaining() - safety_margin
            )
            sleep(backoff)
```

### 8.4 When to Give Up

Decision criteria for abandoning a lease:

| Condition                         | Action                    |
|-----------------------------------|---------------------------|
| N consecutive renewal failures    | Cease operations          |
| Remaining time < safety margin    | Cease operations          |
| Server explicitly revokes         | Cease immediately         |
| Network unreachable confirmed     | Cease operations          |
| Local clock jump detected         | Cease and re-acquire      |

---

## 9. Real-World Implementations

### 9.1 Google Chubby

Chubby uses **session leases** as its core abstraction. A Chubby session is essentially a lease between client and Chubby cell.

```
  Client ◄──── KeepAlive (every ~12s) ────► Chubby Master
                                              │
                                              │ Session lease
                                              │ (default: 12s)
                                              │
  On master failover:
    • Client's session lease extended during grace period
    • New master honors existing sessions
    • Client receives "jeopardy" event if renewal uncertain
```

- Session lease default: 12 seconds
- KeepAlive interval: ~12 seconds (piggybacked on session extension)
- Grace period on failover: 45 seconds
- Read leases: cache invalidation via lease mechanism

### 9.2 ZooKeeper

ZooKeeper's **session timeout** is a lease mechanism.

```
  Client ──── heartbeat (tickTime) ────► ZooKeeper Ensemble
                                          │
                                          │ Session valid for
                                          │ negotiated timeout
                                          │ (default: 2× tickTime
                                          │  to 20× tickTime)
                                          │
  Ephemeral nodes: deleted when session lease expires
  Watches: invalidated when session expires
```

- Session timeout range: 2×tickTime to 20×tickTime
- tickTime default: 2000ms
- Ephemeral znodes = resources held by lease
- Session expiry = all ephemeral nodes deleted atomically

### 9.3 HDFS (Hadoop Distributed File System)

NameNode grants **file write leases** to clients.

```
  Client                    NameNode
    │                          │
    │── open(file, WRITE) ────►│
    │◄── lease granted ────────│  (soft limit: 60s, hard limit: 1hr)
    │                          │
    │── write blocks ─────────►│
    │── renew lease ──────────►│  (every 30s)
    │── close(file) ──────────►│
    │◄── lease released ───────│
    │                          │
  On crash:
    • Soft limit (60s): another client can take over (lease recovery)
    • Hard limit (1hr): NameNode forcibly revokes
```

- Soft limit: 60 seconds (other clients can recover the lease)
- Hard limit: 1 hour (NameNode auto-revokes)
- Renewal: every ~30 seconds
- Lease recovery: another client can finalize/close the file

### 9.4 etcd

etcd provides an explicit **Lease API** with TTL.

```go
// Grant a lease with 15-second TTL
lease, _ := client.Grant(ctx, 15)

// Attach key to lease (key deleted when lease expires)
client.Put(ctx, "/services/api/node1", "alive",
    clientv3.WithLease(lease.ID))

// Keep lease alive (auto-renewal)
ch, _ := client.KeepAlive(ctx, lease.ID)

// Revoke lease (immediate cleanup)
client.Revoke(ctx, lease.ID)
```

- Used for: service discovery (TTL on registration keys), leader election
- KeepAlive sends renewals at TTL/3 interval
- On revoke/expiry: all attached keys deleted atomically

### 9.5 Kubernetes

Kubernetes uses **Lease objects** (coordination.k8s.io/v1) for leader election.

```yaml
apiVersion: coordination.k8s.io/v1
kind: Lease
metadata:
  name: kube-controller-manager
  namespace: kube-system
spec:
  holderIdentity: "controller-manager-node-1"
  leaseDurationSeconds: 15
  acquireTime: "2024-01-15T10:00:00Z"
  renewTime: "2024-01-15T10:00:12Z"
  leaseTransitions: 3
```

- Controller manager, scheduler use lease-based leader election
- Default lease duration: 15 seconds
- Renew interval: 10 seconds
- Node heartbeats: Kubelet uses Lease objects (replaces Node status updates)

### 9.6 DynamoDB Lock Client

Amazon's DynamoDB lock client implements lease-based distributed locks.

```
  ┌─────────────────────────────────────────────────────┐
  │  DynamoDB Table: "locks"                             │
  │                                                      │
  │  PK: lock_key                                        │
  │  Attributes:                                         │
  │    owner_id: "client-abc-123"                        │
  │    lease_duration: 20000 (ms)                        │
  │    record_version_number: "uuid-v4"                  │
  │    expiry_time: 1700000120                           │
  │                                                      │
  │  Heartbeat: conditional update every leaseDuration/3│
  │  Acquire: conditional write (owner_id not exists     │
  │           OR expiry_time < now)                       │
  └─────────────────────────────────────────────────────┘
```

### 9.7 Azure Blob Storage

Azure provides **blob leases** for exclusive write access.

```
  PUT /container/blob?comp=lease
  x-ms-lease-action: acquire
  x-ms-lease-duration: 60       (15-60 seconds, or -1 for infinite)

  Response:
  x-ms-lease-id: <guid>

  // All subsequent writes must include lease-id
  PUT /container/blob
  x-ms-lease-id: <guid>
  [blob content]

  // Renewal
  PUT /container/blob?comp=lease
  x-ms-lease-action: renew
  x-ms-lease-id: <guid>
```

- Duration: 15-60 seconds (fixed) or infinite
- Used for: exclusive blob write, container deletion protection
- Break lease: allows forcible release with optional break period

### 9.8 Redis

Redis `EXPIRE`/`TTL` commands implement lease-like semantics on keys.

```redis
SET resource:lock "owner-123" EX 30 NX
# EX 30 = 30 second expiry (lease duration)
# NX = only if not exists (mutual exclusion)

# Renewal
EXPIRE resource:lock 30

# Safe release (Lua script for atomicity)
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
```

- Redlock algorithm: lease-based locking across multiple Redis nodes
- `SET key value EX seconds NX` = atomic lease acquisition
- No built-in fencing tokens (must implement externally)

---

## 10. Implementing Safe Leases

### 10.1 The GC Pause Problem (Why Leases Alone Are Unsafe)

```
┌─────────────────────────────────────────────────────────────────────┐
│              THE GC PAUSE DISASTER                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Client A          Lease Server         Storage           Client B   │
│     │                  │                   │                 │        │
│     │◄─ LEASE GRANTED ─│                   │                 │        │
│     │   (expires T+30) │                   │                 │        │
│     │                  │                   │                 │        │
│     │  [validates lease locally: OK]       │                 │        │
│     │                  │                   │                 │        │
│     │  ╔═══════════════════════╗           │                 │        │
│     │  ║  GC PAUSE (40 sec!)  ║           │                 │        │
│     │  ║  Process frozen       ║           │                 │        │
│     │  ║  No code executes     ║           │  (T+30)         │        │
│     │  ║                       ║           │                 │        │
│     │  ║                       ║           │◄─── WRITE ──────│        │
│     │  ║  Lease expired but   ║           │   (token=43)    │        │
│     │  ║  client doesn't know ║           │                 │        │
│     │  ╚═══════════════════════╝           │                 │        │
│     │                  │                   │                 │        │
│     │──── WRITE(data) ─────────────────────►                 │        │
│     │  (stale! lease expired during pause) │                 │        │
│     │                  │                   │                 │        │
│     │  ┌───────────────────────────────────────────┐         │        │
│     │  │ DATA CORRUPTION: A overwrites B's write!  │         │        │
│     │  └───────────────────────────────────────────┘         │        │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

**The key insight**: Checking "is my lease valid?" and then performing an operation is NOT atomic. Any pause between the check and the operation (GC, page fault, scheduling, etc.) can cause the lease to expire unnoticed.

### 10.2 Fencing Tokens: The Solution

```
┌─────────────────────────────────────────────────────────────────────┐
│              FENCING TOKENS MAKE LEASES SAFE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Lease Server: issues monotonically increasing token with each grant │
│                                                                       │
│  Client A gets lease:  token = 42                                    │
│  Client A pauses (GC)                                                │
│  Lease expires                                                       │
│  Client B gets lease:  token = 43                                    │
│  Client B writes:      WRITE(data, token=43) → Storage accepts       │
│  Client A resumes:     WRITE(data, token=42) → Storage REJECTS       │
│                                                                       │
│  Storage rule:                                                       │
│  ┌────────────────────────────────────────────┐                      │
│  │  if request.token < max_seen_token:        │                      │
│  │      REJECT("stale fencing token")         │                      │
│  │  else:                                     │                      │
│  │      max_seen_token = request.token        │                      │
│  │      ACCEPT and process request            │                      │
│  └────────────────────────────────────────────┘                      │
│                                                                       │
│  This works REGARDLESS of clock skew, GC pauses, or network delays  │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 10.3 The "Physical Time Is Unreliable" Argument

Martin Kleppmann's argument (from "Designing Data-Intensive Applications"):

1. Physical clocks can jump (NTP adjustment, leap seconds, VM migration)
2. Process pauses are unbounded (GC, swapping, scheduling)
3. Network delays are unbounded (congestion, routing changes)

**Therefore**: Any system relying solely on physical time for safety guarantees is fundamentally broken.

**Correct approach**:
- Use leases for **liveness** (availability, preventing indefinite blocking)
- Use fencing tokens for **safety** (preventing stale operations)
- Lease duration is a performance/availability tradeoff, NOT a safety mechanism

### 10.4 Complete Safe Lease Pattern

```python
class SafeLeaseClient:
    def __init__(self, lease_server, storage):
        self.server = lease_server
        self.storage = storage
        self.lease = None
        self.fencing_token = None

    def acquire(self, resource_id):
        response = self.server.request_lease(resource_id)
        if response.granted:
            self.lease = response.lease
            self.fencing_token = response.fencing_token
            self._start_renewal_loop()
            return True
        return False

    def write(self, key, value):
        # Note: we check lease validity BUT we don't rely on it for safety
        # The fencing token provides safety even if this check is stale
        if not self.lease or not self.lease.appears_valid():
            raise LeaseExpiredError()

        # Fencing token included in EVERY write operation
        self.storage.write(
            key=key,
            value=value,
            fencing_token=self.fencing_token  # ← THIS is what provides safety
        )

    def _start_renewal_loop(self):
        # Runs in background thread
        while self.lease.appears_valid():
            sleep(self.lease.ttl / 2)
            try:
                self.server.renew(self.lease.id)
            except:
                self.lease.invalidate()
                break
```

---

## 11. Lease Scalability

### 11.1 Server Bookkeeping for Thousands of Leases

```
┌─────────────────────────────────────────────────────────────────┐
│                 LEASE SERVER INTERNALS                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────┐                         │
│  │  Active Leases HashMap              │  O(1) lookup            │
│  │  ─────────────────────              │                         │
│  │  resource_id → LeaseInfo            │                         │
│  │                                     │                         │
│  │  "file:/data/001" → {A, T+30, 42}  │                         │
│  │  "file:/data/002" → {B, T+45, 43}  │                         │
│  │  "lock:orders"    → {C, T+20, 44}  │                         │
│  │  ...                                │                         │
│  │  (potentially millions of entries)  │                         │
│  └─────────────────────────────────────┘                         │
│                                                                   │
│  ┌─────────────────────────────────────┐                         │
│  │  Expiry Min-Heap                    │  O(log n) insert/pop    │
│  │  ─────────────────                  │                         │
│  │                                     │                         │
│  │       [T+20]                        │                         │
│  │      /      \                       │                         │
│  │   [T+30]   [T+45]                  │                         │
│  │   /    \                            │                         │
│  │ [T+60] [T+90]                      │                         │
│  │                                     │                         │
│  │  Background thread pops expired     │                         │
│  │  leases periodically                │                         │
│  └─────────────────────────────────────┘                         │
│                                                                   │
│  ┌─────────────────────────────────────┐                         │
│  │  Timer Wheel (alternative)          │  O(1) insert/expire     │
│  │  ─────────────────────────          │                         │
│  │                                     │                         │
│  │  Slot 0: [lease1, lease5]           │                         │
│  │  Slot 1: [lease2]                   │                         │
│  │  Slot 2: []                         │                         │
│  │  Slot 3: [lease3, lease7, lease9]   │                         │
│  │  ...                                │                         │
│  │  Pointer advances each tick         │                         │
│  │  Expires all leases in current slot │                         │
│  └─────────────────────────────────────┘                         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 11.2 Efficient Expiry Tracking

| Data Structure     | Insert   | Expire (pop min) | Check min | Use case                    |
|--------------------|----------|-------------------|-----------|------------------------------|
| Min-Heap           | O(log n) | O(log n)          | O(1)      | General purpose              |
| Timer Wheel        | O(1)     | O(1) amortized    | O(1)      | High-throughput, fixed slots |
| Sorted Set (Redis) | O(log n) | O(log n)          | O(1)      | Distributed lease tracking   |
| Skip List          | O(log n) | O(log n)          | O(1)      | Concurrent access            |

### 11.3 Batch Renewal

When a single client holds many leases (e.g., a service with 1000 registered keys):

```
  Instead of:
    RENEW lease_1
    RENEW lease_2
    ...
    RENEW lease_1000    (1000 round trips!)

  Batch approach:
    RENEW_BATCH [lease_1, lease_2, ..., lease_1000]
    → Single round trip
    → Server extends all in one atomic operation

  etcd example: KeepAlive on a single lease ID,
  with many keys attached to that lease.
  One renewal keeps all keys alive.
```

**etcd's model**: Attach multiple keys to ONE lease. Renewing the single lease keeps all keys alive. This is O(1) renewal overhead regardless of key count.

---

## 12. Architect's Guide

### 12.1 Choosing Lease Duration

```
┌─────────────────────────────────────────────────────────────────────┐
│                 LEASE DURATION TRADEOFFS                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  SHORT LEASE (1-5 seconds)          LONG LEASE (30-300 seconds)      │
│  ─────────────────────────          ────────────────────────────     │
│  ✓ Fast failure detection           ✓ Low renewal overhead           │
│  ✓ Quick recovery                   ✓ Tolerates network blips        │
│  ✗ High renewal traffic             ✓ Less sensitive to latency      │
│  ✗ Sensitive to network jitter      ✗ Slow failure detection         │
│  ✗ False positives (false expiry)   ✗ Long recovery time             │
│                                                                       │
│  GUIDELINE:                                                          │
│  ──────────                                                          │
│  lease_duration = max(                                               │
│      2 × network_RTT_p99,         ← survive worst-case RTT          │
│      2 × GC_pause_max,            ← survive GC pauses               │
│      tolerable_unavailability      ← business requirement            │
│  )                                                                    │
│                                                                       │
│  Typical values:                                                     │
│    • Leader election: 10-30 seconds                                  │
│    • Service discovery: 15-60 seconds                                │
│    • File locks: 60 seconds (HDFS)                                   │
│    • Cache validity: 30-300 seconds                                  │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 12.2 System Design Decision Framework

```
  Question 1: Do I need mutual exclusion?
      YES → Consider lease
      NO  → Maybe just TTL-based caching

  Question 2: What's my failure mode?
      Client crash        → Lease handles it (auto-expiry)
      Network partition   → Lease handles it (auto-expiry)
      Split brain         → Need fencing tokens (lease alone insufficient)
      Server crash        → Need persistent lease state or consensus

  Question 3: What's acceptable unavailability?
      < 1 second   → Very short lease (aggressive), high renewal cost
      1-10 seconds → Standard lease durations
      > 30 seconds → Long leases, may need manual intervention option

  Question 4: What's my write safety requirement?
      Weak (last-writer-wins OK)   → Lease alone may suffice
      Strong (no stale writes)     → MUST use fencing tokens
```

### 12.3 Complete Architecture Pattern

```
┌─────────────────────────────────────────────────────────────────────┐
│              PRODUCTION LEASE-BASED SYSTEM                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌────────────┐         ┌──────────────────┐                        │
│  │  Client    │         │  Lease Service    │                        │
│  │            │─────────│  (Consensus-based)│                        │
│  │  • Acquire │ Request │                  │                        │
│  │  • Renew   │◄────────│  • etcd/ZK/Chubby│                        │
│  │  • Release │ Grant+  │  • Raft/ZAB      │                        │
│  │  • Fence   │ Token   │  • Persistent    │                        │
│  └─────┬──────┘         └──────────────────┘                        │
│        │                                                             │
│        │ Write(data, fencing_token)                                  │
│        ▼                                                             │
│  ┌──────────────────────────────────────┐                           │
│  │  Storage / Resource Layer             │                           │
│  │                                       │                           │
│  │  • Validates fencing token            │                           │
│  │  • Rejects stale tokens               │                           │
│  │  • Tracks max_seen_token per resource │                           │
│  │                                       │                           │
│  └──────────────────────────────────────┘                           │
│                                                                       │
│  SAFETY: Fencing tokens (logical ordering)                           │
│  LIVENESS: Lease expiry (time-bounded blocking)                      │
│  DURABILITY: Consensus protocol (survives server crashes)            │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 12.4 Anti-Patterns to Avoid

| Anti-Pattern | Why It's Wrong | Correct Approach |
|---|---|---|
| Lease without fencing token | GC pause → stale write | Always pair with fencing |
| Relying on synchronized clocks | Clock skew → dual holders | Use duration + safety margin |
| Infinite lease duration | Defeats the purpose | Use finite TTL, always |
| Checking lease then acting non-atomically | TOCTOU race | Include token in every operation |
| Single lease server (no replication) | SPOF | Use consensus-backed store |
| Lease renewal in same thread as work | GC pauses both | Separate renewal thread |

### 12.5 Complementary Mechanisms

```
  LEASE alone provides:
    ✓ Liveness (bounded blocking)
    ✓ Crash recovery
    ✗ Safety under async conditions

  LEASE + FENCING TOKEN provides:
    ✓ Liveness
    ✓ Crash recovery
    ✓ Safety (stale operations rejected)

  LEASE + FENCING TOKEN + CONSENSUS provides:
    ✓ Liveness
    ✓ Crash recovery
    ✓ Safety
    ✓ Durability (survives lease server crashes)
    ✓ Consistency (linearizable lease grants)
```

---

## Summary

| Aspect | Key Takeaway |
|--------|-------------|
| What | Time-bounded permission contract that auto-expires |
| Why | Prevents indefinite blocking on holder failure |
| How | TTL + periodic renewal + fencing tokens |
| Safety | Requires fencing tokens — lease alone is insufficient |
| Liveness | Guaranteed by bounded expiry time |
| Duration | Balance: failure detection speed vs. false expiry risk |
| Clock skew | Use duration-based + safety margins, never trust absolute time |
| Production | Always back with consensus (etcd, ZK, Chubby) |

---

## References

1. Gray, C. & Cheriton, D. (1989). "Leases: An Efficient Fault-Tolerant Mechanism for Distributed File Cache Consistency"
2. Burrows, M. (2006). "The Chubby Lock Service for Loosely-Coupled Distributed Systems"
3. Kleppmann, M. (2016). "Designing Data-Intensive Applications" — Chapter 8: Distributed Locks and Leases
4. Kleppmann, M. (2016). "How to do distributed locking" (blog post on fencing tokens)
5. Hunt, P. et al. (2010). "ZooKeeper: Wait-free Coordination for Internet-scale Systems"
6. etcd documentation: Lease API
7. Kubernetes documentation: coordination.k8s.io/v1 Lease
