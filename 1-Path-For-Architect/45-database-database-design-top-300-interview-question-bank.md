# Top 360 Database and Database Design Interview Question Bank

Purpose: prepare for staff, principal, and architect interviews where database depth decides whether a design is correct, scalable, and operable.

Use this with:

- `06-database-design-internals.md` for storage engines, transactions, indexing, replication, CAP, and internals.
- `07-database-technologies-selection.md` for choosing PostgreSQL, MySQL, MongoDB, ScyllaDB, Aerospike, Redis, DynamoDB, ClickHouse, warehouses, lakehouse, vector, graph, and time-series stores.
- `08-distributed-systems.md` for consensus, partitions, clocks, quorums, and split brain.
- `17-caching-scaling-rate-limiting-resilience.md` for caching, hot keys, scaling, and resilience patterns.

How to practice:

1. Answer each question out loud in 3-5 minutes.
2. For every answer, state the workload, access pattern, correctness requirement, failure mode, and operational signal.
3. For every concurrency question, name the invariant, anomaly, locking or MVCC behavior, retry strategy, and idempotency boundary.
4. For every technology choice, explain why the chosen database fits and why at least two alternatives are weaker.
5. For architect-level answers, connect the topic to latency, throughput, consistency, durability, availability, cost, migration, and recovery.

## Category Map

| Category | Range | What It Trains |
|---|---:|---|
| Data modeling, requirements, and access patterns | 1-15 | Turning product behavior into durable data shape |
| Relational fundamentals, normalization, and constraints | 16-30 | Relational correctness and schema discipline |
| Storage engines, pages, WAL, and MVCC internals | 31-45 | How databases physically store, recover, and read data |
| ACID, transactions, isolation levels, and anomalies | 46-60 | Correct transaction reasoning under concurrency |
| Locking, deadlocks, contention, and concurrency control | 61-75 | Pessimistic, optimistic, MVCC, OCC, 2PL, SSI, and lock behavior |
| Booking, reservation, inventory, and distributed scheduling correctness | 76-90 | Double-booking prevention and high-contention workflows |
| Indexing, query planning, and performance tuning | 91-105 | B-trees, composite indexes, query plans, and optimizer behavior |
| Partitioning, sharding, hot keys, and rebalancing | 106-120 | Horizontal scale and data distribution |
| Replication, HA, backup, restore, and disaster recovery | 121-135 | Durability, failover, RPO/RTO, and data-loss prevention |
| Distributed databases, CAP, PACELC, quorums, and consensus | 136-150 | Distributed consistency and partition trade-offs |
| Relational product deep dives | 151-165 | PostgreSQL, MySQL/InnoDB, SQL Server, Oracle, and distributed SQL |
| NoSQL data models and design trade-offs | 166-180 | Document, wide-column, key-value, graph, and schema-less modeling |
| ScyllaDB, Cassandra, HBase, DynamoDB, and Aerospike | 181-195 | High-scale operational stores and predictable access patterns |
| Caching databases, Redis, Memcached, and cache correctness | 196-210 | Cache design, stampedes, eviction, locking, and ephemeral state |
| Search, vector, and graph databases | 211-225 | Retrieval, relevance, ANN, graph traversal, and source-of-truth limits |
| Time-series, OLAP, warehouse, lakehouse, and HTAP | 226-240 | Analytical storage and user-facing analytics systems |
| Multi-region, geo-distribution, tenancy, security, and compliance | 241-255 | Global data, isolation, residency, encryption, and governance |
| Schema migration, CDC, events, and data evolution | 256-270 | Safe change management and service data ownership |
| Operations, observability, maintenance, and cost | 271-285 | Running databases in production |
| Architect-level database selection and synthesis | 286-300 | Senior trade-off judgment across real scenarios |
| Database administration, diagnostics, and troubleshooting | 301-330 | Locks, plans, waits, replication slots, sessions, and production forensics |
| CDC, Debezium, Kafka Connect, and logical replication | 331-360 | Change data capture, connector operations, slots, offsets, snapshots, and schema history |

## 1. Data Modeling, Requirements, and Access Patterns

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 1 | How do you start a database design discussion for a new system? | Entities, workflows, invariants, read/write paths, scale, latency, consistency, retention, compliance, and non-goals. |
| 2 | How do you identify the real consistency boundaries in a domain? | Business invariants, aggregate boundaries, transaction scope, async tolerance, compensation, and user-visible correctness. |
| 3 | How do you turn product requirements into a logical data model? | Entities, relationships, cardinality, lifecycle, ownership, constraints, queries, events, and audit needs. |
| 4 | What is the difference between conceptual, logical, and physical data modeling? | Domain concepts, schema shape, storage layout, indexes, partitioning, distribution, and engine-specific tuning. |
| 5 | How do access patterns drive database design? | Query-first modeling, write paths, sort/filter needs, cardinality, index selection, denormalization, and workload drift. |
| 6 | What questions do you ask before choosing SQL or NoSQL? | Consistency, joins, transactions, schema volatility, query flexibility, write scale, latency, operations, and team skill. |
| 7 | How do you model many-to-many relationships at scale? | Join tables, edge tables, denormalized projections, graph stores, fanout limits, and indexing strategy. |
| 8 | How do you model hierarchical data? | Adjacency list, materialized path, nested set, closure table, graph database, path updates, and query depth. |
| 9 | How do you model time-bounded state such as sessions, holds, and leases? | TTL, expiration index, sweeper jobs, monotonic clocks, race handling, idempotent renewal, and cleanup lag. |
| 10 | How do you model immutable events vs mutable current state? | Event log, snapshots, projections, auditability, replay, correction events, query latency, and storage growth. |
| 11 | How do you decide whether to embed or reference data? | Access locality, update frequency, document growth, consistency need, fanout, duplication, and ownership. |
| 12 | How do you design audit trails for critical data? | Immutable history, actor, reason, before/after values, correlation IDs, tamper evidence, retention, and privacy. |
| 13 | How do you model soft deletes? | Deleted flags, tombstones, uniqueness with active rows, restore behavior, retention purge, and index filtering. |
| 14 | How do you design for data retention and archival from day one? | Legal retention, TTL, cold storage, partition pruning, restore path, deletion guarantees, and cost. |
| 15 | What makes a data model architect-grade instead of CRUD-grade? | Explicit invariants, access-pattern fit, migration path, scaling plan, observability, recovery, and operational simplicity. |

## 2. Relational Fundamentals, Normalization, and Constraints

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 16 | Why are relational databases still the default choice for many systems? | ACID, constraints, SQL, joins, maturity, tooling, transactions, backup, and operational familiarity. |
| 17 | Explain primary keys, candidate keys, natural keys, and surrogate keys. | Uniqueness, stability, business meaning, storage impact, joins, migrations, and public identifier safety. |
| 18 | How do foreign keys improve correctness and when might teams avoid them? | Referential integrity, cascading behavior, write overhead, migration friction, cross-service boundaries, and bulk loading. |
| 19 | Explain normalization and why over-normalization can hurt systems. | 1NF/2NF/3NF/BCNF, anomaly reduction, joins, read latency, complexity, and denormalized read models. |
| 20 | When is denormalization the right choice? | Read-heavy paths, precomputed views, controlled duplication, update fanout, consistency lag, and repair jobs. |
| 21 | What is a unique constraint and how does it prevent race conditions? | Atomic enforcement, duplicate prevention, idempotency keys, conflict handling, and transaction isolation limits. |
| 22 | How do check constraints, exclusion constraints, and generated columns help design? | Domain rules in DB, range conflicts, derived values, data quality, performance, and portability trade-offs. |
| 23 | How do you model enum-like states in a relational schema? | Check constraints, lookup tables, state machines, valid transitions, migrations, and invalid state prevention. |
| 24 | How do you design a state machine table for orders, bookings, or payments? | Current state, transition table, versioning, audit log, idempotency, retries, and illegal transition guards. |
| 25 | What is the difference between OLTP and OLAP schema design? | Transactional normalization vs analytical facts/dimensions, query shape, latency, concurrency, and storage layout. |
| 26 | Explain star schema, snowflake schema, facts, and dimensions. | Measures, dimensions, grain, slowly changing dimensions, joins, BI performance, and data quality. |
| 27 | How do you model multi-currency money safely? | Integer minor units, currency code, precision, exchange rate source, rounding, audit, and immutable ledger entries. |
| 28 | How do you model ledgers differently from account balances? | Append-only journal, double-entry, derived balances, reconciliation, idempotency, and auditability. |
| 29 | How do you design idempotency storage in a relational database? | Idempotency key, request hash, response cache, unique constraint, status transitions, TTL, and replay safety. |
| 30 | How do you prevent schema design from leaking service boundaries? | Data ownership, database-per-service, APIs/events, read models, anti-corruption layers, and migration strategy. |

