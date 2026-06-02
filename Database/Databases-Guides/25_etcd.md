# etcd - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Raft Consensus Protocol](#raft-consensus-protocol)
3. [Storage Engine (bbolt/BoltDB)](#storage-engine)
4. [Watch API & Event System](#watch-api--event-system)
5. [Lease & TTL System](#lease--ttl-system)
6. [Authentication & RBAC](#authentication--rbac)
7. [Cluster Operations](#cluster-operations)
8. [Performance & Tuning](#performance--tuning)
9. [High Availability & Disaster Recovery](#high-availability--disaster-recovery)
10. [Kubernetes Integration](#kubernetes-integration)
11. [Production Deployment Patterns](#production-deployment-patterns)
12. [Client Libraries & gRPC API](#client-libraries--grpc-api)
13. [Use Case Architectures](#use-case-architectures)
14. [Staff Architect Interview Questions](#staff-architect-interview-questions)
15. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### What is etcd?
```
etcd is a strongly consistent, distributed key-value store that provides
a reliable way to store data across a cluster of machines. It is the
backbone of Kubernetes, providing the single source of truth for all
cluster state.

Key characteristics:
- Strong consistency (linearizable reads/writes via Raft)
- Watch support (streaming changes in real-time)
- MVCC (multi-version concurrency control)
- Lease-based TTL (automatic key expiration)
- Transactions (atomic compare-and-swap)
- Small dataset focus (recommended < 8GB)
- Written in Go, uses gRPC API
- Typically 3 or 5 node clusters

NOT designed for:
- Large datasets (> 8GB database size)
- High write throughput (100s of K writes/sec)
- General-purpose key-value store at scale
- Binary large objects (BLOBs)
- Full-text search
- Time-series data

Comparison:
┌─────────────────────┬──────────────┬──────────────┬──────────────┬──────────┐
│                     │ etcd         │ ZooKeeper    │ Consul       │ Redis    │
├─────────────────────┼──────────────┼──────────────┼──────────────┼──────────┤
│ Consensus           │ Raft         │ ZAB          │ Raft         │ None/Raft│
│ API                 │ gRPC         │ Custom TCP   │ HTTP/gRPC    │ RESP     │
│ Watch               │ gRPC stream  │ One-time     │ Blocking HTTP│ Pub/Sub  │
│ Consistency         │ Linearizable │ Linearizable │ Linearizable │ Eventual │
│ Multi-version       │ MVCC         │ No           │ No           │ No       │
│ Transactions        │ Mini-txns    │ Multi-op     │ Txn API      │ MULTI    │
│ TTL/Lease           │ Lease-based  │ Ephemeral    │ Session/TTL  │ EXPIRE   │
│ Service Discovery   │ Watch-based  │ ZNodes       │ Native       │ No       │
│ Max data size       │ ~8 GB        │ ~1 GB        │ ~512 MB      │ Memory   │
│ Primary use case    │ Kubernetes   │ Hadoop/Kafka │ Service mesh │ Cache    │
│ Operational ease    │ Moderate     │ Hard         │ Easy         │ Easy     │
└─────────────────────┴──────────────┴──────────────┴──────────────┴──────────┘
```

### etcd Cluster Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        etcd CLUSTER (3 or 5 nodes)                            │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │   │
│  │  │   etcd Node 1   │  │   etcd Node 2   │  │   etcd Node 3   │     │   │
│  │  │   (LEADER)       │  │   (FOLLOWER)     │  │   (FOLLOWER)     │     │   │
│  │  │                  │  │                  │  │                  │     │   │
│  │  │  ┌────────────┐ │  │  ┌────────────┐ │  │  ┌────────────┐ │     │   │
│  │  │  │ gRPC Server│ │  │  │ gRPC Server│ │  │  │ gRPC Server│ │     │   │
│  │  │  └─────┬──────┘ │  │  └─────┬──────┘ │  │  └─────┬──────┘ │     │   │
│  │  │        │         │  │        │         │  │        │         │     │   │
│  │  │  ┌─────▼──────┐ │  │  ┌─────▼──────┐ │  │  ┌─────▼──────┐ │     │   │
│  │  │  │  Raft      │ │  │  │  Raft      │ │  │  │  Raft      │ │     │   │
│  │  │  │  Module    │◄├──├──►│  Module    │◄├──├──►│  Module    │ │     │   │
│  │  │  │            │ │  │  │            │ │  │  │            │ │     │   │
│  │  │  │ Term: 5    │ │  │  │ Term: 5    │ │  │  │ Term: 5    │ │     │   │
│  │  │  │ Index: 1234│ │  │  │ Index: 1234│ │  │  │ Index: 1234│ │     │   │
│  │  │  └─────┬──────┘ │  │  └─────┬──────┘ │  │  └─────┬──────┘ │     │   │
│  │  │        │ apply   │  │        │ apply   │  │        │ apply   │     │   │
│  │  │  ┌─────▼──────┐ │  │  ┌─────▼──────┐ │  │  ┌─────▼──────┐ │     │   │
│  │  │  │  Apply     │ │  │  │  Apply     │ │  │  │  Apply     │ │     │   │
│  │  │  │  (state    │ │  │  │  (state    │ │  │  │  (state    │ │     │   │
│  │  │  │  machine)  │ │  │  │  machine)  │ │  │  │  machine)  │ │     │   │
│  │  │  └─────┬──────┘ │  │  └─────┬──────┘ │  │  └─────┬──────┘ │     │   │
│  │  │        │         │  │        │         │  │        │         │     │   │
│  │  │  ┌─────▼──────┐ │  │  ┌─────▼──────┐ │  │  ┌─────▼──────┐ │     │   │
│  │  │  │   MVCC /   │ │  │  │   MVCC /   │ │  │  │   MVCC /   │ │     │   │
│  │  │  │   Store    │ │  │  │   Store    │ │  │  │   Store    │ │     │   │
│  │  │  └─────┬──────┘ │  │  └─────┬──────┘ │  │  └─────┬──────┘ │     │   │
│  │  │        │         │  │        │         │  │        │         │     │   │
│  │  │  ┌─────▼──────┐ │  │  ┌─────▼──────┐ │  │  ┌─────▼──────┐ │     │   │
│  │  │  │  bbolt DB  │ │  │  │  bbolt DB  │ │  │  │  bbolt DB  │ │     │   │
│  │  │  │  (B+ tree) │ │  │  │  (B+ tree) │ │  │  │  (B+ tree) │ │     │   │
│  │  │  └────────────┘ │  │  └────────────┘ │  │  └────────────┘ │     │   │
│  │  │                  │  │                  │  │                  │     │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘     │   │
│  │                                                                       │   │
│  │  Raft: Leader handles ALL writes, replicates to followers            │   │
│  │  Reads: Linearizable (via leader) or Serializable (any node)         │   │
│  │  Quorum: (N/2)+1 nodes must agree for commit                         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Clients:                                                                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                        │
│  │ kube-apiserver│ │ Custom App  │ │ Kubernetes   │                        │
│  │ (primary user)│ │ (etcd client)│ │ controllers │                        │
│  └──────────────┘ └──────────────┘ └──────────────┘                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Raft Consensus Protocol

### Leader Election
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RAFT LEADER ELECTION                                       │
│                                                                              │
│  Normal operation (Leader active):                                           │
│  ┌─────────┐    heartbeat    ┌─────────┐    heartbeat    ┌─────────┐       │
│  │ LEADER  │ ──────────────▶ │FOLLOWER │ ◀────────────── │FOLLOWER │       │
│  │ Node 1  │ ◀────────────── │ Node 2  │                 │ Node 3  │       │
│  │ Term: 5 │                 │ Term: 5 │                 │ Term: 5 │       │
│  └─────────┘                 └─────────┘                 └─────────┘       │
│                                                                              │
│  Leader failure → Election:                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Time ─────────────────────────────────────────────────────────▶      │    │
│  │                                                                       │    │
│  │ Node 1 (was Leader): ──CRASH──X                                      │    │
│  │                                                                       │    │
│  │ Node 2 (Follower):                                                   │    │
│  │   [heartbeat timeout expires]                                        │    │
│  │   → Become CANDIDATE                                                 │    │
│  │   → Increment term to 6                                              │    │
│  │   → Vote for self                                                    │    │
│  │   → RequestVote RPC to Node 3                                        │    │
│  │                                                                       │    │
│  │ Node 3 (Follower):                                                   │    │
│  │   [receives RequestVote from Node 2]                                 │    │
│  │   → Log at least as up-to-date? YES                                  │    │
│  │   → Already voted in term 6? NO                                      │    │
│  │   → Grant vote to Node 2                                             │    │
│  │                                                                       │    │
│  │ Node 2: Received majority (2/3 votes) → Becomes LEADER (term 6)     │    │
│  │   → Sends heartbeats to establish authority                          │    │
│  │   → Ready to accept writes                                           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Election timeout: randomized 1000-1500ms (prevents split vote)             │
│  Heartbeat interval: 100ms (configurable)                                    │
│  Key property: At most one leader per term                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Log Replication
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RAFT LOG REPLICATION                                       │
│                                                                              │
│  Write request: PUT /key1 = "value1"                                        │
│                                                                              │
│  Step 1: Client sends to Leader                                              │
│  Step 2: Leader appends to local log (uncommitted)                           │
│  Step 3: Leader sends AppendEntries RPC to all followers                    │
│  Step 4: Followers append to their logs, respond ACK                        │
│  Step 5: Leader receives majority ACKs → entry COMMITTED                    │
│  Step 6: Leader applies to state machine (bbolt)                            │
│  Step 7: Leader responds to client: SUCCESS                                  │
│  Step 8: Next heartbeat informs followers to commit + apply                 │
│                                                                              │
│  Log state during replication:                                               │
│                                                                              │
│  Leader (Node 1):                                                            │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┐                                    │
│  │ T1  │ T1  │ T2  │ T3  │ T5  │ T5  │  (Term, Entry)                     │
│  │ E1  │ E2  │ E3  │ E4  │ E5  │ E6  │  committed up to E5                │
│  └─────┴─────┴─────┴─────┴─────┴─────┘  E6 = pending                      │
│                                                                              │
│  Follower (Node 2):                                                          │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┐                                    │
│  │ T1  │ T1  │ T2  │ T3  │ T5  │ T5  │  replicated, committed up to E5   │
│  │ E1  │ E2  │ E3  │ E4  │ E5  │ E6  │                                    │
│  └─────┴─────┴─────┴─────┴─────┴─────┘                                    │
│                                                                              │
│  Follower (Node 3, lagging):                                                │
│  ┌─────┬─────┬─────┬─────┬─────┐                                           │
│  │ T1  │ T1  │ T2  │ T3  │ T5  │  still replicating E6                    │
│  │ E1  │ E2  │ E3  │ E4  │ E5  │  committed up to E5 (quorum met)         │
│  └─────┴─────┴─────┴─────┴─────┘                                           │
│                                                                              │
│  Commit rule: Entry committed when replicated to majority                   │
│  3-node cluster: committed when on 2 nodes                                   │
│  5-node cluster: committed when on 3 nodes                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Storage Engine

### Internal Architecture Layers
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    etcd STORAGE LAYERS                                        │
│                                                                              │
│  Client Request (gRPC)                                                       │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  gRPC SERVER / API LAYER                                             │    │
│  │  - KV service (Range, Put, DeleteRange, Txn)                        │    │
│  │  - Watch service (Watch)                                             │    │
│  │  - Lease service (LeaseGrant, LeaseRevoke, LeaseKeepAlive)          │    │
│  │  - Auth service (UserAdd, RoleAdd, AuthEnable)                      │    │
│  └────────────────────────────────┬────────────────────────────────────┘    │
│                                    │                                         │
│  ┌────────────────────────────────▼────────────────────────────────────┐    │
│  │  RAFT MODULE                                                         │    │
│  │  - Proposes changes to Raft cluster                                  │    │
│  │  - Write: Propose → Replicate → Commit → Apply                      │    │
│  │  - Read (linearizable): ReadIndex (leader confirms leadership)       │    │
│  │  - WAL: Write-ahead log for Raft entries (separate from bbolt)      │    │
│  │  - Snapshot: Periodic full state snapshot for slow followers         │    │
│  └────────────────────────────────┬────────────────────────────────────┘    │
│                                    │ apply (committed entries)               │
│  ┌────────────────────────────────▼────────────────────────────────────┐    │
│  │  MVCC STORE                                                          │    │
│  │                                                                       │    │
│  │  Revision system:                                                    │    │
│  │  - Every modification creates a new revision (monotonic counter)     │    │
│  │  - Revision = (main revision, sub revision)                          │    │
│  │  - main: cluster-wide counter incremented per txn                    │    │
│  │  - sub: operation within a txn (0, 1, 2...)                         │    │
│  │                                                                       │    │
│  │  Key index (in-memory B-tree):                                       │    │
│  │    key → [revision_1, revision_2, ..., revision_N]                  │    │
│  │    Allows: "get key at revision X" (time-travel queries)            │    │
│  │                                                                       │    │
│  │  Example:                                                             │    │
│  │    PUT /foo = "bar"     → revision (100, 0)                          │    │
│  │    PUT /foo = "baz"     → revision (105, 0)                          │    │
│  │    DELETE /foo          → revision (110, 0) [tombstone]              │    │
│  │                                                                       │    │
│  │  key_index["/foo"] = [(100,0), (105,0), (110,0,tombstone)]          │    │
│  └────────────────────────────────┬────────────────────────────────────┘    │
│                                    │                                         │
│  ┌────────────────────────────────▼────────────────────────────────────┐    │
│  │  bbolt (BACKEND)                                                     │    │
│  │                                                                       │    │
│  │  B+ tree on disk:                                                    │    │
│  │  Key: revision bytes (main.sub)                                      │    │
│  │  Value: KeyValue protobuf (key, value, create_rev, mod_rev, version)│    │
│  │                                                                       │    │
│  │  Buckets:                                                             │    │
│  │  - "key": revision → KeyValue (main data)                           │    │
│  │  - "meta": consistent_index, scheduled_compact_rev                  │    │
│  │  - "auth": users, roles, tokens                                      │    │
│  │  - "lease": lease_id → TTL + attached keys                          │    │
│  │                                                                       │    │
│  │  Properties:                                                          │    │
│  │  - Single-file database (data/member/snap/db)                        │    │
│  │  - Read transactions: MVCC (readers never block writers)             │    │
│  │  - Write transactions: single-writer (serialized)                    │    │
│  │  - mmap for reads (OS page cache)                                   │    │
│  │  - Copy-on-write B+ tree (crash safe)                               │    │
│  │  - Page size: 4KB                                                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Compaction:                                                                 │
│  - Removes old revisions (frees space for bbolt reuse)                     │
│  - auto-compaction-mode: periodic (every N hours) or revision (keep N)     │
│  - Does NOT return space to OS (bbolt limitation)                          │
│  - Defragmentation: Rewrites entire DB to reclaim space                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Watch API & Event System

### Watch Multiplexing
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WATCH ARCHITECTURE                                         │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  CLIENT SIDE                                                          │   │
│  │                                                                       │   │
│  │  Watch Request 1: key="/services/", prefix=true, start_revision=100  │   │
│  │  Watch Request 2: key="/config/app1", start_revision=105             │   │
│  │  Watch Request 3: key="/leases/", prefix=true, start_revision=100   │   │
│  │                                                                       │   │
│  │  All multiplexed over SINGLE gRPC bidirectional stream               │   │
│  └──────────────────────────────────┬───────────────────────────────────┘   │
│                                      │ gRPC stream                           │
│                                      ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  SERVER SIDE (watchable store)                                        │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │  WATCH STREAM (per gRPC connection)                          │    │   │
│  │  │                                                               │    │   │
│  │  │  Watcher 1: key="/services/", prefix=true                    │    │   │
│  │  │  Watcher 2: key="/config/app1"                               │    │   │
│  │  │  Watcher 3: key="/leases/", prefix=true                     │    │   │
│  │  └────────────────────────────┬────────────────────────────────┘    │   │
│  │                                │                                     │   │
│  │  ┌────────────────────────────▼────────────────────────────────┐    │   │
│  │  │  WATCHER GROUP (synced watchers)                             │    │   │
│  │  │                                                               │    │   │
│  │  │  Synced watchers: watch from current revision onwards         │    │   │
│  │  │  - Efficient: events from MVCC store pushed to all watchers  │    │   │
│  │  │  - Batched: Multiple events combined per response            │    │   │
│  │  │                                                               │    │   │
│  │  │  Unsynced watchers: need to catch up from historical revision│    │   │
│  │  │  - Read events from bbolt (revision range scan)              │    │   │
│  │  │  - Once caught up → moved to synced group                    │    │   │
│  │  └────────────────────────────────────────────────────────────────┘    │   │
│  │                                                                       │   │
│  │  Event delivery:                                                      │   │
│  │  - Events guaranteed in revision order                                │   │
│  │  - No event loss (watch stores last sent revision)                   │   │
│  │  - Compaction safety: if requested revision compacted → error        │   │
│  │  - Client must re-create watch from latest revision                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Watch event:                                                                │
│  {                                                                           │
│    "type": "PUT" | "DELETE",                                                │
│    "kv": { "key": "/foo", "value": "bar", "mod_revision": 150 },          │
│    "prev_kv": { ... }  (optional, if WithPrevKV())                         │
│  }                                                                           │
│                                                                              │
│  Kubernetes uses ~10K watches per apiserver connection to etcd              │
│  Each watch = one key prefix (e.g., /registry/pods/default/)               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Lease & TTL System

### Lease Mechanism
```
Leases provide TTL (time-to-live) for keys:

Grant lease → Attach keys → KeepAlive (renew) → Expires → Keys deleted

Use cases:
- Service discovery (ephemeral registrations)
- Distributed locks (lock held while lease alive)
- Session management (client health detection)
- Leader election (leader key expires on failure)

┌──────────────────────────────────────────────────────────────────────┐
│ Lease lifecycle:                                                      │
│                                                                       │
│ 1. Client: LeaseGrant(TTL=30s) → lease_id=12345                     │
│ 2. Client: Put(key="/services/web1", lease=12345)                    │
│ 3. Client: Put(key="/services/web2", lease=12345) (same lease!)     │
│ 4. Client: LeaseKeepAlive(12345) every 10s (stream)                  │
│    ... client keeps renewing ...                                      │
│ 5. Client crashes → no more KeepAlive                                │
│ 6. 30 seconds pass → Lease expires                                   │
│ 7. etcd: Deletes /services/web1 and /services/web2                  │
│ 8. Watchers on /services/ receive DELETE events                      │
│                                                                       │
│ Lease checkpoint (3.4+):                                              │
│ - Leader periodically checkpoints remaining TTL to followers         │
│ - On leader failover: TTL doesn't reset to full duration             │
│ - Without checkpoint: TTL could be extended by failover              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Kubernetes Integration

### How kube-apiserver Uses etcd
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                KUBERNETES + etcd INTEGRATION                                  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  kube-apiserver                                                       │   │
│  │                                                                       │   │
│  │  Responsibilities:                                                    │   │
│  │  - ONLY component that talks to etcd directly                        │   │
│  │  - All other components (scheduler, controllers) go through API      │   │
│  │  - Stores ALL cluster state in etcd                                  │   │
│  │  - Uses Watch for informers/controller patterns                      │   │
│  │                                                                       │   │
│  │  Key space layout:                                                    │   │
│  │  /registry/                                                           │   │
│  │  ├── pods/{namespace}/{name}                                         │   │
│  │  ├── services/{namespace}/{name}                                     │   │
│  │  ├── deployments/{namespace}/{name}                                  │   │
│  │  ├── configmaps/{namespace}/{name}                                   │   │
│  │  ├── secrets/{namespace}/{name} (encrypted at rest)                  │   │
│  │  ├── nodes/{name}                                                    │   │
│  │  ├── namespaces/{name}                                               │   │
│  │  ├── events/{namespace}/{name}                                       │   │
│  │  ├── leases/{namespace}/{name}                                       │   │
│  │  └── ... (all Kubernetes resource types)                             │   │
│  │                                                                       │   │
│  │  Operations pattern:                                                  │   │
│  │  CREATE pod → etcd Txn: IF key not exists THEN Put key=pod_json      │   │
│  │  UPDATE pod → etcd Txn: IF mod_rev=X THEN Put key=new_json           │   │
│  │  DELETE pod → etcd DeleteRange(key)                                   │   │
│  │  LIST pods  → etcd Range(prefix="/registry/pods/ns/")               │   │
│  │  WATCH pods → etcd Watch(prefix="/registry/pods/ns/", rev=N)        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Scale impact:                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Cluster Size    │ etcd Objects │ etcd DB Size │ Watch Count          │   │
│  ├─────────────────┼──────────────┼──────────────┼──────────────────────┤   │
│  │ 100 nodes       │ ~50K         │ ~200 MB      │ ~5K watches          │   │
│  │ 500 nodes       │ ~250K        │ ~1 GB        │ ~25K watches         │   │
│  │ 1000 nodes      │ ~500K        │ ~2 GB        │ ~50K watches         │   │
│  │ 5000 nodes      │ ~2.5M        │ ~8 GB        │ ~200K watches        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Performance requirements for large K8s clusters:                            │
│  - Write latency p99 < 10ms (for responsive scheduling)                    │
│  - Read latency p99 < 5ms (for list operations)                            │
│  - Watch delivery < 100ms (for controller responsiveness)                   │
│  - NVMe SSD mandatory (WAL write latency critical path)                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Production Deployment Patterns

### Hardware & Configuration
```
Production sizing:

┌───────────────────────────────────────────────────────────────────┐
│ Cluster Size       │ CPU    │ RAM     │ Disk         │ Network    │
├────────────────────┼────────┼─────────┼──────────────┼────────────┤
│ Small (<100 keys/s)│ 2-4    │ 8 GB    │ 50 GB SSD    │ 1 Gbps     │
│ Medium (<1K keys/s)│ 4-8    │ 16 GB   │ 100 GB NVMe  │ 10 Gbps    │
│ Large (K8s 1K node)│ 8-16   │ 32 GB   │ 200 GB NVMe  │ 10 Gbps    │
│ XL (K8s 5K nodes)  │ 16-32  │ 64 GB   │ 500 GB NVMe  │ 25 Gbps    │
└────────────────────┴────────┴─────────┴──────────────┴────────────┘

CRITICAL: Disk latency is THE #1 performance factor
- etcd WAL requires low-latency sequential writes
- Use dedicated NVMe SSD (not shared with other workloads)
- p99 disk write latency should be < 10ms
- If on cloud: use provisioned IOPS (AWS io2, GCP pd-ssd)

Key configuration:
  --heartbeat-interval=100          # ms (default 100)
  --election-timeout=1000           # ms (default 1000, must be > heartbeat × 5)
  --snapshot-count=10000            # Raft entries between snapshots
  --quota-backend-bytes=8589934592  # DB size limit (8GB)
  --auto-compaction-mode=periodic
  --auto-compaction-retention=1h    # Keep 1h of history
  --max-request-bytes=1572864       # 1.5MB max request size
  --max-txn-ops=128                 # Max operations per transaction

Monitoring critical metrics:
  etcd_server_leader_changes_seen_total    # Leader stability
  etcd_disk_wal_fsync_duration_seconds     # Disk health (p99 < 10ms!)
  etcd_disk_backend_commit_duration_seconds # Backend commit time
  etcd_server_proposals_failed_total       # Failed Raft proposals
  etcd_mvcc_db_total_size_in_bytes         # Database size
  etcd_network_peer_round_trip_time_seconds # Peer latency
```

### Backup & Disaster Recovery
```
Backup strategies:

# Snapshot backup (recommended)
etcdctl snapshot save /backup/etcd-$(date +%Y%m%d).snap \
  --endpoints=https://etcd1:2379 \
  --cert=/etc/etcd/client.crt \
  --key=/etc/etcd/client.key \
  --cacert=/etc/etcd/ca.crt

# Verify snapshot
etcdctl snapshot status /backup/etcd-20240101.snap --write-out=table

# Restore from snapshot (new cluster)
etcdctl snapshot restore /backup/etcd-20240101.snap \
  --name etcd1 \
  --initial-cluster etcd1=https://host1:2380,etcd2=https://host2:2380,etcd3=https://host3:2380 \
  --initial-advertise-peer-urls https://host1:2380 \
  --data-dir /var/lib/etcd

Production backup plan:
- Snapshot every 30 minutes (cron job)
- Store snapshots in object storage (S3/GCS)
- Retain: 24h of 30min snapshots, 7 days of daily, 90 days of weekly
- Test restore quarterly
- RPO: 30 minutes (time between snapshots)
- RTO: 5-15 minutes (restore + cluster bootstrap)
```

---

## Client Libraries & gRPC API

### Concurrency Primitives
```
etcd provides distributed concurrency primitives:

1. Distributed Lock:
   cli, _ := clientv3.New(...)
   session, _ := concurrency.NewSession(cli, concurrency.WithTTL(10))
   mutex := concurrency.NewMutex(session, "/locks/my-resource")
   
   mutex.Lock(ctx)    // blocks until acquired
   // ... critical section ...
   mutex.Unlock(ctx)
   
   Implementation: Creates key with lease under /locks/my-resource/
   Ordering: Uses revision-based ordering (waiters queue in order)
   Fault tolerance: Lease expires → lock released

2. Leader Election:
   election := concurrency.NewElection(session, "/election/scheduler")
   
   election.Campaign(ctx, "node-1")  // blocks until elected
   // ... I am the leader ...
   election.Resign(ctx)
   
   Observers:
   election.Observe(ctx)  // channel of leader changes

3. STM (Software Transactional Memory):
   // Atomic read-modify-write
   concurrency.NewSTM(cli, func(stm concurrency.STM) error {
       balance := stm.Get("/accounts/alice")
       newBalance := parseInt(balance) - 100
       stm.Put("/accounts/alice", toString(newBalance))
       return nil
   })
   
   Implementation: Optimistic concurrency (retry on conflict)

4. Watch-based coordination:
   // Wait for a condition
   watchChan := cli.Watch(ctx, "/signals/ready", clientv3.WithPrefix())
   for resp := range watchChan {
       for _, ev := range resp.Events {
           // React to changes
       }
   }
```

---

## Use Case Architectures

### Service Discovery
```
┌─────────────────────────────────────────────────────────────────┐
│          SERVICE DISCOVERY WITH etcd                              │
│                                                                   │
│  Service Registration:                                           │
│  ┌──────────────┐                                               │
│  │ Service A    │──── PUT /services/web/instance1               │
│  │ instance 1   │     value: {"host":"10.0.1.1","port":8080}    │
│  │              │     lease: 30s TTL                             │
│  │              │──── KeepAlive every 10s                        │
│  └──────────────┘                                               │
│                                                                   │
│  Service Discovery:                                              │
│  ┌──────────────┐                                               │
│  │ Client       │──── GET /services/web/ (prefix)               │
│  │              │◀─── [instance1, instance2, instance3]          │
│  │              │                                                │
│  │              │──── WATCH /services/web/ (prefix)              │
│  │              │◀─── Events: instance2 DELETED (unhealthy)     │
│  │              │◀─── Events: instance4 PUT (new instance)      │
│  └──────────────┘                                               │
│                                                                   │
│  Health detection:                                               │
│  - Service crashes → KeepAlive stops → Lease expires            │
│  - Key deleted → Watch fires DELETE event                       │
│  - Clients remove instance from load balancer                   │
│  - Recovery: Service restarts → Re-registers with new lease     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Staff Architect Interview Questions

### Q1: Why does etcd use Raft instead of Paxos?
```
Answer:
Raft was specifically designed to be understandable (vs Paxos which is 
notoriously difficult to implement correctly).

Key differences:
- Raft: Strong leader model (all writes through leader)
  Paxos: Multi-leader possible (more complex conflict resolution)
  
- Raft: Leader election is integral part of protocol
  Paxos: Separate mechanism needed for leader selection
  
- Raft: Log entries committed in order (no gaps)
  Paxos: Out-of-order commits possible (need additional protocol)

- Raft: Membership changes via joint consensus
  Paxos: More complex reconfiguration

etcd benefits from Raft:
- Easier to reason about correctness
- Simpler implementation (fewer edge cases)
- Strong leader = predictable write path
- Ordered log = simpler state machine application
- Well-tested open-source implementation (etcd/raft library)
```

### Q2: How does etcd handle the split-brain problem?
```
Answer:
etcd prevents split-brain through Raft's quorum requirement:

3-node cluster: Quorum = 2 (can tolerate 1 failure)
5-node cluster: Quorum = 3 (can tolerate 2 failures)

Network partition scenario (3 nodes):
  Partition A: [Node1 (leader)]          ← minority (1 node)
  Partition B: [Node2, Node3]            ← majority (2 nodes)

What happens:
1. Node1 (old leader) in minority partition:
   - Cannot replicate to quorum
   - All proposals timeout and fail
   - Step-down timer may trigger (implementation dependent)
   - Clients get errors (write fails)

2. Node2 or Node3 in majority partition:
   - Election timeout triggers
   - New leader elected (has quorum of 2)
   - Writes succeed on new leader
   - System continues operating

3. Partition heals:
   - Node1 discovers higher term → becomes follower
   - Node1 truncates any uncommitted log entries
   - Node1 catches up from new leader
   - No conflicting committed entries possible

Key guarantee: No committed entry is ever lost or conflicted
```

### Q3: Explain etcd's MVCC and why it matters for Kubernetes
```
Answer:
MVCC (Multi-Version Concurrency Control):
- Every write creates a new revision (never overwrites)
- Old revisions available until compacted
- Enables: watches from historical revision, optimistic concurrency

Why it matters for Kubernetes:
1. Watch resumption:
   - Controller disconnects temporarily
   - Reconnects with "give me events since revision X"
   - No missed events (if within compaction window)
   - Without MVCC: would need separate event log

2. Optimistic concurrency (resourceVersion):
   - kubectl updates use If-Match semantics
   - "Update pod IF resourceVersion still = 12345"
   - Maps directly to etcd's mod_revision
   - Prevents lost updates in concurrent modifications

3. List consistency:
   - LIST at specific revision = consistent snapshot
   - No partial reads during concurrent writes
   - Informers get consistent starting state

4. Efficient watches:
   - Watch from specific revision (not "now")
   - Server replays events from that revision
   - Catch-up without full re-list
```

### Q4: What happens when etcd database reaches its quota?
```
Answer:
Default quota: 2GB, configurable up to 8GB

When quota exceeded:
1. etcd enters ALARM state (NO_SPACE alarm)
2. ALL writes rejected (entire cluster read-only)
3. Watches continue working (reads still work)
4. Existing leases stop refreshing (will expire!)

Recovery steps:
1. Get current alarm: etcdctl alarm list
2. Compact old revisions: etcdctl compact <revision>
3. Defragment to reclaim space: etcdctl defrag --cluster
4. Disarm alarm: etcdctl alarm disarm
5. Writes resume

Prevention:
- Monitor: etcd_mvcc_db_total_size_in_bytes
- Alert at 80% of quota
- Auto-compaction: --auto-compaction-mode=periodic --auto-compaction-retention=1h
- Regular defragmentation (weekly cron, rolling across nodes)
- Size quota appropriate for workload (don't set too small)
```

### Q5-Q10: Additional Questions
```
Q5: How to perform zero-downtime etcd upgrades?
- Rolling upgrade one node at a time
- Order: followers first, leader last
- Version skew: max 1 minor version difference
- Steps per node:
  1. Stop etcd process
  2. Backup data directory
  3. Replace binary
  4. Start with same flags
  5. Verify cluster health before next node
- Leader will change during its restart (automatic re-election)

Q6: What's the impact of clock skew on etcd?
- Raft doesn't depend on synchronized clocks for correctness
- Impact is on: lease TTL accuracy, election timeout behavior
- Large clock skew → unstable leader (constant elections)
- Recommendation: Use NTP, max 50ms clock skew
- Monitoring: etcd_server_leader_changes_seen_total (frequent = problem)

Q7: Compare etcd 3.4 vs 3.5 improvements
- 3.5: Downgrade support (can go back to 3.4)
- 3.5: Structured logging (JSON format)
- 3.5: Migration to bbolt from coreos/bbolt
- 3.5: Improved watch performance
- 3.5: Experimental distributed tracing (OpenTelemetry)
- 3.5: LeaseCheckpoint improvements
- 3.5: Better memory usage in large watch workloads

Q8: How does etcd handle a slow follower?
- Leader sends AppendEntries to all followers
- If follower falls behind: Leader sends snapshot instead
- Snapshot = full state transfer (expensive but rare)
- Learner nodes: Non-voting members that catch up without affecting quorum
- Monitoring: etcd_server_slow_apply_total, etcd_network_peer_sent_bytes_total

Q9: What are the limitations of etcd transactions?
- Max 128 operations per transaction (configurable)
- Max 1.5MB request size
- All operations atomic (all-or-nothing)
- Compare-then-act (not multi-statement SQL transactions)
- Format: IF conditions THEN operations ELSE operations
- No nested transactions
- No read-your-writes within same txn (use STM for that)

Q10: How would you migrate etcd to a new set of nodes?
- Option 1: Add new nodes one at a time, remove old ones
  (member add → wait sync → member remove, repeat)
- Option 2: Snapshot + restore on new nodes
  (faster but requires downtime)
- Option 3: Learner-based migration
  (add as learners → promote → remove old members)
- Always: Maintain quorum throughout the process
```

---

## Scenario-Based Questions

### Scenario 1: etcd write latency spikes causing K8s API slowness
```
Diagnosis:
1. Check disk latency: etcd_disk_wal_fsync_duration_seconds
   - p99 > 10ms? → Disk I/O problem
   - Cloud VMs: check for noisy neighbor, throttling

2. Check network latency: etcd_network_peer_round_trip_time_seconds
   - High? → Network congestion between etcd nodes
   
3. Check database size: etcd_mvcc_db_total_size_in_bytes
   - Near quota? → Compaction + defrag needed

4. Check range queries: etcd_server_range_duration_seconds
   - Expensive LIST operations from apiserver?

Solutions:
- Immediate: Move etcd to dedicated NVMe SSD
- Short-term: Increase IOPS (cloud: provision more)
- Medium-term: Tune compaction (more frequent, smaller batches)
- Long-term: Scale K8s apiservers (reduce per-apiserver watch load)
```

### Scenario 2: etcd cluster lost quorum (2 of 3 nodes failed)
```
EMERGENCY - cluster is DOWN (no writes, no new watches)

Recovery options:

Option A: Restore failed nodes (preferred if possible)
1. Check if nodes can be restarted with existing data
2. If data intact: restart nodes, cluster self-heals
3. Time: minutes (if just process crash)

Option B: Force new cluster from remaining node
1. etcdctl snapshot save on surviving node
2. Stop all etcd processes
3. etcdctl snapshot restore with --force-new-cluster
4. Start single-node cluster
5. Add new members one at a time
6. Risk: May lose some uncommitted data

Option C: Restore from backup
1. Get latest snapshot from backup storage
2. Restore on all 3 nodes (new cluster)
3. Data loss: Up to backup interval (RPO)
4. Restart kube-apiservers to reconnect

Prevention:
- 5-node cluster (tolerates 2 failures)
- Automated monitoring with fast alerting
- Regular backup testing (quarterly restore drill)
- Cross-AZ deployment (no single AZ failure takes quorum)
```

### Scenario 3: Kubernetes cluster with 5000 nodes hitting etcd limits
```
Challenge: Large K8s clusters stress etcd significantly

Problems:
- DB size approaching 8GB quota
- Watch count: 200K+ active watches
- Event churn: 10K+ events/sec
- LIST operations: large responses (30MB+)

Solutions:
1. Separate etcd clusters:
   - Events cluster: /registry/events/ (high churn, not critical)
   - Main cluster: everything else
   - kube-apiserver supports --etcd-servers-overrides

2. Reduce object size:
   - Limit Pod spec size (enforce resource policies)
   - Compress secrets at application layer
   - Use server-side field selectors

3. Reduce event volume:
   - Event TTL (garbage collection)
   - Deduplicate similar events
   - Rate-limit controller reconciliation

4. Tune etcd:
   - --quota-backend-bytes=8589934592 (8GB)
   - --auto-compaction-retention=3h (more aggressive)
   - Defrag weekly (off-peak)
   - 5 nodes (better read distribution)

5. Consider K8s API optimization:
   - Watch bookmarks (reduce reconnect cost)
   - API Priority and Fairness (rate limiting)
   - Informer cache improvements
```

### Scenario 4: Data corruption detected in etcd
```
Symptoms:
- etcd_debugging_mvcc_db_compaction_keys_total shows unexpected values
- Inconsistent data between etcd nodes
- Kubernetes objects have corrupted fields

Investigation:
1. Compare data across nodes:
   etcdctl get "" --prefix --keys-only (compare key count)
2. Check for WAL corruption: etcd logs for "WAL" errors
3. Check bbolt integrity: etcdctl check dataquorum

Resolution:
1. If single node corrupted:
   - Remove corrupted node from cluster
   - Wipe its data directory
   - Re-add as new member (will sync from healthy nodes)

2. If multiple nodes corrupted:
   - Restore from last known-good snapshot
   - Validate data integrity
   - Investigate root cause (disk failure? bug?)

3. Post-incident:
   - Review hardware health (SMART data on SSDs)
   - Enable checksums if not already
   - Increase backup frequency
   - Consider separate backup validation (restore + compare)
```

### Scenario 5: Migrating from ZooKeeper to etcd for a distributed system
```
Migration plan:

Phase 1 - Assessment (1 week):
  - Map ZooKeeper ZNode structure to etcd key space
  - Identify ZooKeeper-specific features used:
    - Ephemeral nodes → etcd leases
    - Sequential nodes → etcd revision ordering
    - Watches → etcd watch (improvement: not one-shot)
    - ACLs → etcd RBAC

Phase 2 - Adapter layer (2 weeks):
  - Build abstraction layer over both backends
  - Interface: Get, Put, Delete, Watch, Lock, Elect
  - Dual-write during migration period
  - Feature-flag to switch between backends

Phase 3 - Parallel running (2 weeks):
  - Both systems active
  - Compare operations between ZK and etcd
  - Validate watch delivery correctness
  - Performance comparison

Phase 4 - Cutover (1 week):
  - Switch to etcd as primary
  - ZooKeeper as read-only backup (1 week)
  - Decommission ZooKeeper

Key advantages gained:
  - gRPC API (better than ZK custom protocol)
  - Multi-version watches (not one-shot)
  - Simpler operations (no znodes hierarchy)
  - Better K8s ecosystem alignment
```
