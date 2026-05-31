# FoundationDB - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Ordered Key-Value Store](#ordered-key-value-store)
3. [Transaction Model](#transaction-model)
4. [Layers Architecture](#layers-architecture)
5. [Fault Tolerance & Recovery](#fault-tolerance--recovery)
6. [Staff Architect Interview Questions](#staff-architect-interview-questions)
7. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### Design Philosophy
```
FoundationDB's unique position:
- Ordered key-value store with ACID transactions
- Serializable isolation (strongest guarantee)
- Designed as a "database foundation" (build other databases on top)
- Used by: Apple (iCloud), Snowflake, Ditto

Key principle: Minimal core with strong guarantees
- No query language (raw key-value API)
- No built-in secondary indexes (build with layers)
- No schema (bytes in, bytes out)
- But: Serializable transactions, multi-key, distributed

Users build "layers" on top:
- Document layer (MongoDB-like)
- Record layer (relational, used by Apple)
- Graph layer
- Message queue layer
```

### Architecture
```
┌─────────────────────────────────────────────────────────┐
│                   FoundationDB Cluster                    │
│                                                           │
│  Coordinators (Paxos group):                             │
│  ┌─────┐ ┌─────┐ ┌─────┐                               │
│  │Coord│ │Coord│ │Coord│  Configuration, leader election│
│  └─────┘ └─────┘ └─────┘                               │
│                                                           │
│  Cluster Controller:                                     │
│  ┌──────────────┐                                        │
│  │ Orchestrates │  Role assignment, failure detection    │
│  └──────────────┘                                        │
│                                                           │
│  Transaction System:                                     │
│  ┌──────────┐  ┌───────────────┐  ┌────────────────┐   │
│  │Sequencer │  │ Proxies (N)   │  │ Resolvers (N)  │   │
│  │(1 active)│  │ Accept txns   │  │ Conflict check │   │
│  └──────────┘  └───────────────┘  └────────────────┘   │
│                                                           │
│  Log System:                                             │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐           │
│  │Log Server │  │Log Server │  │Log Server │  WAL      │
│  └───────────┘  └───────────┘  └───────────┘           │
│                                                           │
│  Storage System:                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Storage  │  │ Storage  │  │ Storage  │  B-tree SSDs │
│  │ Server   │  │ Server   │  │ Server   │               │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
```

### Role-Based Architecture
```
1. Coordinators: Paxos-based configuration store
   - Stores cluster-wide configuration
   - Facilitates leader election
   
2. Cluster Controller: Single leader
   - Monitors health of all processes
   - Assigns roles (proxy, resolver, log, storage)
   - Handles failures by reassigning roles
   
3. Sequencer: Single process
   - Assigns read versions (timestamps)
   - Assigns commit versions
   - Bottleneck? Handles millions of versions/second
   
4. Proxies: Multiple
   - Accept client transaction commits
   - Send to resolvers for conflict check
   - Write to log servers on success
   
5. Resolvers: Multiple
   - Conflict detection (range-based)
   - Check if transaction's read ranges were modified since read version
   - Serializable isolation enforcement
   
6. Log Servers: Multiple
   - Durable WAL (replicated)
   - Team-based replication (writes to k-of-n)
   
7. Storage Servers: Multiple
   - B-tree (SQLite-derived engine)
   - Serve reads at specific versions
   - Pull committed mutations from log servers
   - Memory-mapped for fast reads
```

---

## Transaction Model

### Optimistic Concurrency Control
```
Transaction flow:
1. Client calls fdb.createTransaction()
2. Get read version from Sequencer (snapshot timestamp)
3. Perform reads (from storage servers at read_version)
4. Buffer writes locally (no network until commit)
5. Commit:
   a. Send to Proxy: {read_version, read_ranges, write_ranges, mutations}
   b. Proxy → Resolver: Check conflicts
      - Did any other committed txn write to our read ranges?
      - If yes: CONFLICT → transaction retried automatically
   c. Proxy → Log Servers: Persist mutations (synchronous, replicated)
   d. Return commit_version to client

Key properties:
- 5-second transaction time limit (by design!)
- Max transaction size: 10MB mutations
- Max key size: 10KB
- Max value size: 100KB
- Serializable isolation (true, not snapshot!)
- Automatic retry (transparent to application)

Conflict detection:
- Range-based (not row-based)
- If txn A reads range [a,z] and txn B writes to key "m" → conflict
- Enables efficient conflict checking (no per-key tracking)
```

### 5-Second Transaction Limit
```
WHY the 5-second limit:
- Ensures system-wide progress (no long-running txns blocking)
- Resolvers only keep 5 seconds of conflict history
- Forces application to batch work appropriately
- Prevents resource hoarding

Working with the limit:
- Small transactions: Usually well within 5 seconds
- Large batch operations: Break into sub-transactions
  - Process 1000 items per transaction
  - Use a cursor/bookmark to resume
  - Each sub-txn commits independently
- Background jobs: Iterate with multiple short transactions

Example: Process 1M records
for chunk in range(0, 1M, 1000):
    @fdb.transactional
    def process_chunk(tr):
        items = tr.get_range(start_key, end_key, limit=1000)
        for item in items:
            tr.set(transform(item.key), transform(item.value))
        return items[-1].key  # bookmark for next chunk
    start_key = process_chunk(db)
```

---

## Layers Architecture

### Layer Concept
```
FoundationDB provides: Ordered KV + Transactions
Layers provide: Higher-level abstractions

Built-in layers:
- Tuple Layer: Structured key encoding/decoding
- Directory Layer: Hierarchical namespacing
- Subspace Layer: Key prefix management

Community/custom layers:
- Record Layer (Apple): Structured records, indexes, query planning
- Document Layer: MongoDB-compatible API
- SQL Layer: Relational model

Key insight: ALL layers share the same transactional guarantees
- A document update + index update = ATOMIC
- Cross-layer operations are transactional
- No eventual consistency between layers
```

### Tuple Layer (Key Design)
```python
# Tuple layer encodes structured data into ordered bytes
import fdb.tuple

# Key: ("users", "alice", "orders", "2024-01-15", 1)
key = fdb.tuple.pack(("users", "alice", "orders", "2024-01-15", 1))
# Encoded as bytes that sort correctly (lexicographic order)

# Range scan: All Alice's orders in January 2024
start = fdb.tuple.pack(("users", "alice", "orders", "2024-01-01"))
end = fdb.tuple.pack(("users", "alice", "orders", "2024-02-01"))
results = tr.get_range(start, end)

# Benefits:
# - Mixed types sort correctly (strings, ints, tuples)
# - Prefix queries natural (hierarchical)
# - No custom encoding needed
```

### Record Layer (Apple's Implementation)
```
Apple's Record Layer builds on FoundationDB:
- Schema management (protobuf-defined records)
- Indexes (value, rank, text, aggregate)
- Query planning and execution
- Used for: iCloud, Apple's backend services

Features:
- Online index builds (background, transactional)
- Aggregate indexes (pre-computed sums, counts)
- Rank indexes (efficient rank queries)
- Version tracking (schema evolution)
- Multi-tenant support via record store isolation

Scale: Reported to handle billions of records
- Multiple FoundationDB clusters per data center
- Record Layer instances route to appropriate cluster
```

---

## Fault Tolerance & Recovery

### Recovery Process
```
FoundationDB's signature feature: Fast recovery

Recovery time: ~5 seconds (entire cluster recovery!)

How:
1. Failure detected by Cluster Controller
2. Controller recruits new process for failed role
3. Log servers have all committed (unreplayed) data
4. New storage servers replay from log servers
5. Transaction system restarts with new epoch

Key design choices enabling fast recovery:
- Log servers separate from storage (writes survive storage failure)
- Stateless proxies/resolvers (restart = instant)
- Single sequencer (simple state, fast failover)
- No complex distributed state to rebuild

Simulation testing:
- FoundationDB tested with deterministic simulation
- Tests inject random failures (network, disk, process)
- Validates correctness under all failure combinations
- Millions of test hours in simulation
- Most thoroughly tested distributed database
```

---

## Staff Architect Interview Questions

**Q1: Why did Apple choose FoundationDB for iCloud?**
**A:** Apple needed:
- Strong consistency (user data cannot be inconsistent)
- Horizontal scalability (billions of users)
- Flexibility (many data models on one platform)
- Operational simplicity (single system to manage)
- Fast recovery (five-second recovery for HA)
FoundationDB provides the foundation; Record Layer provides the data model. This separation means Apple can evolve their data model without changing the storage layer.

**Q2: What are the trade-offs of the 5-second transaction limit?**
**A:**
Pros: 
- Prevents resource exhaustion
- Enables efficient conflict detection (bounded history)
- Forces good application design (small, fast transactions)
- Enables fast recovery (no long-running state to recover)

Cons:
- Cannot do large batch operations in single transaction
- Requires application-level chunking for bulk operations
- Analytics queries must be broken into sub-queries
- Not suitable for long-running business transactions

**Q3: Compare FoundationDB's approach to CockroachDB's.**
**A:**
| Aspect | FoundationDB | CockroachDB |
|--------|-------------|-------------|
| API | Key-value (raw bytes) | SQL (PostgreSQL compatible) |
| Layers | Build your own data model | Built-in relational |
| Recovery | ~5 seconds | Minutes (Raft re-election) |
| Txn duration | 5-second limit | No limit |
| Txn size | 10MB limit | No hard limit |
| Testing | Deterministic simulation | Standard testing |
| Isolation | Serializable (conflict-based) | Serializable (SSI) |
| Use case | Foundation for custom databases | Drop-in SQL database |

---

## Scenario-Based Questions

### Scenario 1: Building a Message Queue on FoundationDB

```python
# Message Queue layer using tuple + directory
import fdb
fdb.api_version(710)
db = fdb.open()

QUEUE_DIR = fdb.directory.create_or_open(db, ('queues',))

@fdb.transactional
def enqueue(tr, queue_name, message):
    queue = QUEUE_DIR.create_or_open(tr, (queue_name,))
    # Use versionstamp as position (monotonically increasing)
    key = queue.pack((fdb.tuple.Versionstamp(),))
    tr.set_versionstamped_key(key, message.encode())

@fdb.transactional
def dequeue(tr, queue_name):
    queue = QUEUE_DIR.create_or_open(tr, (queue_name,))
    # Get first item
    items = tr.get_range(queue.range().start, queue.range().stop, limit=1)
    for key, value in items:
        tr.clear(key)  # Atomic: read + delete in same transaction
        return value.decode()
    return None

# Properties:
# - Exactly-once delivery (transactional dequeue)
# - Ordered (versionstamp is monotonically increasing)
# - Multi-consumer safe (serializable isolation prevents double-processing)
# - Persistent (survives failures)
# - Horizontally scalable (multiple queue partitions)
```

