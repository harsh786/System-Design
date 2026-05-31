# Problem 120: Design a Globally Distributed SQL Database (like Spanner/CockroachDB)

## Problem Statement

Design a globally distributed SQL database that provides strong consistency (serializable
isolation) across geographically distributed nodes while maintaining high availability
and horizontal scalability. The system must support standard SQL with ACID transactions.

## Key Challenges

1. **Distributed Transactions with 2PC + Paxos**: Implement atomic commits across shards
   using two-phase commit coordinated through consensus groups.
2. **TrueTime/Hybrid Logical Clocks**: Provide external consistency (linearizability)
   using synchronized clocks or hybrid logical clocks for transaction ordering.
3. **Range-Based Sharding with Automatic Splits**: Partition data into ranges that
   automatically split and merge based on size and load.
4. **Distributed Query Planning**: Optimize and execute SQL queries that span multiple
   shards with pushdown predicates and distributed joins.
5. **Geo-Partitioning for Data Residency**: Pin data ranges to specific regions for
   compliance while maintaining global transaction capability.
6. **Online Schema Changes**: Perform DDL operations without downtime using phased
   rollouts across all nodes.
7. **Multi-Version Concurrency Control (MVCC)**: Maintain multiple versions of data
   for non-blocking reads and consistent snapshots.

## Scale Requirements

- Petabytes of structured data
- Millions of transactions per second globally
- <10ms read latency within a region
- <100ms cross-region transaction commits
- 99.999% availability (five nines)
- Support for thousands of concurrent schema-diverse tables

## Expected Discussion Areas

- Raft/Paxos consensus per range/shard
- Timestamp oracle vs TrueTime vs HLC trade-offs
- Leaseholder and follower read optimizations
- Transaction conflict resolution and retry protocols
- Storage engine design (LSM-tree vs B-tree per workload)