## 3. Storage Engines, Pages, WAL, and MVCC Internals

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 31 | What happens when a database writes a row? | Buffer pool, page modification, WAL/redo, commit, fsync policy, indexes, and replication hooks. |
| 32 | What is a database page or block? | Fixed-size storage unit, tuples, headers, free space, page splits, buffer cache, and I/O granularity. |
| 33 | Explain heap-organized tables vs clustered/index-organized storage. | Row location, primary-key locality, secondary lookup cost, fragmentation, and update behavior. |
| 34 | What is write-ahead logging and why is it required? | Durability, redo before data page, crash recovery, commit acknowledgement, checkpoints, and replication. |
| 35 | What is a checkpoint in a database? | Dirty page flushing, WAL truncation, recovery time, I/O burst risk, and tuning. |
| 36 | Explain undo logs, redo logs, and rollback segments. | Transaction rollback, MVCC visibility, crash recovery, purge, and long transaction impact. |
| 37 | How does MVCC work at a high level? | Row versions, transaction IDs/timestamps, snapshots, visibility rules, vacuum/purge, and write conflicts. |
| 38 | Why can long-running transactions hurt MVCC databases? | Old version retention, vacuum blockage, bloat, undo growth, replication lag, and stale snapshots. |
| 39 | Compare B-tree/B+tree storage and LSM-tree storage. | Read/write amplification, range scans, compaction, page splits, bloom filters, and workload fit. |
| 40 | How does an LSM-tree write path work? | WAL, memtable, flush, SSTables, bloom filters, compaction, tombstones, and write amplification. |
| 41 | What are tombstones and why do they hurt LSM databases? | Deletes as markers, read amplification, compaction debt, range scans, TTL storms, and repair risk. |
| 42 | What is compaction and why can it cause latency spikes? | SSTable merge, obsolete data removal, write/read/space amplification, I/O contention, and throttling. |
| 43 | What is a buffer pool or page cache? | Hot page caching, cache hit ratio, eviction, dirty pages, OS cache interaction, and memory sizing. |
| 44 | How do databases recover after a crash? | WAL replay, undo incomplete transactions, checkpoints, torn-page protection, replication catch-up, and verification. |
| 45 | What storage-engine details should architects know before picking a database? | Access pattern, write path, read path, maintenance, failure recovery, data distribution, and operational limits. |

## 4. ACID, Transactions, Isolation Levels, and Anomalies

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 46 | Explain ACID in practical system design terms. | Atomicity, consistency, isolation, durability, business invariants, crash recovery, and trade-offs. |
| 47 | What is a database transaction? | Unit of work, commit/rollback, isolation, locks or versions, error handling, and retry boundaries. |
| 48 | What does atomicity guarantee and what does it not guarantee? | All-or-nothing DB changes, not external side effects, outbox need, and idempotent integration. |
| 49 | What does consistency mean in ACID vs distributed systems? | Constraint-preserving transitions vs replica visibility, invariant correctness, and overloaded terminology. |
| 50 | What does isolation protect against? | Concurrent anomalies, visibility, write conflicts, read phenomena, and database-specific semantics. |
| 51 | What does durability depend on? | WAL fsync, storage guarantees, replicas, commit mode, backups, corruption detection, and operational settings. |
| 52 | Explain dirty read, non-repeatable read, and phantom read. | Read uncommitted data, changed rows, new matching rows, examples, and isolation-level prevention. |
| 53 | Explain lost update and how to prevent it. | Read-modify-write race, row locks, optimistic version checks, atomic update, and retry logic. |
| 54 | What is write skew? | Snapshot isolation anomaly, disjoint row updates violating invariant, example, and serializable mitigation. |
| 55 | Explain read committed isolation. | Statement-level snapshots or locks, no dirty reads, non-repeatable reads, lost update caveats, and DB differences. |
| 56 | Explain repeatable read isolation. | Transaction snapshot, repeated reads, phantom behavior by engine, next-key locks or MVCC, and write conflicts. |
| 57 | Explain snapshot isolation. | Stable snapshot, first-committer-wins/write conflicts, no dirty reads, write skew risk, and MVCC. |
| 58 | What is serializable isolation? | Equivalent serial order, predicate protection, SSI or 2PL, aborts, throughput cost, and when required. |
| 59 | What is serializable snapshot isolation? | Snapshot reads, dangerous-structure detection, predicate/rw conflicts, serialization failures, and retries. |
| 60 | How do you choose the right isolation level for a workflow? | Invariants, anomaly tolerance, contention, latency, retry cost, locks, DB semantics, and tests. |

## 5. Locking, Deadlocks, Contention, and Concurrency Control

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 61 | Compare pessimistic locking and optimistic locking. | Lock before work vs validate on commit, contention profile, retry cost, deadlocks, and user experience. |
| 62 | What is optimistic concurrency control? | Version column, compare-and-swap update, conflict detection, retry, idempotency, and starvation risk. |
| 63 | What is two-phase locking? | Growing/shrinking phases, serializability, lock duration, deadlock risk, and performance cost. |
| 64 | What is a row lock and when is it acquired? | Update/delete/select-for-update, lock modes, wait behavior, index dependency, and transaction duration. |
| 65 | What are table locks and schema locks? | DDL, bulk operations, lock compatibility, metadata locks, migration risk, and online DDL. |
| 66 | Explain shared, exclusive, intent, update, and range locks. | Compatibility matrix, hierarchy, read/write coordination, deadlock avoidance, and predicate protection. |
| 67 | What are gap locks and next-key locks? | Range protection, phantom prevention, index ranges, MySQL/InnoDB behavior, and surprising blocking. |
| 68 | What is predicate locking? | Locking logical query predicates, phantom prevention, serializable isolation, and implementation alternatives. |
| 69 | What is a database latch and how is it different from a lock? | Internal memory structure protection vs transaction isolation, duration, visibility, and contention symptoms. |
| 70 | How do deadlocks happen in databases? | Cyclic waits, inconsistent lock ordering, range locks, foreign keys, detection, victim rollback, and retry. |
| 71 | How do you prevent or reduce database deadlocks? | Deterministic ordering, short transactions, proper indexes, smaller batches, timeout/retry, and monitoring. |
| 72 | What is lock escalation? | Many fine-grained locks becoming coarse lock, memory pressure, blocking impact, and vendor behavior. |
| 73 | What is `SELECT FOR UPDATE` and when should it be used? | Pessimistic row locking, transaction scope, skip locked/nowait variants, contention, and timeout handling. |
| 74 | How do `NOWAIT` and `SKIP LOCKED` change concurrency behavior? | Immediate failure, queue workers, fairness, starvation, duplicate prevention, and retry/backoff. |
| 75 | How do you debug lock contention in production? | Lock wait views, blocked sessions, query text, transaction age, indexes, deadlock logs, and mitigation. |

