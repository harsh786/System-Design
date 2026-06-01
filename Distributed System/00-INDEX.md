# Distributed Systems Concepts - Staff Architect Level

> A comprehensive reference covering 30 fundamental distributed systems concepts with real-world implementations, ASCII diagrams, and architect-level decision frameworks.

---

## Table of Contents

### Foundational Theory
| # | Concept | Key Systems | Core Insight |
|---|---------|-------------|--------------|
| 01 | [CAP Theorem](./01-CAP-Theorem.md) | Spanner, DynamoDB, Cassandra | You can't have C+A+P simultaneously during partitions |
| 02 | [Consistent Hashing](./02-Consistent-Hashing.md) | DynamoDB, Cassandra, Akamai | Only K/N keys move when nodes change |
| 17 | [Lamport Timestamps](./17-Lamport-Timestamps.md) | Kafka, Spanner, CockroachDB | Logical ordering without synchronized clocks |
| 03 | [Vector Clocks](./03-Vector-Clocks.md) | DynamoDB, Riak, Voldemort | Detect causality AND concurrency between events |
| 28 | [Clock Synchronization](./28-Clock-Synchronization.md) | Spanner TrueTime, NTP, PTP | Physical time uncertainty is unavoidable but boundable |

### Consensus & Coordination
| # | Concept | Key Systems | Core Insight |
|---|---------|-------------|--------------|
| 12 | [Paxos Consensus](./12-Paxos-Consensus.md) | Chubby, Spanner, ZooKeeper (ZAB) | The foundational consensus algorithm (correct but hard) |
| 13 | [Raft Consensus](./13-Raft-Consensus.md) | etcd, CockroachDB, Consul, TiKV | Understandable consensus with same guarantees as Paxos |
| 09 | [Leader Election](./09-Leader-Election.md) | Kafka, HDFS, Kubernetes | Single coordinator for serializing decisions |
| 14 | [Two-Phase Commit](./14-Two-Phase-Commit.md) | Spanner, MySQL XA, MSDTC | Atomic commitment across nodes (blocking risk) |
| 21 | [Fencing Tokens](./21-Fencing-Tokens.md) | ZooKeeper, etcd, Kafka epochs | Prevent stale leaders from corrupting data |
| 26 | [Lease Mechanism](./26-Lease-Mechanism.md) | Chubby, HDFS, Kubernetes | Time-bounded authority that self-heals on failure |

### Replication & Consistency
| # | Concept | Key Systems | Core Insight |
|---|---------|-------------|--------------|
| 08 | [Quorum](./08-Quorum.md) | Cassandra, DynamoDB, Raft | R+W>N guarantees read-write overlap |
| 25 | [Sloppy Quorum](./25-Sloppy-Quorum.md) | DynamoDB, Riak | Trade consistency for availability during failures |
| 06 | [Hinted Handoff](./06-Hinted-Handoff.md) | Cassandra, DynamoDB, Riak | Temporary storage for writes to failed nodes |
| 19 | [Read Repair](./19-Read-Repair.md) | Cassandra, DynamoDB, Riak | Fix stale replicas lazily during reads |
| 22 | [Anti-Entropy & Dissemination](./22-Anti-Entropy-and-Dissemination.md) | Cassandra, DynamoDB | Proactive background repair of replica divergence |
| 24 | [Chain Replication](./24-Chain-Replication.md) | HDFS, Azure Storage | Strong consistency with pipelined write throughput |
| 15 | [CRDT](./15-CRDT.md) | Redis, Riak, Figma, Automerge | Conflict-free convergence without coordination |

### Failure Detection & Handling
| # | Concept | Key Systems | Core Insight |
|---|---------|-------------|--------------|
| 04 | [Split Brain](./04-Split-Brain.md) | Elasticsearch, Kafka, PostgreSQL | Network partitions create dangerous dual-master scenarios |
| 07 | [Gossip Protocol](./07-Gossip-Protocol.md) | Cassandra, Consul, Redis Cluster | Epidemic dissemination scales to thousands of nodes |
| 18 | [Phi Accrual Failure Detector](./18-Phi-Accrual-Failure-Detector.md) | Cassandra, Akka | Suspicion level instead of binary alive/dead |
| 29 | [Backpressure & Load Shedding](./29-Backpressure-and-Load-Shedding.md) | TCP, Kafka, Flink, Envoy | Controlled degradation prevents cascading failure |

### Storage & Data Structures
| # | Concept | Key Systems | Core Insight |
|---|---------|-------------|--------------|
| 05 | [Bloom Filter](./05-Bloom-Filter.md) | Cassandra, RocksDB, Chrome | Probabilistic "definitely not in set" with zero false negatives |
| 10 | [Write-Ahead Log](./10-Write-Ahead-Log.md) | PostgreSQL, Kafka, etcd | Sequential append for crash recovery before data mutation |
| 11 | [Merkle Trees](./11-Merkle-Trees.md) | Cassandra, Git, Bitcoin, IPFS | O(log N) difference detection between datasets |
| 20 | [LSM Tree](./20-LSM-Tree.md) | RocksDB, Cassandra, HBase | Convert random writes to sequential for high throughput |
| 27 | [Tombstones & Soft Deletes](./27-Tombstones-and-Soft-Deletes.md) | Cassandra, Kafka, HBase | Deletions require markers to prevent resurrection |

