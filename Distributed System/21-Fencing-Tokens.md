# Fencing Tokens

## 1. Problem Statement

Distributed locks are fundamentally unsafe without fencing. The core issue: **a node may believe it holds a lock when it actually does not**.

Three scenarios cause this:

| Cause | Mechanism |
|-------|-----------|
| GC Pause | Stop-the-world garbage collection freezes the process for seconds |
| Network Delay | Packets delayed beyond lock TTL |
| Clock Skew | Node's clock drifts; it miscalculates expiry |

### The "Zombie Leader" Problem

A process that held a lock, lost it (due to expiry), but continues operating as if it still holds the lock is a **zombie**. It performs writes to shared resources under the false assumption of mutual exclusion.

This is not a theoretical concern. It happens in production at scale. Every major distributed systems outage post-mortem catalog (Google, Amazon, Microsoft) contains instances of zombie leaders corrupting state.

**The fundamental insight**: A lock's TTL is a time-based heuristic. Time cannot provide safety guarantees in asynchronous distributed systems. You need a logical mechanism — fencing tokens — to enforce safety regardless of timing.

---

## 2. The Unsafe Scenario (Without Fencing)

### Sequence of Events

1. **T=0**: Node A acquires lock with TTL=10s
2. **T=1**: Node A begins processing, preparing a write
3. **T=2**: Node A enters a GC pause (stop-the-world)
4. **T=10**: Lock expires. Node A is still paused.
5. **T=11**: Node B acquires the same lock (legitimately)
6. **T=12**: Node B writes to shared resource (valid)
7. **T=15**: Node A wakes from GC pause
8. **T=16**: Node A writes to shared resource — **CORRUPTION**

Node A has no idea 13 seconds have passed. From its perspective, it acquired the lock moments ago.

### ASCII Timeline

```
Time ──────────────────────────────────────────────────────────────────────►

         Lock TTL = 10s
         ├──────────────────────┤

Node A   ┌──ACQUIRE──┐                                    ┌──WRITE──┐
         │  Token: ? │    ██████████████████████████████   │ STALE!  │
         └───────────┘    █  GC PAUSE (13 seconds)    █   │ CORRUPT │
                          █  Process completely frozen █   └─────────┘
                          ██████████████████████████████

Node B                              ┌──ACQUIRE──┐  ┌──WRITE──┐
                                    │  (valid)  │  │  (valid)│
                                    └───────────┘  └─────────┘

Lock     ╠═══ Held by A ═══╣ EXPIRED ╠═══ Held by B ═══════════════════════
State

Resource                                           [B writes] [A writes]
                                                       ✓          ✗ !!!
         ▼                 ▼         ▼              ▼          ▼
         T=0              T=2       T=10           T=12       T=16

         ─── RESULT: BOTH A AND B WRITE TO RESOURCE ───
         ─── MUTUAL EXCLUSION VIOLATED ───
         ─── DATA CORRUPTION / SPLIT BRAIN ───
```

### Why "Check-Then-Act" Fails

You might think: "Node A should check if it still holds the lock before writing."

```
if (lock.isHeld()) {    // <-- Check passes (stale local state)
    // GC pause could happen HERE, between check and write
    resource.write(data); // <-- Write happens after lock expired
}
```

This is a classic TOCTOU (Time-Of-Check-Time-Of-Use) race. The check and the action are not atomic. Any amount of time can elapse between them due to:
- GC pauses
- OS scheduling
- Page faults
- Network delays (if check is remote)

**No local check can provide safety.** Safety must be enforced at the resource.

---

## 3. Fencing Token Solution

### Core Idea

The lock service issues a **monotonically increasing token** (integer) with every lock grant. The protected resource tracks the highest token it has seen and **rejects any operation carrying a lower token**.

### How It Works

1. Lock service maintains counter `C`, starting at 0
2. Each lock grant increments `C` and returns it as the fencing token
3. Client attaches token to every write operation on the protected resource
4. Resource compares incoming token to its stored `max_token`
5. If `incoming_token < max_token` → **REJECT** (stale holder)
6. If `incoming_token >= max_token` → **ACCEPT**, update `max_token`

### ASCII Diagram: Fencing Token Prevents Corruption