## 6. Booking, Reservation, Inventory, and Distributed Scheduling Correctness

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 76 | How do you prevent double booking of a seat, room, or appointment? | Unique constraint or exclusion constraint, transaction, lock strategy, hold expiry, idempotency, and payment timeout. |
| 77 | Design a movie ticket seat-locking workflow. | Seat state machine, hold TTL, payment window, atomic transition, cleanup job, fairness, and oversell prevention. |
| 78 | Design hotel room availability under high concurrency. | Inventory buckets, date ranges, overbooking policy, transactional holds, cancellation, and reconciliation. |
| 79 | Design airline seat and fare-class inventory. | Seat map vs fare bucket, global distribution, holds, waitlists, pricing, consistency, and latency trade-offs. |
| 80 | How do you design inventory reservation for e-commerce checkout? | Available/reserved/sold counters, reservations table, expiry, idempotent checkout, compensation, and reconciliation. |
| 81 | How do you avoid overselling when inventory is sharded? | Single-writer shard, atomic conditional updates, reservation ledger, escrow allocation, and reconciliation. |
| 82 | What is the escrow technique for distributed inventory? | Pre-allocated capacity per shard/region, local commits, rebalancing, bounded oversell risk, and audit. |
| 83 | How do you design a distributed scheduler that must not run a job twice? | Lease table, fencing token, heartbeat, idempotent job, lock expiry, failover, and execution history. |
| 84 | Why are distributed locks dangerous for scheduling? | Pauses, partitions, expired leases, stale holders, clock drift, no fencing, and duplicate side effects. |
| 85 | What is a fencing token and how does it protect shared resources? | Monotonic token, resource rejects stale writers, lease holder safety, storage enforcement, and examples. |
| 86 | How would you implement appointment booking across multiple regions? | Region ownership, conflict domain, globally unique holds, quorum or home-region writes, latency, and failover. |
| 87 | How do you design waitlists and queues for scarce inventory? | Ordered queue, fairness, expiration, notification, idempotent accept, capacity release, and abuse controls. |
| 88 | How do you handle payment success after reservation expiry? | State machine, idempotent payment callback, refund/void, late event handling, and customer communication. |
| 89 | How do you test double-booking prevention? | Concurrent stress tests, isolation-level tests, chaos around expiry, unique constraint checks, and invariant queries. |
| 90 | What database design patterns make high-contention workflows reliable? | Atomic constraints, short transactions, versioning, queues, single writer, idempotency, and reconciliation. |

## 7. Indexing, Query Planning, and Performance Tuning

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 91 | What makes a good database index? | Access pattern, selectivity, cardinality, ordering, covering ability, write cost, and maintenance. |
| 92 | How does a B-tree or B+tree index work? | Balanced tree, root/internal/leaf pages, point lookup, range scan, page splits, and locality. |
| 93 | What is a composite index and why does column order matter? | Left-prefix rule, equality/range/sort ordering, selectivity, covering, and query shape. |
| 94 | What is a covering index? | Query served from index, included columns, reduced heap lookup, storage/write cost, and stale assumptions. |
| 95 | What is a partial or filtered index? | Index subset, predicate matching, smaller size, uniqueness among active rows, and planner requirements. |
| 96 | What is an expression or function-based index? | Indexed computed value, case-insensitive search, deterministic expression, query match, and update cost. |
| 97 | Compare hash, B-tree, bitmap, inverted, BRIN, GIN, GiST, and vector indexes. | Workload fit, equality/range/text/spatial/ANN, storage, update cost, and engine support. |
| 98 | How do indexes hurt write-heavy systems? | Extra writes, page splits, WAL volume, lock contention, memory pressure, replication lag, and bloat. |
| 99 | How do you read an execution plan? | Scan type, join algorithm, estimated vs actual rows, cost, buffers, sort/spill, filters, and timing. |
| 100 | Compare nested loop, hash join, and merge join. | Input size, indexes, sort order, memory, spills, skew, and planner choice. |
| 101 | Why do stale statistics cause slow queries? | Wrong cardinality estimates, bad join order, bad index choice, analyze schedule, and histograms. |
| 102 | How do you tune a slow query systematically? | Reproduce, plan, row estimates, indexes, predicates, joins, sort/spill, locks, cache, and regression test. |
| 103 | What is an index-only scan and when is it not really index-only? | Visibility map/MVCC checks, included columns, heap fetches, vacuum state, and engine specifics. |
| 104 | How do pagination queries become slow? | Large offsets, unstable sort, index scan depth, keyset pagination, cursor tokens, and consistency. |
| 105 | How do you decide whether to add, change, or remove an index? | Query frequency, latency gain, write penalty, storage, duplicate indexes, usage stats, and rollout safety. |

## 8. Partitioning, Sharding, Hot Keys, and Rebalancing

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 106 | Compare partitioning and sharding. | Single logical DB/table partitioning vs horizontal distribution across nodes, routing, operations, and scaling. |
| 107 | Why do databases partition tables? | Pruning, maintenance, retention, parallelism, manageability, hot/cold data, and local indexes. |
| 108 | Compare range, hash, list, and composite partitioning. | Query fit, skew risk, pruning, rebalancing, time-series retention, and operational complexity. |
| 109 | How do you choose a shard key? | Access pattern, cardinality, distribution, locality, tenant isolation, growth, and resharding cost. |
| 110 | What is a hot partition or hot shard? | Skewed key, celebrity tenant, monotonic writes, overloaded node, latency, throttling, and mitigation. |
| 111 | How do you mitigate hot keys? | Salting, sub-shards, write aggregation, caching, queue buffering, adaptive split, and tenant isolation. |
| 112 | What is consistent hashing and where is it useful? | Ring/hash space, virtual nodes, minimal movement, caches/KV stores, uneven load, and replication. |
| 113 | What are virtual nodes in consistent hashing? | Smoother distribution, faster rebalance, operational flexibility, metadata overhead, and placement control. |
| 114 | How do you rebalance shards safely? | Dual read/write, backfill, cutover, verification, throttling, rollback, and client routing updates. |
| 115 | How do you design cross-shard queries? | Avoid if possible, scatter-gather, secondary indexes, fanout limits, precomputed views, and latency budgets. |
| 116 | How do you design cross-shard transactions? | 2PC, sagas, escrow, single-writer routing, idempotency, compensation, and when to avoid. |
| 117 | How do you support global secondary indexes in a sharded database? | Async index table, fanout, consistency lag, unique constraints, backfill, and repair. |
| 118 | How do tenant-based shards differ from hash-based shards? | Isolation, noisy neighbors, compliance, uneven tenant size, migration, and operational routing. |
| 119 | How do you shard a social graph or feed system? | User-based partitioning, celebrity problem, fanout models, edge storage, and read/write trade-offs. |
| 120 | What are the hardest parts of resharding a live system? | Routing correctness, dual writes, lag, backfill consistency, lock-free cutover, validation, and rollback. |

