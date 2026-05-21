# Distributed Systems

_Split from `../world_class_pro_architect_master_roadmap.md`. The original source file is intentionally untouched._

---

# 9. Distributed Systems Roadmap

## Core Mental Model

A distributed system is a system where independent nodes communicate over unreliable networks and still try to provide useful guarantees. Every architect must think about partial failure, time, ordering, replication, consistency, and recovery.

## Must-Master Concepts

### CAP Theorem

- During a partition, choose consistency or availability.
- Do not say a database is simply CP/AP without explaining the operation and failure mode.

### PACELC

- If partition happens: availability vs consistency.
- Else: latency vs consistency.

### Consistency Models

- Linearizability.
- Serializability.
- Sequential consistency.
- Causal consistency.
- Read-your-writes.
- Monotonic reads.
- Bounded staleness.
- Eventual consistency.

### Consensus

- Raft.
- Paxos.
- Zab-like coordination concepts.
- Leader election.
- Log replication.
- Quorum commit.
- Membership changes.

### Replication

- Leader-follower.
- Multi-leader.
- Leaderless.
- Quorum read/write.
- Synchronous vs asynchronous.
- Conflict resolution.
- Read repair.
- Hinted handoff.
- Anti-entropy.

### Partitioning

- Hash partitioning.
- Range partitioning.
- Consistent hashing.
- Rendezvous hashing.
- Virtual nodes.
- Rebalancing.
- Hot partition mitigation.

### Clocks and Ordering

- Physical clocks.
- Clock skew.
- Logical clocks.
- Lamport clocks.
- Vector clocks.
- Hybrid logical clocks.
- Causal ordering.

### Failure Modes

- Split brain.
- Network partition.
- Slow node.
- GC pause.
- Duplicate messages.
- Reordered messages.
- Lost acknowledgements.
- Retry storms.
- Thundering herd.
- Cascading failure.

### Safety Mechanisms

- Idempotency.
- Deduplication.
- Fencing tokens.
- Leases.
- Timeouts.
- Retries with jitter.
- Circuit breakers.
- Bulkheads.
- Backpressure.
- Load shedding.

## Hands-On Labs

1. Implement consistent hashing with virtual nodes.
2. Implement quorum read/write simulator.
3. Implement vector-clock conflict detection.
4. Implement Merkle-tree anti-entropy comparison.
5. Implement leader election using a coordination store.
6. Simulate split brain and fencing tokens.
7. Simulate hinted handoff and read repair.
8. Run chaos tests on a replicated service.

---