```
Time ──────────────────────────────────────────────────────────────────────►

Lock     ┌─ Grant #33 ─┐    EXPIRED    ┌─ Grant #34 ─┐
Service  │  to Node A  │               │  to Node B  │
         └─────────────┘               └─────────────┘

Node A   ┌─ Acquire ──┐                                   ┌── Write ──┐
         │ token = 33  │  ████████████████████████████████ │ token: 33 │
         └─────────────┘  █     GC PAUSE (13s)           █ └─────┬─────┘
                          ████████████████████████████████       │
                                                                 │
Node B                               ┌─ Acquire ──┐ ┌─ Write ─┐ │
                                     │ token = 34  │ │token: 34│ │
                                     └─────────────┘ └────┬────┘ │
                                                          │      │
                                                          ▼      ▼
Resource ─────────────────────────────────────────────────────────────────
(Storage)                                                 │      │
                                                          │      │
         max_token = 0                          Accept    │  Reject
                                                34 >= 0  │  33 < 34
                                                max = 34  │  DENIED!
                                                          │      │
                                                          ▼      ▼
                                                       [Data]  [NOPE]
                                                       safe!   blocked!

         ─── RESULT: ONLY NODE B's WRITE SUCCEEDS ───
         ─── MUTUAL EXCLUSION PRESERVED ───
         ─── DATA INTEGRITY MAINTAINED ───
```

### Key Properties

| Property | Guarantee |
|----------|-----------|
| Monotonicity | Tokens always increase; no reuse |
| Irrevocability | Once a higher token is seen, lower tokens are permanently invalid |
| Resource-side enforcement | Safety doesn't depend on client behavior |
| Crash-safe | Resource persists max_token; survives restarts |

---

## 4. Algorithm

### Lock Service (Pseudocode)

```python
class FencingLockService:
    def __init__(self):
        self.counter = 0              # Persisted durably
        self.lock_holder = None
        self.lock_expiry = None

    def acquire(self, client_id, ttl):
        if self.lock_holder is None or now() > self.lock_expiry:
            self.counter += 1         # Monotonically increasing
            self.lock_holder = client_id
            self.lock_expiry = now() + ttl
            persist(self.counter)     # Durable before responding
            return LockGrant(
                token=self.counter,
                ttl=ttl,
                holder=client_id
            )
        return LOCK_BUSY
```

### Client Usage

```python
class Client:
    def do_protected_work(self, lock_service, resource):
        grant = lock_service.acquire(self.id, ttl=10)
        if grant is None:
            return FAILED_TO_ACQUIRE

        # Attach token to EVERY operation on protected resource
        result = resource.write(
            data=self.prepare_data(),
            fencing_token=grant.token   # <── Critical
        )

        if result == REJECTED:
            # We are a zombie. Abort immediately.
            self.abort()
```

### Resource Validation

```python
class ProtectedResource:
    def __init__(self):
        self.max_token = 0            # Persisted durably
        self.data = None

    def write(self, data, fencing_token):
        # The safety check
        if fencing_token < self.max_token:
            return REJECTED           # Stale token → zombie detected

        # Accept the write
        self.max_token = max(self.max_token, fencing_token)
        self.data = data
        persist(self.max_token, self.data)  # Atomic persist
        return ACCEPTED
```

### Formal Safety Property

```
∀ writes W1, W2 to resource R:
  if W1.token < W2.token and W2 was accepted before W1 arrives:
    W1 MUST be rejected

Equivalently:
  R accepts write W iff W.token >= R.max_token
```

This holds regardless of:
- Clock skew between nodes
- Network delays
- GC pauses
- Process scheduling

---

## 5. Requirements for the Protected Resource

Fencing tokens only work if the resource cooperates. This imposes strict requirements:

### 5.1 Token Validation Support

The resource MUST:
- Accept a fencing token parameter on every mutating operation
- Compare it against the stored maximum
- Reject operations with tokens lower than the maximum

This means **arbitrary storage systems cannot be fenced without modification**. You cannot use a plain MySQL database, a raw filesystem, or a vanilla HTTP API as a fenced resource without adding token validation logic.

### 5.2 Single Access Path

```
                    ┌──────────────────┐
                    │   Lock Service   │
                    │  (issues tokens) │
                    └────────┬─────────┘
                             │ token
                             ▼
┌────────┐  write+token  ┌──────────────────────┐
│ Client ├──────────────►│  Protected Resource   │
└────────┘               │  (validates tokens)   │
                         └──────────────────────┘
                                   ▲
                                   │
                              ╔════╧════╗
                              ║ NO OTHER║
                              ║ ACCESS  ║
                              ║ ALLOWED ║
                              ╚═════════╝
```

If ANY write path bypasses token validation, the entire scheme is broken. The resource must be the **sole linearization point**.

### 5.3 Durable Token Storage