## 9. Replication, HA, Backup, Restore, and Disaster Recovery

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 121 | Why do databases replicate data? | Availability, read scale, durability, locality, disaster recovery, migration, and analytics offload. |
| 122 | Compare synchronous and asynchronous replication. | Commit latency, data loss risk, failover safety, replica lag, throughput, and geography. |
| 123 | What is semi-synchronous replication? | Acknowledgement from at least one replica, reduced data loss, latency impact, and failure behavior. |
| 124 | Explain leader-follower replication. | Single write leader, WAL/binlog shipping, read replicas, failover, split brain, and lag. |
| 125 | Explain multi-leader replication. | Local writes, conflicts, convergence, clock/order issues, use cases, and operational risk. |
| 126 | Explain leaderless replication. | Quorums, hinted handoff, read repair, anti-entropy, conflict resolution, and tunable consistency. |
| 127 | What is replica lag and why does it matter? | Stale reads, read-your-writes failure, failover data loss, monitoring, and routing. |
| 128 | How do you provide read-your-writes with replicas? | Read from leader, session stickiness, LSN/token tracking, causal reads, and bounded staleness. |
| 129 | How do failovers go wrong? | Split brain, stale replica promotion, lost writes, DNS/client caching, connection pools, and runbook gaps. |
| 130 | What is point-in-time recovery? | Base backup, WAL/binlog archive, restore timestamp, validation, RPO, and operational drills. |
| 131 | How do snapshots differ from logical backups? | Physical copy vs SQL/export, speed, portability, consistency, restore granularity, and corruption risk. |
| 132 | What should a database backup strategy include? | Full/incremental, WAL archive, encryption, offsite copy, retention, restore tests, and access controls. |
| 133 | How do you design disaster recovery for a database? | RTO/RPO, region strategy, backup restore, replica promotion, DNS, app compatibility, and game days. |
| 134 | How do you detect and handle data corruption? | Checksums, scrubbing, replica comparison, backups, repair tools, blast-radius limits, and audit. |
| 135 | What makes database HA different from stateless service HA? | Stateful failover, data loss risk, consistency, storage, client reconnection, and recovery validation. |

## 10. Distributed Databases, CAP, PACELC, Quorums, and Consensus

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 136 | Explain CAP theorem correctly. | Network partitions, consistency vs availability under partition, partition tolerance necessity, operation-specific nuance. |
| 137 | What is PACELC and why is it more useful than CAP alone? | Partition trade-off plus else latency/consistency trade-off, normal-operation design, and examples. |
| 138 | What does consistency mean in distributed databases? | Linearizability, sequential, causal, read-your-writes, eventual, bounded staleness, and monotonic reads. |
| 139 | What is linearizability? | Single real-time order, latest successful write visibility, latency cost, quorum/consensus, and use cases. |
| 140 | What is eventual consistency? | Convergence without immediate visibility, conflict handling, anti-entropy, user impact, and bounded risk. |
| 141 | What is causal consistency? | Happens-before preservation, session dependencies, vector/logical clocks, stronger than eventual, weaker than linearizable. |
| 142 | How do quorum reads and writes work? | N/R/W, R+W>N, stale reads, latency, failure tolerance, and consistency-level selection. |
| 143 | What is tunable consistency? | Per-operation consistency levels, latency/correctness trade-off, quorum math, and operational pitfalls. |
| 144 | What are vector clocks and version vectors used for? | Concurrent update detection, causal ordering, conflict resolution, metadata growth, and client reconciliation. |
| 145 | What is read repair? | Repair during reads, stale replica detection, latency impact, consistency improvement, and anti-entropy complement. |
| 146 | What are Merkle trees used for in databases? | Efficient replica comparison, anti-entropy repair, range hashing, and large dataset synchronization. |
| 147 | What is hinted handoff? | Temporary write storage for unavailable replica, availability improvement, staleness risk, and replay behavior. |
| 148 | Why is two-phase commit blocking? | Coordinator dependency, prepared participants, uncertain outcome, recovery logs, and alternatives. |
| 149 | How does consensus replication differ from async replication? | Majority agreement, leader terms, log order, commit safety, failover correctness, and latency cost. |
| 150 | When should an architect choose a distributed database? | Scale/geography/availability need, consistency requirement, operational maturity, latency budget, and simpler alternatives. |

## 11. Relational Product Deep Dives

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 151 | What PostgreSQL internals should every architect know? | MVCC, WAL, vacuum, indexes, planner stats, isolation, replication, partitioning, and connection pooling. |
| 152 | Why does PostgreSQL vacuum matter? | Dead tuple cleanup, bloat, transaction ID wraparound, visibility map, index-only scans, and long transactions. |
| 153 | How do you diagnose PostgreSQL table or index bloat? | Dead tuples, `pg_stat` views, autovacuum lag, relation size, reindex/vacuum strategy, and risk. |
| 154 | How do PostgreSQL physical and logical replication differ? | WAL byte stream vs decoded changes, failover/read replicas vs CDC/upgrades, slots, and lag. |
| 155 | What MySQL/InnoDB internals should every architect know? | Clustered PK, secondary indexes, buffer pool, redo/undo, MVCC, gap locks, replication, and online DDL. |
| 156 | Why does primary-key choice matter in InnoDB? | Clustered storage, secondary index size, page locality, random inserts, fragmentation, and UUID trade-offs. |
| 157 | How do MySQL gap locks affect application behavior? | Range locking, phantom prevention, blocked inserts, isolation-specific behavior, and index design. |
| 158 | What SQL Server concepts are common in senior interviews? | Clustered/nonclustered indexes, row-versioning isolation, TempDB, Query Store, deadlocks, and columnstore. |
| 159 | What is parameter sniffing and why can it hurt SQL Server? | Plan reuse, skewed parameter values, bad estimates, recompilation/options, and Query Store mitigation. |
| 160 | What Oracle concepts matter for architects? | Optimizer, partitioning, RAC, Data Guard, flashback, PL/SQL trade-offs, backup, and licensing. |
| 161 | Compare PostgreSQL and MySQL for backend OLTP systems. | SQL features, JSON, replication, isolation, indexing, operational tooling, ecosystem, and team experience. |
| 162 | Compare relational DB read replicas and distributed SQL. | Simpler read scale vs horizontal writes, consistency, failover, latency, operations, and cost. |
| 163 | What is distributed SQL? | SQL plus horizontal scale, consensus replication, range/tablet sharding, distributed transactions, and latency trade-offs. |
| 164 | How do Spanner-like systems use time or clocks? | TrueTime/clock uncertainty, commit timestamps, external consistency, waiting, and geo-latency. |
| 165 | When should you not migrate from a single relational DB to distributed SQL? | Single-region fit, low write scale, team maturity, latency sensitivity, cost, and migration complexity. |

## 12. NoSQL Data Models and Design Trade-Offs

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 166 | What does NoSQL mean in practical architecture? | Non-relational models, scale/flexibility goals, relaxed joins/transactions, operational differences, and fit by workload. |
| 167 | When is a document database a strong choice? | Aggregate documents, flexible schema, bounded nesting, indexable fields, product iteration, and transactional limits. |
| 168 | How do you model data in MongoDB-style document stores? | Embed vs reference, document size, indexes, shard key, schema validation, and update patterns. |
| 169 | What are common document database anti-patterns? | Unbounded arrays, deep nesting, cross-document joins, low-selectivity indexes, large hot documents, and schema drift. |
| 170 | When is a wide-column database a strong choice? | Massive writes, predictable queries, partition/clustering key design, denormalization, and horizontal scale. |
| 171 | How do wide-column databases differ from relational tables? | Sparse rows, partitions, clustering order, query restrictions, no arbitrary joins, and duplicate tables. |
| 172 | When is a key-value database the right abstraction? | Access by key, low latency, session/profile/cache/counter workloads, TTL, and limited query needs. |
| 173 | What are key-value database design risks? | Hot keys, large values, missing secondary access, transactions, durability, and schema hidden in values. |
| 174 | When should you choose a graph database? | Relationship traversal, variable-depth queries, fraud, identity, recommendations, supernode mitigation, and graph indexes. |
| 175 | When should you avoid a graph database? | Simple key lookups, large analytical scans, high write fanout, limited team expertise, and operational maturity. |
| 176 | What does schema-less really mean? | No rigid DB schema does not mean no schema; validation, application contracts, migrations, and data quality. |
| 177 | How do NoSQL databases handle transactions today? | Single-item atomicity, conditional writes, limited multi-document transactions, distributed costs, and modeling around them. |
| 178 | How do you design secondary access in NoSQL? | GSIs/materialized views, duplicate tables, async updates, consistency lag, backfill, and repair. |
| 179 | How do you decide between denormalization and joins? | Query latency, write amplification, correctness, consistency lag, cardinality, and operational simplicity. |
| 180 | What makes NoSQL answers weak in interviews? | Saying "NoSQL scales" without access patterns, consistency, partition keys, failure modes, and operations. |