### Distributed Transactions & Patterns
| # | Concept | Key Systems | Core Insight |
|---|---------|-------------|--------------|
| 16 | [Saga Pattern](./16-Saga-Pattern.md) | Uber/Temporal, Netflix, AWS Step Functions | Compensating transactions for long-lived workflows |
| 23 | [Distributed Snapshots](./23-Distributed-Snapshots.md) | Flink, Spark, CockroachDB | Consistent global state capture without stopping the system |
| 30 | [Partitioning Strategies](./30-Partitioning-Strategies.md) | Cassandra, MongoDB, Kafka, Vitess | Splitting data across nodes while maintaining access patterns |

---

## Reading Order Recommendations

### For System Design Interviews
1. CAP Theorem → Consistent Hashing → Quorum → Partitioning
2. Leader Election → Raft → Split Brain → Fencing Tokens
3. Write-Ahead Log → LSM Tree → Bloom Filter
4. Gossip Protocol → Hinted Handoff → Read Repair → Anti-Entropy
5. Saga Pattern → Two-Phase Commit → CRDT

### For Building Distributed Databases
1. CAP Theorem → Quorum → Consistent Hashing → Partitioning
2. Write-Ahead Log → LSM Tree → Merkle Trees → Bloom Filter
3. Raft → Leader Election → Fencing Tokens → Lease
4. Vector Clocks → CRDT → Read Repair → Anti-Entropy → Tombstones
5. Chain Replication → Distributed Snapshots

### For Building Microservices
1. CAP Theorem → Saga Pattern → Two-Phase Commit
2. Backpressure → Gossip Protocol → Phi Accrual Failure Detector
3. Consistent Hashing → Partitioning → Sloppy Quorum
4. Leader Election → Lease → Fencing Tokens → Split Brain
5. Clock Synchronization → Lamport Timestamps

---

## Concept Relationship Map

```
                         ┌─────────────────┐
                         │   CAP Theorem   │
                         └────────┬────────┘
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              ┌──────────┐ ┌──────────┐ ┌──────────────┐
              │    CP    │ │    AP    │ │   PACELC     │
              │ Systems  │ │ Systems  │ │  Extension   │
              └────┬─────┘ └────┬─────┘ └──────────────┘
                   │            │
         ┌─────────┘     ┌──────┘
         ▼               ▼
   ┌──────────┐    ┌──────────────┐
   │  Raft/   │    │  Consistent  │──→ Partitioning
   │  Paxos   │    │   Hashing    │
   └────┬─────┘    └──────┬───────┘
        │                  │
        ▼                  ▼
   ┌──────────┐    ┌──────────────┐
   │  Leader  │    │   Quorum /   │──→ Sloppy Quorum
   │ Election │    │   Replicas   │
   └────┬─────┘    └──────┬───────┘
        │                  │
        ▼                  ▼
   ┌──────────┐    ┌──────────────┐    ┌──────────┐
   │ Fencing  │    │Hinted Handoff│──→ │  Read    │
   │  Tokens  │    │              │    │  Repair  │
   └──────────┘    └──────────────┘    └────┬─────┘
                                            │
                                            ▼
                                     ┌──────────────┐
                                     │ Anti-Entropy │──→ Merkle Trees
                                     └──────────────┘
```

---

## Systems Cross-Reference

| System | Concepts Used |
|--------|-------------|
| **Apache Cassandra** | Consistent Hashing, Gossip, Quorum, Hinted Handoff, Read Repair, Anti-Entropy, Bloom Filter, LSM Tree, Merkle Trees, Tombstones, Phi Accrual, Vector Clocks |
| **Amazon DynamoDB** | Consistent Hashing, Sloppy Quorum, Hinted Handoff, Vector Clocks, Gossip, Anti-Entropy, LSM Tree |
| **Google Spanner** | Paxos, 2PC, TrueTime (Clock Sync), Leader Election, Distributed Snapshots |
| **Apache Kafka** | WAL, Partitioning, Leader Election, Fencing (Epochs), ISR (Quorum variant) |
| **etcd** | Raft, WAL, Leader Election, Lease, Fencing Tokens, Distributed Snapshots |
| **CockroachDB** | Raft, HLC (Clocks), MVCC (Snapshots), Range Partitioning, 2PC |
| **Redis Cluster** | Gossip, Consistent Hashing, Split Brain detection |
| **Apache Flink** | Distributed Snapshots (ABS), Backpressure, Checkpointing |

---

## Key Papers Reference

| Paper | Year | Concept |
|-------|------|---------|
| "Time, Clocks, and the Ordering of Events" - Lamport | 1978 | Lamport Timestamps |
| "The Part-Time Parliament" - Lamport | 1998 | Paxos |
| "Brewer's Conjecture" - Gilbert & Lynch | 2002 | CAP Theorem |
| "Dynamo: Amazon's Highly Available Key-Value Store" | 2007 | Consistent Hashing, Sloppy Quorum, Vector Clocks, Gossip |
| "In Search of an Understandable Consensus Algorithm" - Ongaro | 2014 | Raft |
| "Spanner: Google's Globally-Distributed Database" | 2012 | TrueTime, 2PC over Paxos |
| "SWIM: Scalable Weakly-consistent Infection-style Membership" | 2002 | Gossip/Failure Detection |
| "A comprehensive study of CRDTs" - Shapiro et al. | 2011 | CRDTs |
| "The Phi Accrual Failure Detector" - Hayashibara et al. | 2004 | Phi Accrual |
| "Chandy-Lamport Distributed Snapshots" | 1985 | Distributed Snapshots |

---

*Total: 30 concepts | ~1.5MB of content | Staff Architect level depth*