The `max_token` must survive crashes. If the resource restarts and forgets the highest token it has seen, a zombie with an old token could succeed.

```
Before crash: max_token = 34
After crash (if lost): max_token = 0
Zombie with token 33: 33 >= 0 → ACCEPTED ← BUG!
```

### 5.4 Why "Just Use Redis SETNX" Is Dangerous

Redis `SETNX` (or `SET NX EX`) gives you a lock, but:

1. **No fencing token issued** — Redis doesn't return a monotonic counter on lock acquisition (unless you build it yourself)
2. **No resource-side validation** — Your storage backend doesn't know about the Redis lock
3. **Relies on timing** — TTL-based expiry is the only defense against zombies
4. **Redlock amplifies the problem** — Multiple Redis instances don't solve the fundamental issue

```
┌────────┐  SETNX    ┌───────┐
│ Client ├──────────►│ Redis │  ← Lock lives here
└───┬────┘           └───────┘
    │
    │ write (no token!)
    ▼
┌───────────┐
│ Database  │  ← No awareness of Redis lock
└───────────┘     No token validation
                  Cannot reject zombies!
```

The lock and the resource are decoupled. There is no mechanism for the resource to distinguish a valid lock holder from a zombie.

---

## 6. Relationship with Epochs/Terms

Fencing tokens are a general pattern. Many systems implement the same concept under different names:

### 6.1 Raft Term Numbers

```
Term 1: Leader A          Term 2: Leader B
├─────────────────────┤   ├──────────────────────────►
     │                         │
     │ AppendEntries           │ AppendEntries
     │ term=1                  │ term=2
     ▼                         ▼
┌──────────┐              ┌──────────┐
│ Follower │              │ Follower │
│          │              │          │
│ Rejects  │              │ Accepts  │
│ term=1   │              │ term=2   │
│ if it has│              │          │
│ seen 2   │              │          │
└──────────┘              └──────────┘
```

- Each new leader election increments the term
- Followers reject messages from old terms
- **The term IS a fencing token** — it prevents stale leaders from corrupting state

### 6.2 ZooKeeper zxid

ZooKeeper's transaction ID (`zxid`) is a 64-bit number:
- High 32 bits: epoch (leader election count)
- Low 32 bits: transaction counter within epoch

Clients can use the `zxid` returned on lock creation as a fencing token. The resource checks that it only accepts writes associated with the most recent zxid.

### 6.3 Kafka Controller Epoch

```
┌──────────────────────────────────────────────────────────┐
│                    Kafka Cluster                          │
│                                                          │
│  Controller (epoch=5)          Stale Controller (ep=4)   │
│       │                              │                   │
│       │ LeaderAndIsr(epoch=5)        │ LeaderAndIsr(ep=4)│
│       ▼                              ▼                   │
│  ┌──────────┐                   ┌──────────┐            │
│  │ Broker 1 │                   │ Broker 2 │            │
│  │          │                   │          │            │
│  │ Accepts  │                   │ Rejects  │            │
│  │ epoch=5  │                   │ epoch=4  │            │
│  │ >= max(5)│                   │ < max(5) │            │
│  └──────────┘                   └──────────┘            │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 6.4 Kafka Producer Epoch (Idempotent/Transactional)

```
Producer A (epoch=0) ──► Broker: Accept (0 >= max)
Producer A crashes, restarts
Producer A' (epoch=1) ──► Broker: Accept (1 >= max), max=1
Producer A (zombie, epoch=0) ──► Broker: REJECT (0 < 1)
                                         "ProducerFencedException"
```

### 6.5 Kubernetes ResourceVersion

Every Kubernetes object has a `resourceVersion` (backed by etcd's mod revision):

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-config
  resourceVersion: "12345"    # <── Fencing token
data:
  key: value
```

Updates must include the current `resourceVersion`. If another write happened in between (bumping the version), the update is rejected with `409 Conflict`.

### Summary Table

| System | Token Name | Scope | Enforcement Point |
|--------|-----------|-------|-------------------|
| Raft | Term | Cluster-wide | Followers |
| ZooKeeper | zxid / czxid | Session/node | Application |
| Kafka Controller | Controller epoch | Cluster-wide | Brokers |
| Kafka Producer | Producer epoch | Per-producer | Brokers |
| Kubernetes | resourceVersion | Per-object | API Server (etcd) |
| etcd | Revision | Per-key/global | etcd server |
| Google Chubby | Lock sequencer | Per-lock | Application |
| DynamoDB | Version attribute | Per-item | DynamoDB (conditional) |