## 13. ScyllaDB, Cassandra, HBase, DynamoDB, and Aerospike

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 181 | How do Cassandra and ScyllaDB model data? | Query-first tables, partition key, clustering key, denormalization, consistency levels, and compaction. |
| 182 | What is ScyllaDB's shard-per-core architecture concept? | CPU-core-local shards, reduced locking, predictable latency, partition-to-shard routing, and operational implications. |
| 183 | How do you choose a partition key in Cassandra or ScyllaDB? | Even distribution, bounded partition size, query pattern, cardinality, hot key avoidance, and repair impact. |
| 184 | What are clustering keys used for in Cassandra or ScyllaDB? | On-partition ordering, range queries within partition, time-series patterns, and query restrictions. |
| 185 | How do consistency levels work in Cassandra or ScyllaDB? | ONE/QUORUM/ALL/local variants, RF, latency, availability, stale reads, and per-query trade-offs. |
| 186 | Why are tombstones a major Cassandra or ScyllaDB interview topic? | Deletes/TTL, read amplification, compaction, large partitions, timeout risk, and modeling avoidance. |
| 187 | How do Cassandra repair and anti-entropy work conceptually? | Replica divergence, Merkle comparison, repair scheduling, incremental/full repair, and operational load. |
| 188 | How does HBase differ from Cassandra or ScyllaDB? | HDFS/storage separation, RegionServers, strong row consistency, range scans, region splitting, and ecosystem fit. |
| 189 | How do you model DynamoDB single-table design? | Access patterns, PK/SK overloading, item collections, GSIs, LSIs, adjacency, and query constraints. |
| 190 | How do DynamoDB conditional writes solve concurrency problems? | Atomic condition expression, version checks, uniqueness patterns, retries, and idempotency. |
| 191 | What are DynamoDB hot partitions and adaptive capacity? | Partition-key skew, throughput limits, burst/adaptive behavior, salting, write sharding, and monitoring. |
| 192 | How do DynamoDB global tables affect consistency? | Multi-region replication, last-writer-wins/conflicts, latency, failover, and idempotent design. |
| 193 | When is Aerospike a strong choice? | Ultra-low-latency KV, ad tech/fraud/profile/session workloads, memory/NVMe architecture, TTL, and large scale. |
| 194 | Explain Aerospike namespace, set, record, and bin. | Data organization, primary index, secondary index, TTL, storage policy, and modeling constraints. |
| 195 | Compare Aerospike strong consistency and availability-oriented modes. | CP vs AP behavior, replication, partition handling, latency, failover, and workload fit. |

## 14. Caching Databases, Redis, Memcached, and Cache Correctness

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 196 | What is the difference between a cache and a primary database? | Source of truth, durability, eviction, consistency, recovery, backup, and data-loss tolerance. |
| 197 | When should Redis be used as a database-like system? | Ephemeral state, sessions, counters, leaderboards, queues/streams with caveats, TTL, and persistence trade-offs. |
| 198 | Compare Redis and Memcached. | Data structures vs simple KV, persistence, clustering, memory overhead, operations, and use cases. |
| 199 | Explain cache-aside. | App read miss/load/set, invalidation, stale data, stampede risk, TTL, and write path behavior. |
| 200 | Compare read-through, write-through, write-behind, and refresh-ahead caching. | Latency, consistency, failure coupling, data loss risk, operational complexity, and fit. |
| 201 | What is cache stampede and how do you prevent it? | Concurrent misses, single-flight, locks, stale-while-revalidate, jittered TTLs, warming, and backpressure. |
| 202 | What is cache penetration and cache breakdown? | Missing-key abuse, hot-key expiry, bloom filters, null caching, TTL jitter, and admission control. |
| 203 | How do you handle hot keys in Redis? | Local cache, replication, key splitting, request coalescing, rate limits, data modeling, and observability. |
| 204 | How do Redis eviction policies affect correctness? | LRU/LFU/random/TTL variants, allkeys vs volatile, memory sizing, data loss, and source-of-truth safety. |
| 205 | Compare Redis RDB and AOF persistence. | Snapshot vs append log, recovery point, write latency, rewrite, fsync policy, and durability expectations. |
| 206 | How does Redis Cluster shard data? | Hash slots, key tags, resharding, multi-key restrictions, replicas, failover, and client routing. |
| 207 | Why are Redis distributed locks subtle? | Expiry, pauses, partitions, stale owners, clock assumptions, fencing tokens, and safer alternatives. |
| 208 | When would you use Redis Streams? | Lightweight event stream, consumer groups, pending entries, ordering, retention, and Kafka comparison. |
| 209 | How do you cache permissioned or personalized data safely? | Cache key includes identity/scope, invalidation, privacy, tenant isolation, and stale authorization risk. |
| 210 | What should be monitored for a caching layer? | Hit ratio, latency, memory, evictions, hot keys, replication lag, command mix, and stampede indicators. |

## 15. Search, Vector, and Graph Databases

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 211 | Why is a search engine not usually the primary database? | Eventual indexing, refresh lag, weak transactions, source-of-truth risk, rebuilds, and consistency. |
| 212 | How does an inverted index work? | Term dictionary, postings lists, analyzers, tokenization, scoring, filters, and segment merges. |
| 213 | What are analyzers in Elasticsearch/OpenSearch/Solr? | Tokenizer, filters, stemming, synonyms, case normalization, language handling, and relevance impact. |
| 214 | How do search shards and replicas affect performance? | Query fanout, shard sizing, replica reads, merge cost, hot shards, and cluster state. |
| 215 | What is refresh interval in Elasticsearch-like systems? | Near-real-time visibility, indexing throughput, query freshness, segment creation, and write cost. |
| 216 | How do you design product search? | Catalog source, indexing pipeline, facets, filters, relevance, availability, personalization, and stale inventory. |
| 217 | How do you keep a search index in sync with the source database? | CDC/outbox, retries, idempotent indexing, backfill, versioning, lag metrics, and rebuild. |
| 218 | What is vector search? | Embeddings, similarity metrics, ANN indexes, recall/latency trade-off, metadata filtering, and re-ranking. |
| 219 | Compare HNSW, IVF, and brute-force vector search at a high level. | Graph vs centroid partitioning vs exact scan, recall, memory, latency, build cost, and updates. |
| 220 | How do you design vector search for RAG? | Chunking, embeddings, metadata ACLs, ANN index, re-rank, freshness, evaluation, and deletion. |
| 221 | What are common vector database failure modes? | Stale embeddings, poor chunking, missing filters, low recall, high cardinality metadata, and reindex cost. |
| 222 | How does graph traversal differ from relational joins? | Edge-first traversal, variable depth, path queries, index-backed starting points, and supernode risk. |
| 223 | What is a supernode and how do you mitigate it? | Very high-degree node, traversal explosion, edge partitioning, summarization, limits, and model redesign. |
| 224 | When should graph data be projected into another store? | Analytics, recommendations, search, low-latency serving, materialized paths, and operational separation. |
| 225 | How do you choose between search, vector, graph, and relational storage for discovery? | Query semantics, ranking, freshness, joins/traversal, scale, correctness, and source-of-truth design. |