---

## 7. Implementation Patterns

### 7.1 Database: Token in WHERE Clause

The simplest and most robust pattern for relational databases:

```sql
-- On every write, include the fencing token in the WHERE clause
UPDATE accounts
SET balance = balance - 100,
    last_fencing_token = 34
WHERE account_id = 'X'
  AND last_fencing_token < 34;    -- Reject if stale

-- Check affected rows
-- If 0 rows affected → token was stale → we are a zombie
```

Alternative with explicit rejection:

```sql
-- Stored procedure approach
BEGIN TRANSACTION;

SELECT last_fencing_token FROM accounts WHERE account_id = 'X' FOR UPDATE;

IF @current_token >= @incoming_token THEN
    ROLLBACK;
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Fencing token rejected';
END IF;

UPDATE accounts
SET balance = @new_balance,
    last_fencing_token = @incoming_token
WHERE account_id = 'X';

COMMIT;
```

### 7.2 File Storage: Token in Metadata

```python
class FencedFileStorage:
    def write_file(self, path, data, fencing_token):
        metadata_path = path + ".fence"

        # Read current fence (atomic read)
        current_token = read_atomic(metadata_path) or 0

        if fencing_token < current_token:
            raise FencingTokenRejected(fencing_token, current_token)

        # Write data and update fence atomically
        # (Use rename for atomicity on POSIX)
        tmp = path + ".tmp"
        write(tmp, data)
        write(metadata_path + ".tmp", str(fencing_token))
        rename(metadata_path + ".tmp", metadata_path)  # Atomic
        rename(tmp, path)                               # Atomic
```

### 7.3 Conditional Writes (etcd)

```go
// etcd: use revision as fencing token
// Only succeed if the key hasn't been modified since we read it
resp, err := client.Txn(ctx).
    If(clientv3.Compare(clientv3.ModRevision("my-key"), "=", lastSeenRevision)).
    Then(clientv3.OpPut("my-key", newValue)).
    Else(clientv3.OpGet("my-key")).
    Commit()

if !resp.Succeeded {
    // Someone else wrote since we last read → we may be stale
}
```

### 7.4 DynamoDB Conditional Writes

```python
# DynamoDB: conditional expression as fencing
table.update_item(
    Key={'id': 'resource-1'},
    UpdateExpression='SET #data = :data, #token = :token',
    ConditionExpression='#token < :token OR attribute_not_exists(#token)',
    ExpressionAttributeNames={
        '#data': 'data',
        '#token': 'fencing_token'
    },
    ExpressionAttributeValues={
        ':data': new_data,
        ':token': 34
    }
)
# Throws ConditionalCheckFailedException if token is stale
```

### 7.5 Message Queue: Token as Attribute

```python
# Producer (lock holder) attaches token
producer.send(
    topic='commands',
    value=command_payload,
    headers=[('fencing-token', str(grant.token).encode())]
)

# Consumer validates before processing
def process_message(msg):
    token = int(msg.headers['fencing-token'])
    current_max = get_max_token_for_resource(msg.key)

    if token < current_max:
        log.warn(f"Rejecting stale message: token={token}, max={current_max}")
        return  # Skip

    update_max_token(msg.key, token)
    apply_command(msg.value)
```

---

## 8. Real-World Implementations

### 8.1 ZooKeeper

ZooKeeper provides fencing through **sequential ephemeral nodes**:

```
/locks/my-resource/lock-0000000033  ← Node A created this
/locks/my-resource/lock-0000000034  ← Node B created this
```

The sequence number (33, 34) IS the fencing token. The recipe:

1. Client creates sequential ephemeral node under `/locks/resource`
2. Client checks if its node has the lowest sequence number
3. If yes → lock acquired, sequence number = fencing token
4. Client includes this number in all operations on the protected resource
5. If client dies → ephemeral node deleted → next client acquires lock with higher number

**Session ID + zxid** provide additional fencing:
- `czxid` (creation zxid) of the lock node is globally ordered
- Even across session expiry and re-creation, new zxid > old zxid

### 8.2 etcd

etcd provides fencing through its **revision** system:

```go
// Acquire lock using etcd's concurrency package
session, _ := concurrency.NewSession(client, concurrency.WithTTL(10))
mutex := concurrency.NewMutex(session, "/my-lock/")
mutex.Lock(ctx)

// The lock's revision is the fencing token
fencingToken := mutex.Header().Revision

// Use revision in subsequent operations
client.Txn(ctx).
    If(clientv3.Compare(clientv3.CreateRevision("/my-lock/"+mutex.Key()), "=", fencingToken)).
    Then(clientv3.OpPut("/protected-resource", value)).
    Commit()
```