## 16. Time-Series, OLAP, Warehouse, Lakehouse, and HTAP

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 226 | What makes time-series databases different from generic databases? | Time-indexed writes, retention, downsampling, compression, cardinality, range scans, and append-heavy patterns. |
| 227 | How do you model time-series metrics? | Measurement, timestamp, tags, fields, cardinality control, retention, rollups, and query windows. |
| 228 | Why is high cardinality dangerous in time-series systems? | Index explosion, memory pressure, slow queries, cost, unbounded labels, and observability design. |
| 229 | Compare TimescaleDB, InfluxDB, Prometheus, M3DB, and QuestDB at a high level. | SQL vs metrics, pull/push, retention, compression, clustering, ecosystem, and workload fit. |
| 230 | How do retention and downsampling policies work? | Raw vs aggregate data, TTL, continuous aggregates, rollups, query accuracy, and cost. |
| 231 | What is a columnar database and why is it fast for analytics? | Column storage, compression, vectorized scans, late materialization, pruning, and aggregation efficiency. |
| 232 | Compare ClickHouse, Pinot, and Druid. | Real-time OLAP, segments/parts, ingestion, indexing, query serving, upserts, and operations. |
| 233 | What is a data warehouse? | Integrated analytical store, SQL BI, dimensional modeling, governance, workload management, and cost. |
| 234 | Compare Snowflake, BigQuery, and Redshift conceptually. | Managed warehouse, storage/compute separation, slots/warehouses/clusters, scaling, cost, and ecosystem. |
| 235 | What is a lakehouse? | Object storage plus table format, ACID metadata, open files, compute separation, governance, and compaction. |
| 236 | Compare Iceberg, Delta Lake, and Hudi at a high level. | Table metadata, snapshots, schema evolution, deletes/upserts, streaming, compaction, and engine support. |
| 237 | What is HTAP and when is it useful? | Hybrid transactional/analytical processing, fresh analytics, workload isolation, row/column layout, and trade-offs. |
| 238 | Why should OLTP and OLAP workloads often be separated? | Contention, different access patterns, isolation, cost, query duration, and operational risk. |
| 239 | How do you design a real-time analytics dashboard? | Ingestion, stream processing, OLAP store, pre-aggregation, freshness SLO, late events, and backfills. |
| 240 | How do you control analytical query cost? | Partition pruning, clustering/sort keys, materialized views, workload limits, sampling, and governance. |

## 17. Multi-Region, Geo-Distribution, Tenancy, Security, and Compliance

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 241 | How do you design data placement for a global product? | User locality, residency, latency, replication, failover, legal constraints, and operational ownership. |
| 242 | Compare active-passive, active-active, and follow-the-sun database architectures. | Write routing, failover, conflicts, latency, operational complexity, and recovery. |
| 243 | How do you handle conflict resolution in multi-region systems? | Last-writer-wins risks, version vectors, app-level merge, CRDTs, user workflow, and audit. |
| 244 | What is bounded staleness and when is it acceptable? | Staleness window, user expectations, replica lag, latency improvement, and correctness limits. |
| 245 | How do you design region failover without corrupting data? | Promotion rules, fencing old primary, DNS/routing, replication state, write freeze, and reconciliation. |
| 246 | How do you design multi-tenant data isolation? | Tenant ID, row-level security, schema/database isolation, encryption, quotas, backup/restore, and audit. |
| 247 | Compare shared DB, shared schema, separate schema, and separate database tenancy. | Cost, isolation, compliance, noisy neighbors, operations, migrations, and tenant tiering. |
| 248 | How do row-level security policies affect application design? | Defense in depth, session context, policy testing, performance, admin bypass, and migration. |
| 249 | How do you encrypt database data properly? | TLS, at-rest encryption, KMS, envelope encryption, column encryption, key rotation, and access control. |
| 250 | How do you manage PII in database design? | Classification, minimization, tokenization, masking, access logs, retention, deletion, and residency. |
| 251 | How do you implement right-to-erasure in distributed data systems? | Data inventory, tombstones, async deletion, backups, search/cache/vector copies, audit, and legal holds. |
| 252 | How do you design database access control for services and humans? | Least privilege, separate roles, break-glass, audit, secret rotation, read-only access, and approvals. |
| 253 | How do you handle tenant-level backup and restore? | Isolation model, point-in-time restore, per-tenant export/import, consistency, privacy, and blast radius. |
| 254 | How do you design for data residency and sovereignty? | Region pinning, routing, replication constraints, support access, encryption keys, and evidence. |
| 255 | What compliance questions should architects ask about databases? | Retention, auditability, encryption, access, residency, deletion, backup, lineage, and breach response. |

## 18. Schema Migration, CDC, Events, and Data Evolution

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 256 | How do you perform zero-downtime schema migrations? | Expand-contract, backward compatibility, deploy order, backfill, dual reads/writes, validation, and rollback. |
| 257 | What is the expand-contract pattern? | Add nullable/new structures, dual-write/backfill, switch reads, enforce constraints, remove old fields safely. |
| 258 | How do you add a non-null column to a huge table safely? | Nullable add, default/backfill in chunks, constraint validation, lock avoidance, and deploy sequencing. |
| 259 | How do you backfill large datasets without hurting production? | Chunking, throttling, ordering, idempotency, checkpoints, metrics, retries, and off-peak controls. |
| 260 | How do online DDL tools reduce migration risk? | Shadow table, triggers/binlog copy, cutover locks, validation, rollback limits, and operational caveats. |
| 261 | How do you change a primary key or shard key? | New key column, dual writes, backfill, secondary indexes, routing migration, cutover, and rollback. |
| 262 | How do you evolve JSON/document schemas safely? | Version fields, tolerant readers, validators, migration jobs, defaults, and mixed-version app support. |
| 263 | What is CDC and when should it be used? | Log-based change capture, replication, search indexing, analytics, outbox alternative, ordering, and lag. |
| 264 | Compare outbox pattern and CDC. | App-owned event table vs log capture, atomicity, ordering, schema contracts, tooling, and operations. |
| 265 | How do you design the outbox pattern? | Same DB transaction, relay, idempotent publish, status/attempts, ordering, cleanup, and observability. |
| 266 | How do you handle duplicate or out-of-order database change events? | Idempotent consumers, version checks, monotonic sequence, compaction, replay, and dead-letter handling. |
| 267 | How do you rebuild a derived read model or search index? | Snapshot plus CDC tail, versioned writes, backfill throttling, compare counts, switch alias, and rollback. |
| 268 | How do you manage schema evolution across microservices? | Ownership, compatibility, contract tests, events, consumer-driven changes, and deprecation windows. |
| 269 | How do you retire a table or column safely? | Usage detection, read removal, write removal, dark validation, backup, delayed drop, and rollback window. |
| 270 | What are the biggest migration mistakes in database systems? | Blocking DDL, no rollback, unbounded backfill, incompatible app versions, missing validation, and ignored replicas. |