Key properties:
- etcd revision is cluster-wide, monotonically increasing
- Every write (including lock acquisition) gets a unique revision
- Transactions can condition on revisions → built-in fencing

### 8.3 Google Chubby (Lock Sequencer)

From the Chubby paper (Burrows, 2006):

> "Chubby provides a means by which holders of locks can prevent stale locks from having effects... The holder of a lock can request a **sequencer**, which is an opaque byte-string that describes the state of the lock immediately after acquisition."

The sequencer contains:
- Lock name
- Lock mode (exclusive/shared)
- Lock generation number (monotonically increasing)

Clients pass the sequencer to servers. Servers validate it against Chubby (or cache it) before performing operations.

```
Client ──acquire──► Chubby ──returns──► Sequencer{name, mode, gen=47}
   │
   │  operation + sequencer
   ▼
Server ──validate──► Chubby: "Is gen=47 still valid?"
   │                     or
   │                 Server checks: gen=47 >= last_seen_gen?
   ▼
Accept/Reject
```

### 8.4 Apache Kafka

Kafka uses fencing tokens at multiple levels:

**Controller Epoch:**
```
Controller elected → epoch incremented
All controller requests carry epoch
Brokers reject requests from old epochs

Broker state:
  current_controller_epoch = 5
  Incoming request: epoch=4 → REJECT (stale controller)
  Incoming request: epoch=5 → ACCEPT
```

**Producer Epoch (Transactional/Idempotent):**
```
InitProducerId → assigned (PID=1, epoch=0)
Producer crashes, re-inits → (PID=1, epoch=1)
Old producer instance (epoch=0) sends Produce request
Broker: epoch 0 < current epoch 1 → ProducerFencedException
```

**Leader Epoch (Log Divergence Prevention):**
```
Partition leader changes → leader epoch bumps
Followers include leader epoch in fetch requests
Prevents log truncation from stale leaders
```

### 8.5 Kubernetes ResourceVersion

```
GET /api/v1/namespaces/default/configmaps/my-config
→ Returns: resourceVersion: "12345"

PUT /api/v1/namespaces/default/configmaps/my-config
  metadata:
    resourceVersion: "12345"    # Must match current

If another write changed it to "12346":
→ 409 Conflict: "the object has been modified; please apply your changes
                  to the latest version"
```

This is optimistic concurrency control using the resourceVersion as a fencing token. Under the hood, it maps to etcd's mod revision for the key.

### 8.6 Redis Redlock (and Its Problems)

Redlock acquires locks across N Redis instances (majority quorum). However:

```
┌─────────────────────────────────────────────────────────────┐
│                    REDLOCK PROBLEM                           │
│                                                             │
│  1. Client A acquires Redlock (majority of 5 Redis nodes)   │
│  2. Client A enters GC pause                                │
│  3. Lock TTL expires on all Redis nodes                     │
│  4. Client B acquires Redlock                               │
│  5. Client A wakes up, writes to resource                   │
│                                                             │
│  Redlock does NOT issue a fencing token that the resource   │
│  can validate. The resource has no way to reject A's write. │
│                                                             │
│  ┌────────┐          ┌──────────────┐         ┌────────┐   │
│  │Client A│──write──►│   Resource   │◄──write──│Client B│   │
│  │(zombie)│          │(no fence     │          │(valid) │   │
│  └────────┘          │ validation!) │          └────────┘   │
│                      └──────────────┘                       │
│                                                             │
│  ═══ NO SAFETY GUARANTEE ═══                                │
└─────────────────────────────────────────────────────────────┘
```

### 8.7 Amazon DynamoDB

DynamoDB's conditional writes serve as a fencing mechanism:

```python
# Pattern: version counter as fencing token
table.put_item(
    Item={
        'pk': 'resource-1',
        'data': new_data,
        'version': new_version      # Acts as fencing token
    },
    ConditionExpression='attribute_not_exists(version) OR version < :v',
    ExpressionAttributeValues={':v': new_version}
)
```

DynamoDB guarantees that conditional writes are linearizable per-item, making it a valid fencing enforcement point.

---

## 9. The Redlock Controversy

### Background

In 2016, a public debate between Salvatore Sanfilippo (antirez, Redis creator) and Martin Kleppmann (author of "Designing Data-Intensive Applications") exposed fundamental issues with distributed locking.

### Antirez's Redlock Algorithm

```
To acquire lock on resource R:
1. Get current time T1
2. Try to acquire lock on N Redis instances (sequentially/parallel)
   - Use same key name and random value on all instances
   - Short timeout per instance (5-50ms)
3. Lock acquired if:
   - Majority (N/2 + 1) instances grant it
   - Total elapsed time < lock TTL
4. Effective TTL = initial TTL - elapsed time
5. If lock not acquired, release on all instances
```

### Kleppmann's Critique ("How to do distributed locking")

Key arguments:

**1. If you need correctness, Redlock is insufficient:**

The algorithm depends on timing assumptions:
- Bounded network delay
- Bounded process pauses
- Bounded clock drift

In an asynchronous system, none of these are guaranteed.

**2. The GC pause attack (no fencing):**

```
Timeline:
─────────────────────────────────────────────────────────────►

Client A: [acquire Redlock] [GC pause.................] [write]
                                    ▲                       ▲
                                    │                       │
                             Lock expired              Still thinks
                             during pause              it has lock!

Client B:              [acquire Redlock] [write]
                                              ▲
                                              │
                                         Valid holder

Resource:                            [B writes] [A writes]
                                         ✓          ✗ CORRUPT!
```

**3. The solution: fencing tokens**

Kleppmann's argument: If you add fencing tokens, you don't need Redlock's complexity. A single Redis instance (or ZooKeeper, or etcd) suffices because:
- The fencing token provides safety
- The lock service only needs to be available (not Byzantine-fault-tolerant)
- Correctness comes from the token, not the lock's timing properties

**4. If you only need efficiency, a single Redis instance suffices:**

For efficiency-only locks (preventing duplicate work, not corruption), a single Redis `SET NX EX` is simpler and equally effective.

### The Fundamental Issue

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   TIMING-BASED SAFETY          vs.    TOKEN-BASED SAFETY        │
│                                                                 │
│   Assumes:                            Requires:                 │
│   - Bounded delays                    - Monotonic counter       │
│   - Bounded pauses                    - Resource validation     │
│   - Synchronized clocks                                         │
│                                       Guarantees:               │
│   Fails when:                         - Safety regardless of    │
│   - GC pause > TTL                      timing                  │
│   - Network partition > TTL           - No timing assumptions   │
│   - Clock jumps                                                 │
│                                                                 │
│   Redlock = timing-based              Fencing = token-based     │
│   ═══ UNSAFE for correctness ═══      ═══ SAFE ═══             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Verdict

| Use Case | Recommendation |
|----------|---------------|
| Efficiency (avoid duplicate work) | Single Redis instance, no fencing needed |
| Correctness (prevent corruption) | ZooKeeper/etcd + fencing tokens |
| Correctness with Redis | Redis + custom fencing token counter + resource validation |

---

## 10. STONITH (Shoot The Other Node In The Head)

### What Is STONITH?

STONITH is a **hardware-level fencing** mechanism used in cluster systems (primarily Linux HA clusters like Pacemaker/Corosync). When a node is suspected of being a zombie, the cluster forcibly powers it off or resets it via an out-of-band mechanism.

```
┌──────────────────────────────────────────────────────────────┐
│                     Cluster Manager                           │
│                    (Pacemaker/Corosync)                       │
│                                                              │
│   "Node A hasn't responded to heartbeat for 10s"            │
│   "Node A might be a zombie writing to shared storage"       │
│   "SHOOT IT IN THE HEAD"                                     │
│                                                              │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            │ IPMI / iLO / DRAC / PDU command
                            │ "POWER OFF NODE A"
                            ▼
                    ┌───────────────┐
                    │  Node A       │
                    │  (zombie?)    │
                    │               │
                    │  ╔═══════╗    │
                    │  ║ RESET ║    │  ← Hardware forced off
                    │  ╚═══════╝    │
                    └───────────────┘
```

### STONITH Mechanisms

| Mechanism | How It Works |
|-----------|-------------|
| IPMI/BMC | Baseboard management controller powers off server |
| PDU (Power Distribution Unit) | Cuts power to the server's outlet |
| SAN fencing | Revokes storage access at the fabric level |
| Hypervisor API | VM destroy/stop via vSphere/KVM/Hyper-V |
| Watchdog timer | Hardware timer resets the node if not pet |

### Software Fencing vs. Hardware Fencing