## 19. Operations, Observability, Maintenance, and Cost

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 271 | What database metrics should every production system monitor? | Latency, QPS, errors, saturation, locks, deadlocks, cache hit, replication lag, storage, and connections. |
| 272 | How do you diagnose a sudden database latency spike? | Workload change, locks, slow queries, I/O, CPU, memory, plan regression, replication, and dependency issues. |
| 273 | How do connection pools fail in production? | Pool exhaustion, too many DB connections, leaked connections, long transactions, wait queues, and timeouts. |
| 274 | How do you size a database connection pool? | DB concurrency limit, workload latency, app instances, CPU/I/O capacity, queueing, and backpressure. |
| 275 | What is a connection storm and how do you prevent it? | Restart fanout, pool warmup, max connections, jitter, proxy pooling, circuit breakers, and autoscaling coordination. |
| 276 | How do you detect a query plan regression? | Baseline plans, query store/statements, latency change, stats drift, parameter skew, and rollback. |
| 277 | How do you handle database capacity planning? | QPS, read/write mix, storage growth, index growth, retention, replicas, headroom, and load tests. |
| 278 | What is database saturation? | CPU, I/O, memory, locks, connections, WAL, compaction, replication, and queue growth. |
| 279 | How do you maintain large indexes and partitions? | Reindex, vacuum/analyze, compact, partition detach/drop, schedule windows, and monitoring. |
| 280 | How do you handle large deletes safely? | Batched deletes, partition drops, tombstone control, vacuum/compaction, replica lag, and archival. |
| 281 | How do you design database alerts that are useful? | SLO-based latency/errors, saturation trends, replication lag, storage forecast, lock waits, and paging policy. |
| 282 | How do you run database incident response? | Triage, freeze risky writes, preserve evidence, mitigate, failover if needed, communicate, and postmortem. |
| 283 | How do you test database failover? | Planned drills, replica promotion, client reconnect, data validation, RTO/RPO measurement, and rollback. |
| 284 | How do you estimate database cost? | Compute, storage, indexes, replicas, backups, snapshots, egress, queries, licenses, and operational labor. |
| 285 | What database operational maturity signals matter in architecture review? | Backups tested, migrations safe, dashboards, runbooks, load tests, DR drills, ownership, and capacity model. |

## 20. Architect-Level Database Selection and Synthesis

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 286 | How do you choose the right database for a new service? | Workload, consistency, access patterns, scale, latency, operations, team skill, cost, and migration path. |
| 287 | When should you start with PostgreSQL instead of a specialized database? | Relational fit, moderate scale, query flexibility, transactions, maturity, simplicity, and future escape hatches. |
| 288 | When should you choose multiple databases for one product? | Different workloads, source-of-truth clarity, derived stores, sync pipeline, consistency lag, and operational cost. |
| 289 | How do you avoid database sprawl? | Clear ownership, platform standards, approved patterns, operational readiness, data contracts, and retirement plan. |
| 290 | Design a database architecture for a high-scale social feed. | Graph storage, fanout, feed cache, ranking store, hot users, consistency, and rebuilds. |
| 291 | Design database storage for a payments platform. | Ledger, idempotency, transactions, audit, reconciliation, isolation, encryption, and disaster recovery. |
| 292 | Design database storage for a ride-hailing marketplace. | Geo index, driver state, trip state machine, matching latency, event log, and regional partitioning. |
| 293 | Design database storage for a SaaS multi-tenant platform. | Tenant isolation, shared vs dedicated DB, quotas, migrations, analytics, backup/restore, and compliance. |
| 294 | Design database storage for IoT telemetry at massive scale. | Ingestion buffer, time-series store, retention, downsampling, hot devices, compression, and late data. |
| 295 | Design database storage for an e-commerce catalog and inventory system. | Catalog search, product DB, inventory reservations, pricing, cache, consistency, and reconciliation. |
| 296 | Design database storage for a real-time fraud detection platform. | Feature store, event stream, low-latency KV, graph/search, model feedback, and audit trail. |
| 297 | How do you explain a database trade-off to executives? | Business risk, cost, timeline, failure mode, migration path, operational burden, and measurable outcome. |
| 298 | How do you evaluate a vendor database claim? | Benchmark relevance, workload match, failure tests, consistency guarantees, lock-in, ecosystem, and TCO. |
| 299 | How do you migrate from one database technology to another safely? | Dual writes, CDC, backfill, validation, shadow reads, phased cutover, rollback, and decommissioning. |
| 300 | What is your architect-level checklist before approving a database design? | Invariants, schema, indexes, transactions, scale, HA/DR, security, observability, migrations, cost, and ownership. |

## 21. Database Administration, Diagnostics, and Troubleshooting

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 301 | How do you inspect active database sessions and currently running queries? | Session views, query text, user/app/source, transaction age, wait state, blocking session, and safe termination policy. |
| 302 | How do you find blocking sessions and lock chains? | Lock tables/DMVs, blocked-by relationships, lock mode, object/row/page, wait duration, root blocker, and mitigation. |
| 303 | How do you check database locks in PostgreSQL, MySQL, SQL Server, or Oracle conceptually? | `pg_locks`/activity, InnoDB lock waits, DMVs/AWR/ASH, lock compatibility, blockers, and vendor-specific tooling. |
| 304 | How do you decide whether to kill a blocking database session? | Business impact, transaction age, rollback cost, lock scope, owner contact, safety runbook, and post-incident fix. |
| 305 | How do you diagnose deadlocks after they occur? | Deadlock graph/log, victim query, lock order, indexes, transaction scope, retry behavior, and permanent prevention. |
| 306 | How do you inspect and explain a query execution plan? | Scan type, join order, join algorithm, estimates vs actuals, buffers/I/O, sort/spill, filters, and timing. |
| 307 | What is the difference between estimated plan and actual plan? | Planner prediction vs runtime reality, row-count errors, parameter values, buffers, timing, and instrumentation overhead. |
| 308 | How do you detect a query plan regression in production? | Query IDs, normalized SQL, plan hash, baseline latency, stats changes, parameter skew, deployment correlation, and rollback. |
| 309 | How do wait events help diagnose database performance? | CPU vs I/O vs lock vs network vs WAL/log sync waits, top wait classes, session-level waits, and saturation signals. |
| 310 | How do you diagnose thread or worker contention in a database? | Worker pools, background workers, scheduler waits, runnable queues, latch/spin contention, CPU saturation, and query concurrency. |
| 311 | How do you connect application thread contention to database behavior? | App thread dumps, connection-pool waits, blocked JDBC calls, slow queries, DB wait events, and end-to-end tracing. |
| 312 | How do you troubleshoot connection pool exhaustion? | Active/idle/waiting counts, max connections, leak detection, long transactions, slow dependencies, timeout settings, and backpressure. |
| 313 | How do you inspect long-running transactions and why are they dangerous? | Transaction age, idle-in-transaction sessions, MVCC bloat, lock retention, vacuum blockage, replication lag, and cancellation. |
| 314 | How do you diagnose PostgreSQL replication slot problems? | Slot lag, retained WAL, inactive slots, restart LSN, disk growth, consumer health, safe slot removal, and monitoring. |
| 315 | What are replication slots and why can they fill disks? | WAL retention for consumers, physical/logical slots, lagging replicas/CDC, disk pressure, and operational guardrails. |
| 316 | How do you diagnose replication lag? | Replay/apply lag, network, disk I/O, long transactions, large batches, replica load, slot lag, and read-routing impact. |
| 317 | How do you check WAL, redo log, or binlog pressure? | Generation rate, archive lag, fsync latency, checkpoint behavior, replica consumption, disk growth, and retention settings. |
| 318 | How do you diagnose autovacuum, purge, or compaction falling behind? | Dead tuples, bloat, old snapshots, tombstones, compaction backlog, I/O throttling, and maintenance tuning. |
| 319 | How do you investigate table and index bloat in production? | Size growth, dead rows, free space, index scans, vacuum/reindex need, lock impact, and maintenance windows. |
| 320 | How do you check whether indexes are being used or are wasteful? | Index usage stats, query plans, duplicate indexes, write overhead, cache footprint, selectivity, and safe removal. |
| 321 | How do you diagnose high database CPU usage? | Top queries, execution plans, missing indexes, inefficient joins, sort/hash work, compilation/planning, and concurrency. |
| 322 | How do you diagnose high database I/O usage? | Buffer hit ratio, read/write latency, checkpoints, temp spills, sequential scans, compaction, and storage saturation. |
| 323 | How do you diagnose temp file or spill-to-disk problems? | Sort/hash/window operations, memory grants/work mem, query plans, temp space growth, concurrency, and query rewrite. |
| 324 | How do you troubleshoot slow commits? | WAL/log fsync, synchronous replication, group commit, disk latency, transaction size, checkpoints, and commit path metrics. |
| 325 | How do you inspect database configuration safely during an incident? | Current settings, reload vs restart, changed parameters, memory limits, connection limits, logging, and change audit. |
| 326 | How do you design useful slow-query logging? | Thresholds, sampling, bind parameters safely, query IDs, plans for outliers, PII controls, and log volume management. |
| 327 | How do you perform safe online maintenance as a DBA or architect? | Backups, lock analysis, throttling, canary, low-traffic windows, rollback, progress monitoring, and communication. |
| 328 | How do you validate replica health before failover or cutover? | LSN/binlog position, replication lag, read-only state, data checks, connection routing, promotion test, and rollback. |
| 329 | How do you build a database administration runbook? | Symptoms, dashboards, diagnostic queries, decision tree, escalation, safe commands, rollback, and postmortem checklist. |
| 330 | What administration topics should architects know even if they are not DBAs? | Locks, plans, waits, sessions, replication, backups, maintenance, capacity, security, and operational blast radius. |