```
┌─────────────────────────┬───────────────────────────────────┐
│   Software Fencing      │   Hardware Fencing (STONITH)       │
│   (Fencing Tokens)      │                                   │
├─────────────────────────┼───────────────────────────────────┤
│ Resource rejects stale  │ Zombie node physically killed     │
│ operations              │                                   │
│                         │                                   │
│ Requires resource       │ Requires out-of-band hardware     │
│ cooperation             │ management                        │
│                         │                                   │
│ Works for application-  │ Works for shared storage (SAN,    │
│ level resources         │ NFS) that can't validate tokens   │
│                         │                                   │
│ No hardware dependency  │ Hardware/infrastructure required   │
│                         │                                   │
│ Preferred in cloud/     │ Required for shared-disk clusters │
│ distributed systems     │ (Oracle RAC, traditional HA)      │
└─────────────────────────┴───────────────────────────────────┘
```

### When Hardware Fencing Is Needed

1. **Shared-disk clusters**: When multiple nodes access the same physical disk/LUN, and the storage has no token validation capability
2. **Legacy systems**: Applications that cannot be modified to accept fencing tokens
3. **Kernel-level corruption risk**: When a zombie could corrupt filesystem metadata (not just application data)
4. **Regulatory requirements**: Some standards (e.g., financial) mandate hardware fencing for HA databases

### When Software Fencing Suffices

1. **Cloud-native applications**: Resources are accessed via APIs that support conditional writes
2. **Modern distributed databases**: etcd, CockroachDB, Spanner — all have built-in fencing
3. **Shared-nothing architectures**: No shared storage to corrupt
4. **Microservices**: Each service owns its data; access goes through APIs

---

## 11. Architect's Guide

### Decision Framework: Do You Need Fencing Tokens?

```
                    ┌──────────────────────────────┐
                    │ Are you using distributed     │
                    │ locks for correctness?        │
                    └──────────────┬───────────────┘
                                   │
                    ┌──── YES ─────┼───── NO ────┐
                    │              │              │
                    ▼              │              ▼
        ┌────────────────┐        │    ┌──────────────────┐
        │ YOU NEED        │        │    │ Efficiency only?  │
        │ FENCING TOKENS │        │    │ Single Redis is   │
        └───────┬────────┘        │    │ fine. Accept rare │
                │                 │    │ duplicate work.   │
                ▼                 │    └──────────────────┘
   ┌─────────────────────────┐   │
   │ Can your resource        │   │
   │ validate tokens?         │   │
   └────────────┬─────────────┘   │
                │                  │
     ┌── YES ──┼──── NO ─────┐   │
     │         │              │   │
     ▼         │              ▼   │
 ┌────────┐    │     ┌─────────────────────┐
 │ Great! │    │     │ Options:            │
 │ Use    │    │     │ 1. Add validation   │
 │ them.  │    │     │ 2. Use STONITH      │
 └────────┘    │     │ 3. Use a resource   │
               │     │    that supports it  │
               │     └─────────────────────┘
               │
               ▼
```

### Choosing a Lock Service

| Requirement | Recommended Service |
|------------|-------------------|
| Strong consistency + fencing | ZooKeeper, etcd |
| High availability, tolerates some risk | Redis (single) + manual fencing |
| Cloud-native (AWS) | DynamoDB conditional writes (no separate lock service) |
| Cloud-native (GCP) | Cloud Spanner with transactions |
| Kubernetes-native | Lease objects + resourceVersion |
| Already using Kafka | Use Kafka transactions (producer fencing built-in) |

### Fencing Patterns by Storage Backend

#### Relational Database (PostgreSQL, MySQL)

```sql
-- Add fencing_token column to protected tables
ALTER TABLE protected_resource ADD COLUMN fencing_token BIGINT DEFAULT 0;

-- Every write includes token check
UPDATE protected_resource
SET data = $new_data, fencing_token = $my_token
WHERE id = $resource_id AND fencing_token < $my_token;

-- Verify: if affected_rows == 0, we are stale
```

#### Object Storage (S3)

S3 doesn't support fencing natively. Workarounds:

1. **Use DynamoDB as coordination layer**: Write to DynamoDB (with condition) first, then S3
2. **S3 Object Lock + versioning**: Use version IDs as quasi-tokens
3. **Conditional writes (S3 2024)**: `If-None-Match` / `If-Match` headers

#### gRPC Services

```protobuf
message WriteRequest {
  string resource_id = 1;
  bytes data = 2;
  int64 fencing_token = 3;  // Required field
}

message WriteResponse {
  bool accepted = 1;
  string rejection_reason = 2;
}
```

### Complete Architecture Example

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PRODUCTION SETUP                             │
│                                                                     │
│  ┌────────────┐    acquire(ttl=30s)    ┌──────────────────────┐    │
│  │            │ ──────────────────────► │                      │    │
│  │  Worker    │ ◄────────────────────── │   etcd (3 nodes)     │    │
│  │  Node A    │    grant{token=147}     │   Lock Service       │    │
│  │            │                         │                      │    │
│  └─────┬──────┘                         └──────────────────────┘    │
│        │                                                            │
│        │  write(data, token=147)                                    │
│        │                                                            │
│        ▼                                                            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Protected Resource                         │   │
│  │                    (PostgreSQL)                                │   │
│  │                                                              │   │
│  │  ┌─────────────────────────────────────────────────────┐     │   │
│  │  │ BEFORE INSERT OR UPDATE trigger:                     │     │   │
│  │  │   IF NEW.fencing_token < current_max_token THEN     │     │   │
│  │  │     RAISE EXCEPTION 'Stale fencing token';          │     │   │
│  │  │   END IF;                                           │     │   │
│  │  │   UPDATE max_tokens SET token = NEW.fencing_token   │     │   │
│  │  │     WHERE resource = NEW.resource_id;               │     │   │
│  │  └─────────────────────────────────────────────────────┘     │   │
│  │                                                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Anti-Patterns

| Anti-Pattern | Why It's Wrong |
|-------------|----------------|
| Lock without fencing | Timing-based safety; broken by GC/network |
| Fencing token checked client-side | Client can be a zombie; must be resource-side |
| Token stored in-memory only | Lost on resource restart; zombie succeeds |
| Multiple write paths, some unfenced | Single unfenced path breaks entire scheme |
| Using wall-clock time as token | Clocks can go backwards; not monotonic |
| Fencing token per-client (not per-lock) | Different clients could have overlapping tokens |

### Kafka Controller Epoch: Complete Timeline

```
Time ──────────────────────────────────────────────────────────────────────►

ZooKeeper  [C1 elected]         [C1 session expires]  [C2 elected]
           epoch=1                                     epoch=2

Controller ┌── C1 active ──────────────────┐
1 (epoch=1)│                               │ ████████████████████████████
           │  Sends:                       │ █ Network partition /      █
           │  LeaderAndIsr(epoch=1) ✓      │ █ GC pause                █
           └───────────────────────────────┘ █                          █
                                             █ C1 doesn't know it's     █
                                             █ no longer controller     █
                                             ████████████████████████████
                                                            │
                                                            │ Sends:
                                                            │ LeaderAndIsr(epoch=1)
                                                            ▼
Controller                                   ┌── C2 active ─────────────────
2 (epoch=2)                                  │
                                             │  Sends:
                                             │  LeaderAndIsr(epoch=2) ✓
                                             └──────────────────────────────

Broker     max_epoch = 0
State:     ──────────────────────────────────────────────────────────────────
           Receives epoch=1: Accept (1 > 0), max=1
                                             Receives epoch=2: Accept (2>1), max=2
                                                            │
                                             Receives epoch=1 from zombie C1:
                                                            │
                                                      REJECT (1 < 2)
                                                      "Stale controller"
                                                      ✓ SAFETY PRESERVED
```

### Summary: The Safety Argument

Fencing tokens transform a **timing-dependent** lock into a **timing-independent** safety mechanism:

1. **Without fencing**: Safety depends on TTL > max(GC pause + network delay + clock drift). This cannot be guaranteed in asynchronous systems.

2. **With fencing**: Safety depends on (a) monotonic token issuance, (b) resource-side validation. Both are local properties that hold regardless of timing.

The key insight from Lamport, Kleppmann, and decades of distributed systems research:

> **You cannot achieve safety through timing alone in an asynchronous system. You need logical mechanisms (sequence numbers, epochs, fencing tokens) that are independent of physical time.**

---

## References

- Kleppmann, M. (2016). "How to do distributed locking." https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html
- Sanfilippo, S. (2016). "Is Redlock safe?" http://antirez.com/news/101
- Burrows, M. (2006). "The Chubby lock service for loosely-coupled distributed systems." OSDI'06.
- Ongaro, D. & Ousterhout, J. (2014). "In Search of an Understandable Consensus Algorithm." (Raft paper)
- Kleppmann, M. (2017). *Designing Data-Intensive Applications.* O'Reilly. Chapter 8.
- Hunt, P. et al. (2010). "ZooKeeper: Wait-free Coordination for Internet-scale Systems."