## 22. CDC, Debezium, Kafka Connect, and Logical Replication

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 331 | What is change data capture and when should you use it? | Log-based capture, low-latency propagation, search/analytics/read models, audit, source-of-truth boundaries, and lag. |
| 332 | How does Debezium fit into a database architecture? | Source DB log, connector, Kafka Connect or embedded engine, topics, offsets, schema history, consumers, and derived stores. |
| 333 | What is the difference between a database replication slot and a Debezium/Kafka Connect offset? | Slot retains database log position, offset tracks connector progress, failure recovery, WAL/binlog retention, and data-loss risk. |
| 334 | Why does each Debezium PostgreSQL connector need its own replication slot? | Single slot consumer semantics, unique LSN tracking, avoiding consumer interference, WAL retention, and connector isolation. |
| 335 | What happens if a Debezium replication slot becomes inactive or lagging? | Retained WAL growth, disk pressure, stale downstream data, connector failure, alerting, restart, catch-up, or safe slot removal. |
| 336 | How do you monitor PostgreSQL replication slots used by Debezium? | Active flag, restart/confirmed flush LSN, retained WAL bytes, lag age, connector health, disk forecast, and consumer throughput. |
| 337 | How do publications, logical decoding plugins, and replication roles relate to Debezium PostgreSQL? | `REPLICATION` role, `pgoutput`, publication/table scope, permissions, schema filters, and operational validation. |
| 338 | What Debezium connector configuration must an architect understand? | Connector class, database connection, `topic.prefix`, `slot.name`, `publication.name`, `plugin.name`, include/exclude lists, snapshot mode, and offset storage. |
| 339 | How do Debezium snapshot modes affect production rollout? | Initial snapshot, schema-only, never/no-data modes, locking behavior, consistency, connector start point, and backfill strategy. |
| 340 | How do incremental snapshots work conceptually in Debezium? | Chunked table capture, signaling, low-lock backfill, watermarks, concurrent changes, stop/resume, and operational throttling. |
| 341 | What is a Debezium signaling channel and why is it useful? | Runtime commands, execute/stop incremental snapshots, Kafka or table signaling, connector name/topic prefix matching, and governance. |
| 342 | What is Debezium schema history and why is losing it dangerous? | DDL history, event decoding, connector restart, schema evolution, history topic/file durability, and recovery procedure. |
| 343 | How do Debezium offsets fail and how do you recover safely? | Offset storage corruption/loss, duplicate or skipped events, snapshot restart, slot LSN alignment, idempotent consumers, and backup. |
| 344 | How do Debezium heartbeats help with monitoring and WAL retention? | Low-traffic databases, LSN advancement, lag visibility, slot retention reduction, heartbeat topics, and alerting. |
| 345 | How are delete and tombstone events represented in Debezium pipelines? | Before/after payloads, delete event, tombstone for log compaction, consumer handling, cache invalidation, and topic cleanup. |
| 346 | What is the outbox pattern with Debezium? | Transactional outbox table, CDC relay, event routing SMT, aggregate/event IDs, ordering, cleanup, and consumer idempotency. |
| 347 | How do Debezium single message transforms affect architecture? | Routing, unwrapping envelopes, masking, filtering, topic naming, schema impact, operational debugging, and data contract risk. |
| 348 | How do you design topic naming, partitioning, and keys for Debezium events? | `topic.prefix`, table topics, primary-key event keys, ordering per key, partition skew, compaction, and consumer contracts. |
| 349 | What delivery guarantees should you assume from Debezium plus Kafka Connect? | At-least-once delivery, offset flush timing, duplicates after retry/restart, ordering scope, and idempotent consumers. |
| 350 | How do you troubleshoot a Debezium connector that is running but not producing events? | Source changes, connector status/tasks, slot activity, publication/table filters, permissions, offsets, logs, and Kafka topic ACLs. |
| 351 | How do you troubleshoot Debezium connector lag? | Source write rate, connector task health, Kafka producer latency, Connect worker resources, slot lag, large transactions, and consumer backpressure. |
| 352 | How do large transactions affect CDC pipelines? | Memory/buffering, delayed visibility, offset advancement, WAL/binlog retention, topic burst, and transaction-boundary semantics. |
| 353 | How do schema changes affect Debezium consumers? | DDL capture, schema registry compatibility, nullable/additive changes, breaking changes, consumer upgrades, and replay. |
| 354 | How do you secure a Debezium CDC pipeline? | Least-privilege replication user, network/TLS, secrets management, PII masking, topic ACLs, audit, and tenant boundaries. |
| 355 | How do you run multiple Debezium connectors against the same database safely? | Unique connector names, unique slots, publication scope, topic prefixes, resource limits, WAL retention, and ownership. |
| 356 | How do Debezium connectors differ across PostgreSQL, MySQL, SQL Server, Oracle, and MongoDB? | WAL/logical slots, binlog/GTID, SQL Server CDC, redo/log mining, change streams, permissions, and snapshot behavior. |
| 357 | How do you plan Debezium failover and disaster recovery? | Offset backup, schema history durability, slot recreation, replica compatibility, Kafka Connect rebalance, duplicate handling, and runbooks. |
| 358 | When should you avoid Debezium or log-based CDC? | Extreme write volume without capacity, unsupported source constraints, strict synchronous requirements, weak operations, and simpler alternatives. |
| 359 | How do you validate CDC correctness end to end? | Row-count checks, checksums, LSN/offset tracking, replay tests, synthetic writes, lag SLOs, duplicate detection, and reconciliation. |
| 360 | What makes a CDC/Debezium answer architect-grade? | Source DB impact, slots/log retention, offsets, snapshots, schema history, delivery guarantees, security, observability, and recovery. |

## Final Mastery Drill

For any database interview question, answer in this order:

1. State the workload and invariant.
2. Choose the data model and explain why.
3. Define the transaction or consistency boundary.
4. Pick indexes, partitioning, and replication strategy.
5. Explain failure modes and operational signals.
6. Compare at least two alternatives and explain the trade-off.
7. Close with migration, recovery, and cost implications.

Senior signal:

> Do not say "use Postgres", "use NoSQL", "add an index", "use Redis", or "use distributed locks" as a final answer. Explain the invariant, failure mode, and operational proof that the design remains correct under concurrency, partial failure, and growth.
