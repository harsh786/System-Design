# World-Class Pro-Level Software Architect Master Roadmap

**Purpose:** prepare aggressively for senior, staff, principal, architect, platform architect, and distributed-systems architect interviews.

**Coverage:** system design, low-level design, DSA, Java/JVM internals, languages and frameworks, database design and internals, database technologies, distributed systems, microservices, event-driven architecture, Kafka, Flink, lakehouse formats, object storage, software architecture, observability, SRE, deployment, Kubernetes, cloud, and security.

**Generated on:** 2026-05-21

---

## How to Use This Roadmap

This is not a casual reading list. Treat it like a professional architecture training plan.

1. **Study the concept.** Learn the theory, diagrams, and trade-offs.
2. **Build a working implementation.** Do not stop at notes.
3. **Write an architecture document.** Include requirements, APIs, data model, diagrams, failure modes, observability, deployment, and trade-offs.
4. **Practice interview speaking.** Explain out loud with structure.
5. **Run production-like tests.** Load test, chaos test, backup/restore test, failover test, canary deployment test.
6. **Create proof.** GitHub repo, diagrams, ADRs, runbooks, dashboards, and postmortems.

### Architect-Level Answer Formula

Use this formula in every serious design interview:

```text
Clarify scope -> Functional requirements -> Non-functional requirements -> Scale estimates -> API contracts -> Data model -> High-level design -> Deep dives -> Failure modes -> Security -> Observability -> Deployment -> Cost -> Trade-offs -> Migration plan
```

### The Core Architect Mindset

For every technology or design choice, be ready to answer:

- Why this and not the alternative?
- What can fail?
- How does it scale?
- How is it secured?
- How is it monitored?
- How is it deployed and rolled back?
- How is data backed up and recovered?
- How do teams evolve it without breaking clients?

---

# 1. Master Skill Matrix

| Area | Architect-Level Outcome |
| --- | --- |
| DSA | Solve patterns quickly and connect them to production systems such as caches, queues, schedulers, partitioning, search, and stream processing. |
| Low-Level Design | Convert requirements into maintainable, extensible, concurrent, testable code-level design. |
| System Design | Design scalable, reliable, secure, cost-aware distributed systems with clear trade-offs. |
| Java/JVM | Explain memory model, garbage collection, collections internals, locking, concurrent collections, thread pools, virtual threads, and production debugging. |
| Languages & Frameworks | Go deep in one backend stack and understand operational implications of runtime, framework, concurrency, memory, and instrumentation. |
| Database Design | Model data, choose storage engines, design indexes, tune queries, plan replication/sharding, handle backups, and reason about consistency. |
| Distributed Systems | Understand partitions, clocks, consensus, replication, quorums, leader election, failure detection, and eventual consistency. |
| Microservices | Design service boundaries, APIs, data ownership, resilience, sagas, outbox, CDC, observability, deployment, and testing. |
| Event-Driven | Design event contracts, topics, partitioning, ordering, retries, DLQs, schema evolution, replay, and stream processing. |
| Big Data | Build batch, streaming, lakehouse, OLAP, and governance architectures. |
| Software Architecture | Use architecture styles, DDD, C4, ADRs, quality attributes, and migration strategies. |
| Observability & SRE | Define SLIs/SLOs, instrument telemetry, debug incidents, write runbooks, and manage error budgets. |
| Kubernetes & Deployment | Deploy, scale, secure, observe, troubleshoot, and progressively release workloads on Kubernetes. |
| Security & Cloud | Design auth, network isolation, encryption, secrets, IAM, threat models, compliance, and cost governance. |

---

# 2. Aggressive 12-Month Roadmap

## Month 1: DSA, Complexity, and Core CS

### Learn

- Arrays, strings, hash maps, sets, prefix sums.
- Two pointers, sliding window, monotonic stack, heap.
- Trees, tries, graphs, BFS, DFS, topological sort, union-find.
- Dynamic programming, greedy algorithms, backtracking.
- Streaming algorithms: top-K, approximate counting, bloom filters.
- Concurrency basics: locks, queues, producer-consumer, race conditions.

### Build

- LRU cache.
- LFU cache.
- Token bucket rate limiter.
- Consistent hashing ring.
- Thread-safe bounded blocking queue.
- Top-K streaming service.

### Interview Output

- 100 DSA problems solved.
- 20 pattern notes.
- 5 production-style implementations.

## Month 2: Primary Language and Framework Mastery

Choose one primary backend stack and become extremely deep.

### Recommended Primary Stack

- Java + Spring Boot for enterprise/platform/backend architect interviews.
- Go for cloud-native/platform/distributed systems roles.
- Python for data-platform and ML-platform adjacent roles.
- TypeScript/Node.js for API/platform roles in JS-heavy organizations.

### Must Learn

- Runtime memory model.
- Concurrency model.
- Collections internals.
- Request lifecycle.
- Dependency injection.
- Security framework.
- ORM and transactions.
- Connection pooling.
- Testing.
- Resilience patterns.
- Observability instrumentation.

### Build

A production-grade service with REST, gRPC, PostgreSQL, Redis, Kafka, auth, tracing, metrics, logs, tests, Docker, and CI.

## Month 3: Low-Level Design and Object-Oriented Design

### Learn

- SOLID, DRY, KISS, YAGNI.
- Composition over inheritance.
- Design patterns.
- Domain-driven tactical patterns.
- State machines.
- Concurrency-safe design.
- API and SDK design.
- Testability and extensibility.

### Build

Design and code:

- Parking lot.
- Elevator.
- Booking system.
- Payment gateway.
- Logging framework.
- Rate limiter.
- Workflow engine.
- Cache library.

## Months 4-5: System Design Fundamentals and Deep Practice

### Learn

- Requirements, scale estimation, API design, data modeling.
- Load balancing, caching, CDN, rate limiting.
- SQL vs NoSQL decisions.
- Sharding, replication, consistency.
- Event-driven systems.
- Multi-region architecture.
- Security, observability, deployment, cost.

### Practice Designs

- URL shortener.
- Notification system.
- Chat system.
- News feed.
- Video platform.
- File storage.
- Payment ledger.
- Ride sharing.
- E-commerce.
- Real-time analytics.

## Month 6: Database Design and Internals

### Learn

- Data modeling: relational, document, key-value, wide-column, graph, time-series, OLAP.
- Storage: pages, extents, heap files, B-trees, LSM trees, columnar storage.
- Indexing: B-tree, hash, bitmap, inverted, GIN, GiST, BRIN, vector indexes.
- Transactions: ACID, MVCC, locks, isolation, deadlocks.
- Query optimization: statistics, cardinality, join algorithms, execution plans.
- Replication, sharding, backup, monitoring, recovery.

### Build

- Schema for commerce platform.
- Index experiments.
- Query plan analysis notebook.
- Backup and restore drill.
- Sharding design doc.

## Month 7: Distributed Systems

### Learn

- CAP, PACELC, consistency models.
- Quorums, leader election, consensus.
- Clocks, vector clocks, Lamport clocks.
- Consistent hashing, hinted handoff, Merkle trees.
- Split brain, fencing tokens, distributed locks.
- Replication, partitioning, failure detection.

### Build

- Toy replicated key-value store.
- Consistent hash ring.
- Quorum read/write simulator.
- Merkle-tree anti-entropy demo.
- Leader-election simulation.

## Month 8: Microservices Design and Patterns

### Learn

- Bounded contexts.
- Database per service.
- API gateway and BFF.
- Service discovery and load balancing.
- Saga, CQRS, event sourcing.
- Outbox, inbox, CDC.
- Circuit breaker, retry, timeout, bulkhead.
- Contract testing, versioning, observability.

### Build

Order, payment, inventory, catalog, user, notification, search, and analytics services with Kubernetes deployment.

## Month 9: Event-Driven Architecture and Kafka

### Learn

- Events, commands, topics, partitions, offsets.
- Ordering, replay, retention, compaction.
- Delivery semantics.
- DLQ and retry topics.
- Schema registry and event versioning.
- CDC and outbox.
- Stream processing.

### Build

- Event-driven order pipeline.
- Outbox table.
- CDC connector.
- Idempotent consumers.
- DLQ and replay tool.

## Month 10: Big Data Frameworks and Data Architecture

### Learn

- Data lake, warehouse, lakehouse, data mesh.
- Spark, Flink, Kafka, Airflow, dbt, Trino.
- Parquet, ORC, Avro.
- Iceberg, Delta Lake, Hudi.
- ClickHouse, Pinot, Druid.
- Redshift, Snowflake, BigQuery.
- Data quality, lineage, governance, PII.

### Build

Real-time analytics platform with Kafka, Spark/Flink, object storage, Iceberg/Delta/Hudi, Trino, ClickHouse/Pinot, and dashboards.

## Month 11: Observability, SRE, and Production Reliability

### Learn

- Logs, metrics, traces, profiles.
- OpenTelemetry.
- Prometheus, Grafana, Loki/ELK, Jaeger/Tempo.
- SLI, SLO, SLA, error budgets.
- Alerting, incident response, postmortems.
- Load testing, stress testing, chaos engineering.

### Build

- Full telemetry for capstone.
- Dashboards.
- Burn-rate alerts.
- Runbooks.
- Incident simulation and postmortem.

## Month 12: Kubernetes, Deployment, Cloud, Security, and Interview Mastery

### Learn

- Pods, Deployments, StatefulSets, Services, Ingress/Gateway.
- ConfigMaps, Secrets, Volumes, RBAC, NetworkPolicy.
- HPA, VPA, Cluster Autoscaler, PDB.
- Helm, Kustomize, GitOps, Argo CD/Flux.
- Canary, blue-green, rolling deployments.
- Service mesh, mTLS, CRDs, operators.
- Security, IAM, secrets, image scanning, policy as code.

### Build

- Deploy full platform to Kubernetes.
- Implement canary and rollback.
- Add network policies and RBAC.
- Add GitOps.
- Perform failover, backup, and recovery drills.

---

# 3. System Design Roadmap

## What You Must Master

### Requirements and Scope

- Functional vs non-functional requirements.
- Out-of-scope decisions.
- User personas and workflows.
- API consumers.
- Product constraints.
- Compliance constraints.

### Scale Estimation

- DAU, MAU, QPS, peak QPS.
- Read/write ratio.
- Storage per event/object.
- Bandwidth.
- Cache size.
- Partition count.
- Replication factor.
- Growth projection.

### API Design

- REST resources.
- gRPC services.
- Async event contracts.
- Idempotency keys.
- Pagination.
- Filtering and sorting.
- Versioning.
- Rate-limit headers.
- Error codes.

### Data Design

- Entities and relationships.
- Access patterns.
- Indexes.
- Partition keys.
- Consistency requirements.
- Retention and archival.
- Audit requirements.

### Scaling Patterns

- Horizontal scaling.
- Load balancing.
- Stateless services.
- Read replicas.
- Sharding.
- Caching.
- CDN.
- Queues.
- Stream processing.
- Materialized views.

### Reliability Patterns

- Timeout.
- Retry with jitter.
- Circuit breaker.
- Bulkhead.
- Fallback.
- Load shedding.
- Graceful degradation.
- Failover.
- Disaster recovery.

### Deep Practice Systems

- URL shortener.
- Rate limiter.
- Search autocomplete.
- Distributed cache.
- Notification system.
- Chat system.
- News feed.
- Media platform.
- Video streaming platform.
- File storage and sync.
- Payment system.
- Wallet and ledger.
- Trading system.
- Booking system.
- E-commerce platform.
- API gateway.
- Identity system.
- Feature flag platform.
- Observability platform.
- Real-time analytics platform.

## System Design Template

```text
1. Clarify scope
2. List functional requirements
3. List non-functional requirements
4. Estimate capacity
5. Define APIs
6. Define data model
7. Draw high-level design
8. Deep dive into bottlenecks
9. Handle failures
10. Add security
11. Add observability
12. Add deployment strategy
13. Discuss cost
14. Explain trade-offs
15. Explain migration path
```

---

# 4. Low-Level Design Roadmap

## Core Principles

- SOLID.
- DRY.
- KISS.
- YAGNI.
- Composition over inheritance.
- Encapsulation.
- Polymorphism.
- Immutability where useful.
- Dependency inversion.
- Separation of concerns.
- High cohesion, low coupling.

## Design Patterns

### Creational

- Factory Method.
- Abstract Factory.
- Builder.
- Prototype.
- Singleton with caution.

### Structural

- Adapter.
- Facade.
- Decorator.
- Proxy.
- Composite.
- Bridge.

### Behavioral

- Strategy.
- Observer.
- Command.
- State.
- Chain of Responsibility.
- Template Method.
- Mediator.
- Visitor.

### Enterprise Patterns

- Repository.
- Unit of Work.
- Service Layer.
- Specification.
- Data Mapper.
- Domain Model.
- Transaction Script.
- CQRS.
- Outbox.
- Saga.

## LLD Answer Template

```text
1. Clarify requirements
2. Identify actors and use cases
3. Identify core entities
4. Define class responsibilities
5. Define interfaces
6. Define relationships
7. Model state transitions
8. Handle concurrency
9. Define persistence model
10. Define error handling
11. Discuss extensibility
12. Discuss tests
```

## Practice Problems

- Parking lot.
- Elevator.
- Library management.
- Food delivery.
- Hotel booking.
- Movie ticket booking.
- Chess.
- Snake and ladder.
- Splitwise.
- ATM.
- Vending machine.
- File system.
- Logging framework.
- Rate limiter.
- Cache library.
- Notification service.
- Payment gateway.
- Wallet.
- Rule engine.
- Workflow engine.
- Feature flag SDK.
- Job scheduler.
- API gateway filters.
- Distributed lock client.
- Circuit breaker library.

---

# 5. DSA Roadmap for Architect Interviews

## Why DSA Matters for Architects

DSA is not only for coding rounds. It helps you reason about scalability, memory, streaming, scheduling, routing, caching, partitioning, query planning, and distributed systems.

## Must-Master Patterns

- Arrays and prefix sums.
- Hash maps and sets.
- Two pointers.
- Sliding window.
- Stack and monotonic stack.
- Queue and deque.
- Heap and priority queue.
- Binary search.
- Intervals.
- Linked lists.
- Trees.
- Tries.
- Graph BFS/DFS.
- Topological sort.
- Union-find.
- Shortest paths.
- Backtracking.
- Dynamic programming.
- Greedy algorithms.
- Bit manipulation.
- Streaming top-K.
- Bloom filters.
- Consistent hashing.
- LRU/LFU caches.
- Concurrent queues.

## Production Connections

| DSA Topic | Production Usage |
| --- | --- |
| Heap | Schedulers, top-K analytics, priority queues. |
| Trie | Autocomplete, prefix search, routing tables. |
| Graph traversal | Dependency resolution, workflow engines, social graphs. |
| Union-find | Clustering, connectivity, account merge. |
| Consistent hashing | Distributed cache, sharded storage, load distribution. |
| Bloom filter | Avoiding unnecessary database or disk reads. |
| Sliding window | Rate limiting, stream analytics, fraud detection. |
| LRU/LFU | Cache eviction. |
| Dynamic programming | Optimization, pricing, scheduling. |

---

# 6. Languages and Frameworks Roadmap

## Pick One Primary Stack

You need one deep stack and two conversational stacks.

### Primary Stack Option 1: Java + Spring Boot

Master:

- JVM memory: heap, stack, metaspace.
- Garbage collection: G1, ZGC concepts, pause-time trade-offs.
- Java memory model.
- Threads, locks, volatile, synchronized, ReentrantLock.
- ExecutorService, CompletableFuture, virtual threads concepts.
- Collections internals: HashMap, ConcurrentHashMap, ArrayList.
- Spring Boot lifecycle.
- Auto-configuration.
- Dependency injection.
- Spring MVC request lifecycle.
- Spring Security filter chain.
- JPA/Hibernate, transactions, N+1 problem, lazy/eager loading.
- HikariCP/connection pooling.
- Resilience4j.
- Micrometer and OpenTelemetry.
- Testcontainers.

### Primary Stack Option 2: Go

Master:

- Goroutines.
- Channels.
- Context cancellation.
- Interfaces.
- Struct composition.
- Error handling.
- Race detection.
- Worker pools.
- HTTP server internals.
- gRPC.
- Kubernetes/operator ecosystem.

### Primary Stack Option 3: Python

Master:

- FastAPI.
- asyncio.
- multiprocessing vs multithreading.
- GIL basics.
- Pydantic.
- SQLAlchemy.
- Celery.
- PySpark.
- Airflow DAGs.
- Data engineering patterns.

### Primary Stack Option 4: TypeScript/Node.js

Master:

- Event loop.
- Promises and async/await.
- Streams and backpressure.
- Worker threads.
- NestJS.
- Express/Fastify.
- TypeScript type system.
- Memory leaks.
- Observability.

## Architect-Level Framework Questions

Always connect framework internals to:

- Latency.
- Throughput.
- Memory.
- Threading.
- Connection pools.
- Transactions.
- Deployment.
- Debuggability.
- Operational risk.

---

# 7. Database Design and Internals Roadmap

This section is intentionally deep. Architect interviews often become database interviews because most hard system-design trade-offs are data trade-offs.

## 7.1 Data Modeling in Depth

### Conceptual Modeling

- Identify business entities, relationships, invariants, lifecycle, and ownership.
- Separate commands, queries, events, and audit requirements.
- Define consistency boundaries: what must be correct immediately vs eventually.

### Logical Modeling

- Relational tables, keys, foreign keys, constraints.
- Document collections and embedded vs referenced documents.
- Wide-column tables designed by query pattern.
- Key-value access with composite keys.
- Graph nodes and relationships.
- OLAP facts and dimensions.

### Physical Modeling

- Partition keys.
- Clustering keys.
- Index design.
- Sort keys.
- Distribution keys.
- File format and compression.
- Storage layout.
- Retention and archival.

### Modeling Rules

- Start from access patterns.
- Model writes and reads separately.
- Know invariants before choosing technology.
- Avoid joins in systems that cannot serve joins efficiently.
- Avoid unbounded arrays/documents.
- Avoid hot partitions.
- Design for migration.

## 7.2 Storage and Retrieval in Depth

### Row Stores

- Good for OLTP point lookups and transactional workloads.
- Store rows together, making full-row reads efficient.
- Common in PostgreSQL, SQL Server, MySQL/InnoDB.

### Column Stores

- Good for OLAP scans, aggregation, compression, and vectorized execution.
- Store values of a column together.
- Common in ClickHouse, Redshift, Pinot, Druid, Parquet-based lakes.

### B-Tree / B+Tree Storage

- Balanced tree optimized for range scans and point lookups.
- Updates can cause page splits.
- Needs maintenance for fragmentation and statistics.

### LSM Tree Storage

- Writes go to memory and commit log, then flush to immutable SSTables.
- Reads may check memtable, block cache, bloom filters, and SSTables.
- Compaction merges files and removes obsolete versions/tombstones.
- Used in RocksDB, Cassandra/Scylla-style systems, and many embedded/distributed stores.

### Log-Structured Storage

- Append-only writes improve write throughput.
- Requires compaction, garbage collection, or segment cleaning.
- Enables replay and crash recovery.

## 7.3 Pages, Fragmentation, and Maintenance

### Pages

- Databases store data in fixed-size pages or blocks.
- Pages contain tuples/records, headers, free space, and metadata.
- Indexes also use pages.

### Fragmentation

- Page splits can fragment indexes.
- Updates can create dead tuples or row movement.
- Deletes leave free space or tombstones.
- Fragmentation can increase random I/O, memory pressure, and scan cost.

### Maintenance

- Vacuum or cleanup dead row versions.
- Reindex fragmented indexes.
- Update statistics.
- Compact LSM files.
- Manage tombstones.
- Monitor bloat, free space, and page split rates.

## 7.4 Encoding and Evolution in Depth

### Encoding Formats

- JSON: human-readable, flexible, larger payloads.
- Avro: compact, schema-based, good for Kafka and data lakes.
- Protobuf: compact, strongly typed, common for gRPC.
- Parquet/ORC: columnar analytics formats.

### Schema Evolution

- Backward compatibility: new reader reads old data.
- Forward compatibility: old reader can tolerate new data.
- Full compatibility: both directions.
- Add optional fields before required fields.
- Do not reuse field IDs in Protobuf.
- Avoid breaking enum changes.
- Version events and APIs explicitly.

## 7.5 Query Languages in Depth

### SQL

- Declarative relational language.
- Strong for joins, aggregation, transactions, ad hoc analysis.
- Requires query planning and statistics.

### CQL / Wide-Column Query Languages

- Query by partition key and clustering key.
- Denormalized tables per access pattern.
- No arbitrary joins.

### Document Queries

- Query nested JSON-like structures.
- Index specific fields and compound patterns.
- Watch document growth and unbounded arrays.

### Search Query Languages

- Full-text search, scoring, analyzers, inverted indexes.
- Not a replacement for primary transactional storage.

### Graph Query Languages

- Relationship traversal.
- Useful for fraud, recommendations, identity graphs, network analysis.

## 7.6 Indexing in Depth

### Index Types

- Primary index.
- Secondary index.
- Composite index.
- Covering index.
- Partial/filtered index.
- Expression/function index.
- B-tree/B+tree index.
- Hash index.
- Bitmap index.
- Inverted index.
- GIN/GiST/SP-GiST/BRIN.
- Bloom filters.
- Sparse index.
- Data skipping index.
- Vector index.

### Index Trade-offs

- Faster reads.
- Slower writes.
- More storage.
- More maintenance.
- More optimizer complexity.
- Risk of unused indexes.
- Risk of wrong index due stale stats.

## 7.7 Query Analysis in Depth

Learn to read:

- Sequential scan.
- Index scan.
- Index-only scan.
- Bitmap scan.
- Nested loop join.
- Hash join.
- Merge join.
- Sort.
- Aggregate.
- Window function.
- Materialization.
- Spill to disk.
- Estimated vs actual rows.
- Cost estimates.
- Buffers read/hit/dirtied.
- Lock waits.

### Query Tuning Checklist

1. Confirm the access pattern.
2. Check execution plan.
3. Compare estimated vs actual rows.
4. Check indexes.
5. Check statistics freshness.
6. Check join order and join algorithm.
7. Check sorts and memory spills.
8. Check lock waits.
9. Check connection pool saturation.
10. Check cache hit ratio.

## 7.8 Transactions and Concurrency in Depth

### ACID

- Atomicity: all-or-nothing.
- Consistency: constraints and invariants preserved.
- Isolation: concurrent transactions do not corrupt each other.
- Durability: committed data survives failure.

### Isolation Levels

- Read Uncommitted.
- Read Committed.
- Repeatable Read.
- Snapshot Isolation.
- Serializable.

### Anomalies

- Dirty read.
- Non-repeatable read.
- Phantom read.
- Lost update.
- Write skew.
- Read skew.

### Concurrency Control

- Lock-based concurrency.
- MVCC.
- Optimistic concurrency control.
- Pessimistic locking.
- Serializable snapshot isolation.
- Deadlock detection.
- Lock escalation.
- Fencing tokens for distributed writes.

## 7.9 Replication in Depth

### Replication Types

- Synchronous replication.
- Asynchronous replication.
- Semi-synchronous replication.
- Leader-follower replication.
- Multi-leader replication.
- Leaderless replication.
- Log shipping.
- Physical replication.
- Logical replication.
- CDC-based replication.

### Replication Concerns

- Replication lag.
- Read-your-writes.
- Failover.
- Split brain.
- Quorum.
- Conflict resolution.
- Data loss window.
- RPO/RTO.

## 7.10 Partitioning and Sharding in Depth

### Partitioning Types

- Range partitioning.
- Hash partitioning.
- List partitioning.
- Composite partitioning.
- Time-based partitioning.
- Tenant-based partitioning.

### Sharding Strategies

- Application-level sharding.
- Database-native sharding.
- Consistent hashing.
- Directory-based routing.
- Range-based routing.
- Geo-sharding.
- Tenant sharding.

### Sharding Risks

- Hot shards.
- Cross-shard joins.
- Cross-shard transactions.
- Rebalancing complexity.
- Operational complexity.
- Skewed tenants.
- Global secondary indexes.

## 7.11 Caching in Depth

### Patterns

- Cache-aside.
- Read-through.
- Write-through.
- Write-back.
- Refresh-ahead.
- Negative caching.
- Local cache.
- Distributed cache.
- CDN cache.

### Failure Modes

- Cache stampede.
- Cache penetration.
- Cache avalanche.
- Hot key.
- Stale reads.
- Thundering herd.
- Memory eviction.

### Mitigations

- TTL jitter.
- Request coalescing.
- Soft TTL and background refresh.
- Bloom filters.
- Hot-key replication.
- Rate limits.
- Circuit breakers.

## 7.12 Distributed Transactions in Depth

### Approaches

- Two-phase commit.
- Three-phase commit.
- Saga orchestration.
- Saga choreography.
- Try-confirm-cancel.
- Transactional outbox.
- Inbox deduplication.
- CDC.
- Idempotency keys.

### Architect-Level Rule

Avoid distributed transactions unless strict atomicity is truly required. Prefer local transactions plus events, sagas, idempotency, and compensation for business workflows.

## 7.13 Consistency and Consensus in Depth

### Consistency Models

- Linearizability.
- Serializability.
- Sequential consistency.
- Causal consistency.
- Monotonic reads.
- Read-your-writes.
- Bounded staleness.
- Eventual consistency.

### Consensus

- Used when nodes must agree on a value/order despite failures.
- Common use cases: leader election, metadata replication, distributed configuration, membership changes.
- Learn Raft and Paxos conceptually.

## 7.14 CAP Theorem in Depth

During a network partition, a distributed data system must choose between:

- **Consistency:** every read sees the latest committed write.
- **Availability:** every request receives a non-error response.
- **Partition tolerance:** system continues despite network partitions.

Practical systems are more nuanced. Discuss CAP with PACELC:

- If Partition, choose Availability or Consistency.
- Else, choose Latency or Consistency.

## 7.15 Backup and Recovery in Depth

### Backup Types

- Full backup.
- Incremental backup.
- Differential backup.
- Snapshot.
- Logical dump.
- Physical backup.
- WAL/archive-based backup.
- Point-in-time recovery.

### Recovery Concepts

- RPO: how much data loss is acceptable.
- RTO: how quickly service must recover.
- Restore testing.
- Backup encryption.
- Retention policy.
- Cross-region copies.
- Disaster recovery drills.

## 7.16 Monitoring in Depth

Monitor:

- Query latency.
- QPS.
- Error rate.
- Connection count.
- Connection pool saturation.
- Lock waits.
- Deadlocks.
- Replication lag.
- Cache hit ratio.
- Index usage.
- Table/index bloat.
- Disk IOPS.
- CPU and memory.
- WAL/log growth.
- Backup success/failure.
- Slow queries.

---

# 8. Database Technology Deep Dives

## 8.1 PostgreSQL

### Best For

- Relational OLTP.
- Strong consistency.
- Complex SQL.
- Transactions.
- Extensibility.
- Moderate-to-high scale with proper design.

### Learn Deeply

- MVCC.
- WAL.
- Autovacuum.
- Transaction isolation.
- B-tree, Hash, GIN, GiST, SP-GiST, BRIN indexes.
- Partitioning.
- Query planner and statistics.
- EXPLAIN and EXPLAIN ANALYZE.
- Physical and logical replication.
- PITR.
- Connection pooling with PgBouncer.
- Table/index bloat.
- Locks and deadlocks.

### Interview Focus

- Why Postgres for transactional state?
- How does MVCC work?
- Why does autovacuum matter?
- How do you tune slow queries?
- How do you handle high write load?
- How do you scale reads and writes?

## 8.2 Microsoft SQL Server

### Best For

- Enterprise OLTP and analytics.
- Microsoft ecosystem.
- Strong tooling.
- Stored procedures, reporting, BI integrations.

### Learn Deeply

- Clustered and non-clustered indexes.
- Execution plans.
- Locking and row-versioning isolation.
- TempDB.
- Query Store.
- Always On Availability Groups.
- Backup/restore.
- Columnstore indexes.
- Partitioning.
- Statistics.

### Interview Focus

- Clustered vs non-clustered indexes.
- Read committed snapshot isolation.
- Parameter sniffing.
- Deadlocks.
- Query Store usage.
- High availability design.

## 8.3 MongoDB

### Best For

- Document-oriented workloads.
- Flexible schema.
- Aggregation pipelines.
- Rapid product iteration.
- Nested data with bounded document growth.

### Learn Deeply

- Document modeling.
- Embedded vs referenced documents.
- Indexes and compound indexes.
- Aggregation pipeline.
- Replica sets.
- Sharding.
- Read/write concerns.
- Transactions.
- Change streams.
- TTL indexes.

### Interview Focus

- When embedding is better than referencing.
- How to prevent unbounded documents.
- How shard keys are chosen.
- How read/write concerns affect consistency.

## 8.4 ScyllaDB

### Best For

- Cassandra-compatible wide-column workloads.
- High-throughput, low-latency, horizontally scalable systems.
- Query-pattern-first modeling.

### Learn Deeply

- Partition key and clustering key design.
- CQL.
- Replication factor.
- Tunable consistency.
- Compaction.
- Tombstones.
- Read repair and anti-entropy concepts.
- Shard-per-core architecture concept.
- Materialized views and secondary-index trade-offs.

### Interview Focus

- Why queries must follow primary key design.
- How hot partitions happen.
- How consistency levels work.
- How tombstones hurt performance.

## 8.5 Aerospike

### Best For

- Ultra-low-latency key-value workloads.
- Ad tech, personalization, fraud, session/profile stores.
- Large scale with memory/NVMe-oriented architecture.

### Learn Deeply

- Namespace, set, record, bin.
- Primary index.
- Secondary index.
- Data distribution.
- Strong consistency vs availability modes.
- Replication.
- XDR cross-datacenter replication.
- TTL and eviction.
- Batch operations.

### Interview Focus

- Why Aerospike for very low latency?
- AP vs CP mode.
- Primary-index behavior.
- Operational tuning and replication.

## 8.6 Redis

### Best For

- Cache.
- Session store.
- Rate limiting.
- Leaderboard.
- Pub/sub and streams.
- Distributed locks with caution.
- Real-time counters.

### Learn Deeply

- Data structures: string, hash, list, set, sorted set, stream, bitmap, hyperloglog, geospatial, JSON/vector modules where relevant.
- Expiration and eviction policies.
- Persistence: RDB and AOF.
- Replication.
- Sentinel.
- Cluster mode.
- Pipelining.
- Lua scripts.
- Hot keys.

### Interview Focus

- Cache-aside pattern.
- Redis cluster slotting.
- Eviction policy selection.
- Why distributed locks are subtle.
- How to handle cache stampede.

## 8.7 RocksDB

### Best For

- Embedded high-performance key-value storage.
- Systems that need an LSM-tree engine.
- Building databases, stream processors, caches, metadata stores.

### Learn Deeply

- Memtables.
- WAL.
- SSTables.
- Bloom filters.
- Block cache.
- Compaction strategies.
- Write amplification.
- Read amplification.
- Space amplification.
- Column families.
- Snapshots.

### Interview Focus

- Why LSM for write-heavy systems?
- How compaction affects latency.
- How bloom filters reduce reads.
- How to tune write/read/space amplification.

## 8.8 Apache Pinot

### Best For

- Real-time OLAP.
- User-facing analytics dashboards.
- Low-latency aggregation over event data.

### Learn Deeply

- Offline and real-time tables.
- Segments.
- Ingestion from Kafka.
- Star-tree indexes.
- Inverted, range, JSON, text indexes.
- Brokers, servers, controllers, minions.
- Query routing.
- Upsert support and limitations.

### Interview Focus

- Pinot vs ClickHouse vs Druid.
- How segments are created and queried.
- How to model analytics tables.
- How to handle late events and backfills.

## 8.9 ClickHouse

### Best For

- High-performance columnar OLAP.
- Logs, events, traces, analytics.
- Large scans and aggregations.

### Learn Deeply

- MergeTree engine family.
- Parts and background merges.
- Primary key as sort order.
- Partitioning.
- Data skipping indexes.
- Projections.
- Materialized views.
- Compression.
- Distributed tables.
- ReplicatedMergeTree.

### Interview Focus

- Why ClickHouse is fast for analytics.
- How ordering key differs from OLTP primary key.
- How merges affect ingestion/query performance.
- How to design partitions and materialized views.

## 8.10 Amazon Redshift

### Best For

- Cloud data warehouse.
- SQL analytics over large datasets.
- BI workloads.
- Integration with AWS ecosystem.

### Learn Deeply

- Columnar storage.
- MPP architecture.
- Distribution styles and distribution keys.
- Sort keys.
- Spectrum.
- Workload management.
- Vacuum/analyze.
- Compression encoding.
- Materialized views.
- Concurrency scaling/serverless concepts.

### Interview Focus

- How to choose dist keys and sort keys.
- How to avoid data redistribution.
- How to optimize joins.
- Redshift vs Snowflake vs BigQuery vs ClickHouse.

## 8.11 Database Selection Matrix

| Workload | Strong Candidates | Avoid When |
| --- | --- | --- |
| Relational OLTP | PostgreSQL, SQL Server, MySQL | Massive global writes without sharding plan. |
| Flexible documents | MongoDB | You require complex cross-document joins everywhere. |
| Wide-column high write scale | ScyllaDB/Cassandra | You need ad hoc joins and arbitrary queries. |
| Ultra-low-latency KV | Aerospike, Redis | You need complex relational transactions. |
| Embedded LSM engine | RocksDB | You want a full client-server database out of the box. |
| Cache and ephemeral state | Redis | You need primary source-of-truth durability without careful persistence design. |
| Real-time OLAP | Pinot, ClickHouse, Druid | You need transactional row-level updates. |
| Cloud warehouse | Redshift, Snowflake, BigQuery | You need millisecond transactional APIs. |
| Search | Elasticsearch/OpenSearch | You need a transactional source of truth. |
| Graph traversal | Neo4j/graph DB | Your queries are simple key lookups. |
| Vector similarity | Vector DB / pgvector / Redis vector | You need strict OLTP constraints only. |

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

# 10. Microservices Design and Patterns Roadmap

## 10.1 Service Boundaries

Design services around business capabilities and bounded contexts, not around technical layers.

### Good Boundaries

- Clear ownership.
- Independent deployability.
- Private data ownership.
- Stable APIs/events.
- Minimal synchronous dependencies.
- Separate scalability and reliability needs.

### Bad Boundaries

- Service per table.
- Service per CRUD screen.
- Shared database across services.
- Chatty synchronous calls.
- Distributed monolith.
- No clear team ownership.

## 10.2 Core Microservice Patterns

### API Gateway

- Authentication.
- Routing.
- Rate limiting.
- Request/response transformation.
- TLS termination.
- Observability.

### Backend for Frontend

- UI-specific API aggregation.
- Reduces client complexity.
- Avoids one generic API serving every consumer poorly.

### Database Per Service

- Each service owns its data.
- Other services access through APIs or events.
- Enables autonomy but creates consistency challenges.

### Saga

- Coordinates long-running business transactions.
- Uses local transactions and compensation.
- Can be orchestrated or choreographed.

### CQRS

- Separate write model from read model.
- Useful when reads and writes have different scale/model needs.

### Event Sourcing

- Store state changes as events.
- Rebuild state through replay.
- Powerful but operationally complex.

### Transactional Outbox

- Save business state and event in same local transaction.
- Separate relay publishes event.
- Prevents DB commit success but event publish failure.

### Inbox Pattern

- Store processed message IDs.
- Enables idempotent consumers.

### CDC

- Capture database changes and publish events.
- Useful for integration and migration.

## 10.3 Resilience Patterns

- Timeout.
- Retry with exponential backoff and jitter.
- Circuit breaker.
- Bulkhead.
- Rate limiter.
- Fallback.
- Load shedding.
- Backpressure.
- Dead-letter queue.
- Poison message quarantine.

## 10.4 Microservice Deployment Patterns

- Rolling deployment.
- Blue-green deployment.
- Canary deployment.
- Shadow traffic.
- Feature flags.
- Progressive delivery.
- Expand-contract database migration.
- Backward-compatible event/API evolution.

## 10.5 Microservice Testing

- Unit tests.
- Integration tests.
- Contract tests.
- Consumer-driven contract tests.
- End-to-end smoke tests.
- Chaos tests.
- Load tests.
- Replay tests.

## 10.6 Microservice Capstone Requirements

Build:

- API gateway.
- User service.
- Catalog service.
- Cart service.
- Order service.
- Inventory service.
- Payment service.
- Notification service.
- Search service.
- Analytics service.

Implement:

- Database per service.
- Outbox.
- Saga.
- Kafka events.
- Redis caching.
- OpenTelemetry tracing.
- Kubernetes deployment.
- GitOps.
- Canary release.

---

# 11. Event-Driven Architecture Roadmap

## Core Concepts

- Event.
- Command.
- Query.
- Topic.
- Queue.
- Stream.
- Partition.
- Offset.
- Consumer group.
- Ordering.
- Replay.
- Retention.
- Compaction.
- Schema registry.
- Dead-letter queue.
- Retry topic.
- Idempotent consumer.
- Exactly-once processing limitations.

## Kafka Deep Dive

### Learn

- Brokers.
- Topics.
- Partitions.
- Replication factor.
- Leader and follower replicas.
- ISR.
- Producer acknowledgements.
- Idempotent producer.
- Transactions.
- Consumer groups.
- Offset commits.
- Rebalancing.
- Partition key choice.
- Consumer lag.
- Retention.
- Compaction.
- Kafka Connect.
- Kafka Streams.
- Schema Registry.

### Design Rules

- Choose partition key based on ordering and load distribution.
- Do not require global ordering unless absolutely necessary.
- Treat consumers as at-least-once by default.
- Make consumers idempotent.
- Use DLQs with runbooks.
- Version events carefully.
- Include trace IDs and correlation IDs.
- Monitor lag and processing errors.

## Event Schema Template

```json
{
  "eventId": "uuid",
  "eventType": "OrderCreated",
  "eventVersion": 1,
  "occurredAt": "timestamp",
  "producer": "order-service",
  "correlationId": "trace-or-business-id",
  "tenantId": "tenant-id",
  "payload": {}
}
```

---

# 12. Big Data Frameworks and Data Architecture Roadmap

## Big Data Foundation

- OLTP vs OLAP.
- Data lake vs warehouse vs lakehouse.
- Data mesh.
- Batch vs streaming.
- ETL vs ELT.
- Lambda vs Kappa architecture.
- CDC.
- Data quality.
- Data lineage.
- Data governance.
- PII and compliance.

## Frameworks

### Kafka

- Event ingestion.
- Replayable logs.
- Stream source for analytics.

### Spark

- Batch processing.
- Spark SQL.
- DataFrames.
- Structured Streaming.
- Shuffle optimization.
- Skew handling.
- Broadcast joins.
- Caching and persistence.

### Flink

- Stateful stream processing.
- Event time.
- Watermarks.
- Checkpoints.
- Savepoints.
- Exactly-once processing.
- Low-latency streaming.

### Airflow

- DAG orchestration.
- Scheduling.
- Retries.
- Backfills.
- SLA monitoring.

### dbt

- SQL transformations.
- Data tests.
- Documentation.
- Lineage.

### Trino/Presto

- Federated SQL.
- Interactive analytics.
- Querying data lakes.

### Lakehouse Formats

- Apache Iceberg.
- Delta Lake.
- Apache Hudi.

### OLAP Serving

- ClickHouse.
- Apache Pinot.
- Apache Druid.

### Data Warehouses

- Redshift.
- Snowflake.
- BigQuery.

## Big Data Capstone

Build a clickstream analytics platform:

1. Ingest events through Kafka.
2. Validate schemas.
3. Store raw events in object storage.
4. Process batch with Spark.
5. Process streaming with Flink or Spark Structured Streaming.
6. Store curated tables in Iceberg/Delta/Hudi.
7. Query with Trino.
8. Serve real-time dashboard from ClickHouse/Pinot.
9. Add data quality checks.
10. Add lineage, monitoring, and cost controls.

---

# 13. Software Architecture Concepts Roadmap

## Architecture Styles

- Layered architecture.
- Clean architecture.
- Hexagonal architecture.
- Onion architecture.
- Modular monolith.
- Microservices.
- Service-oriented architecture.
- Event-driven architecture.
- CQRS.
- Event sourcing.
- Serverless.
- Cell-based architecture.
- Multi-tenant architecture.
- Data mesh.
- Lakehouse.
- Microkernel/plugin architecture.
- Pipe-and-filter.
- Space-based architecture.

## Architecture Documentation

- C4 context diagram.
- C4 container diagram.
- Component diagram.
- Sequence diagram.
- Deployment diagram.
- Data-flow diagram.
- Threat model.
- ADR.
- RFC.
- Migration plan.
- Runbook.
- Postmortem.
- Capacity plan.
- SLO document.

## ADR Template

```text
Title:
Status:
Context:
Decision:
Options considered:
Trade-offs:
Risks:
Migration/rollback plan:
Success metrics:
Review date:
```

## Quality Attributes

- Availability.
- Reliability.
- Scalability.
- Maintainability.
- Testability.
- Security.
- Observability.
- Performance.
- Cost efficiency.
- Portability.
- Extensibility.

---

# 14. Observability, SRE, and Production Reliability Roadmap

## Observability Pillars

- Logs.
- Metrics.
- Traces.
- Profiles.
- Events.

## OpenTelemetry

Learn:

- Traces.
- Spans.
- Metrics.
- Logs.
- Context propagation.
- Instrumentation libraries.
- Collector.
- Exporters.

## Metrics Frameworks

### RED Metrics

- Rate.
- Errors.
- Duration.

### USE Metrics

- Utilization.
- Saturation.
- Errors.

### Golden Signals

- Latency.
- Traffic.
- Errors.
- Saturation.

## SRE Concepts

- SLI.
- SLO.
- SLA.
- Error budget.
- Burn-rate alert.
- Incident response.
- Postmortem.
- Runbook.
- Toil.
- Capacity planning.
- Load testing.
- Chaos engineering.

## Production Dashboards

Create dashboards for:

- API latency p50/p90/p95/p99.
- Error rate.
- Request rate.
- Saturation.
- Database slow queries.
- Connection pool usage.
- Kafka consumer lag.
- Redis hit ratio.
- Kubernetes pod restarts.
- Deployment health.
- SLO burn rate.

---

# 15. Kubernetes, Deployment, and Cloud-Native Roadmap

## Kubernetes Core

- Cluster.
- Node.
- Pod.
- Deployment.
- ReplicaSet.
- StatefulSet.
- DaemonSet.
- Job.
- CronJob.
- Service.
- EndpointSlice.
- Ingress.
- Gateway API.
- ConfigMap.
- Secret.
- Volume.
- PersistentVolume.
- PersistentVolumeClaim.
- StorageClass.
- Namespace.
- ServiceAccount.
- RBAC.
- NetworkPolicy.
- Resource requests and limits.
- Probes.
- HPA.
- VPA.
- Cluster Autoscaler.
- PodDisruptionBudget.
- Taints and tolerations.
- Affinity and anti-affinity.
- CRD.
- Operator.

## Deployment

- Dockerfile best practices.
- Multi-stage builds.
- Image scanning.
- SBOM.
- Container registry.
- CI/CD.
- GitOps.
- Argo CD.
- Flux.
- Helm.
- Kustomize.
- Terraform.
- Secrets management.
- Rolling deployment.
- Blue-green deployment.
- Canary deployment.
- Shadow traffic.
- Feature flags.
- Rollback.
- Database migration.
- Expand-contract pattern.

## Kubernetes Troubleshooting

Know how to debug:

- CrashLoopBackOff.
- ImagePullBackOff.
- Pending pods.
- Readiness probe failures.
- Liveness probe failures.
- OOMKilled.
- CPU throttling.
- DNS failure.
- Service routing failure.
- Ingress routing failure.
- Persistent volume mount failure.
- RBAC denied.
- NetworkPolicy blocking traffic.
- HPA not scaling.
- Rollout stuck.

---

# 16. Security and Cloud Architecture Roadmap

## Security Foundation

- Authentication.
- Authorization.
- OAuth2.
- OIDC.
- JWT.
- Sessions.
- RBAC.
- ABAC.
- Zero trust.
- Secrets management.
- Encryption in transit.
- Encryption at rest.
- Key management.
- Network segmentation.
- API security.
- WAF.
- DDoS protection.
- Audit logging.
- Threat modeling.

## Cloud Architecture

- VPC design.
- Subnets.
- NAT gateway.
- Private endpoints.
- IAM.
- Managed databases.
- Object storage.
- Load balancers.
- CDN.
- Autoscaling.
- Multi-AZ design.
- Multi-region design.
- Disaster recovery.
- Cost controls.
- Tagging strategy.
- Cloud security posture.

## Supply-Chain Security

- SBOM.
- Image scanning.
- Dependency scanning.
- Signed images.
- Provenance.
- Policy as code.
- Admission controls.

---

---

# 16.5 Communication Protocols Deep Dive

## gRPC

### Architecture & Internals
- Built on HTTP/2: multiplexed streams, header compression (HPACK), binary framing.
- Protocol Buffers (protobuf) as Interface Definition Language (IDL) and serialization format.
- Code generation: `.proto` files → client stubs + server skeletons in 10+ languages.
- Four communication patterns:
  - Unary RPC (request-response).
  - Server streaming (one request, stream of responses).
  - Client streaming (stream of requests, one response).
  - Bidirectional streaming (both sides stream independently).

### Key Concepts
- **Interceptors**: middleware for logging, auth, metrics, retry logic (client-side and server-side).
- **Deadlines/Timeouts**: propagated across service hops; prevents cascading hangs.
- **Metadata**: key-value pairs sent as headers (like HTTP headers but typed).
- **Channel**: virtual connection to an endpoint; manages connection pool internally.
- **Name resolution & load balancing**: client-side (pick_first, round_robin) or external (Envoy, Linkerd).
- **Reflection**: runtime schema discovery for debugging tools like `grpcurl`.
- **Health checking protocol**: standard `grpc.health.v1.Health` service for load balancers.

### gRPC vs REST Comparison

| Aspect | gRPC | REST |
|--------|------|------|
| Serialization | Protobuf (binary) | JSON (text) |
| Transport | HTTP/2 only | HTTP/1.1 or HTTP/2 |
| Streaming | Native bidirectional | SSE or WebSocket bolt-on |
| Code generation | Built-in from .proto | OpenAPI/Swagger optional |
| Browser support | Requires grpc-web proxy | Native |
| Schema evolution | Field numbers, backward-compatible | Versioned URLs |
| Performance | 2-10x faster serialization | Human-readable |
| Tooling | grpcurl, Evans, BloomRPC | curl, Postman |

### Implementation Patterns
- **Service mesh integration**: Envoy as gRPC-aware sidecar (routing, retries, circuit breaking).
- **Gateway pattern**: grpc-gateway generates REST reverse-proxy from proto annotations.
- **Error model**: rich error details via `google.rpc.Status` with typed detail messages.
- **Retry policy**: configurable in service config JSON (max attempts, backoff, retryable status codes).
- **Connection keepalive**: PING frames to detect dead connections; configurable intervals.

### Interview Questions
1. How does gRPC achieve better performance than REST? Explain the HTTP/2 and protobuf layers.
2. Design a real-time collaborative editing service using bidirectional streaming gRPC.
3. How do you handle backward compatibility when evolving protobuf schemas?
4. Explain gRPC deadline propagation across a chain of 5 microservices. What happens when one times out?
5. How would you implement authentication in gRPC? Compare token-based vs mTLS approaches.
6. What happens when a gRPC client-side load balancer detects an unhealthy backend?
7. How do you debug a gRPC call that works in development but fails in production?
8. Compare gRPC interceptors to HTTP middleware. When would you choose one over the other?
9. How would you migrate a REST API to gRPC incrementally without breaking existing clients?
10. Explain how gRPC handles flow control in streaming RPCs. What is the window update mechanism?

---

## WebSockets

### Architecture & Internals
- Upgrade handshake: HTTP/1.1 → 101 Switching Protocols → persistent TCP connection.
- Frame types: text, binary, ping/pong (heartbeat), close.
- Full-duplex: both sides send independently without request/response pairing.
- No built-in multiplexing (unlike HTTP/2); one logical channel per connection.

### Scaling WebSockets
- **Sticky sessions**: required when using in-memory connection state; ALB/NLB with connection-based routing.
- **Pub/Sub backbone**: Redis Pub/Sub, NATS, or Kafka to fan-out messages across server instances.
- **Connection limits**: OS file descriptor limits (~1M per server with tuning), memory per connection (~2-10KB).
- **Horizontal scaling architecture**:
  ```
  Client → Load Balancer (L4, connection-based)
         → WebSocket Server (maintains conn registry)
         → Redis Pub/Sub (cross-server message routing)
         → WebSocket Server (delivers to target client)
  ```

### Connection Management
- **Heartbeat/Ping-Pong**: detect dead connections (30-60s interval typical).
- **Reconnection strategy**: exponential backoff with jitter (1s, 2s, 4s, 8s... + random 0-1s).
- **Connection state recovery**: resume token / last-event-ID to replay missed messages.
- **Graceful shutdown**: send close frame, drain in-flight messages, wait for close acknowledgment.
- **Authentication**: token in query param during upgrade (not ideal) or first message after connect.

### WebSocket vs Alternatives

| Feature | WebSocket | SSE | Long Polling | gRPC Streaming |
|---------|-----------|-----|--------------|----------------|
| Direction | Bidirectional | Server → Client | Simulated bidir | Bidirectional |
| Protocol | WS over TCP | HTTP/1.1 | HTTP/1.1 | HTTP/2 |
| Reconnection | Manual | Automatic | Automatic | Manual |
| Binary data | Yes | No (text only) | Yes | Yes (protobuf) |
| Browser support | All modern | All modern | All | Requires proxy |
| Through proxies | Sometimes blocked | Always works | Always works | Usually works |
| Max connections | ~6 per domain (browser) | ~6 per domain | ~6 per domain | Multiplexed |

### Interview Questions
1. Design a chat system supporting 10M concurrent WebSocket connections. How do you scale?
2. How do you handle WebSocket authentication and token refresh without dropping the connection?
3. Explain the WebSocket upgrade handshake. What happens if a proxy doesn't support it?
4. How do you implement exactly-once message delivery over WebSockets?
5. Design a real-time dashboard with 100K concurrent viewers. WebSocket vs SSE? Why?
6. How do you detect and handle zombie WebSocket connections (half-open state)?
7. Explain back-pressure in WebSocket streaming. What happens when the client can't keep up?
8. How would you implement room-based messaging (like Slack channels) at scale?
9. Compare WebSocket connection cost vs HTTP/2 server push for a stock ticker use case.
10. How do you test WebSocket-based systems? What failure modes do you simulate?

---

## Server-Sent Events (SSE)

### Architecture
- Unidirectional: server → client only over a standard HTTP/1.1 connection.
- `Content-Type: text/event-stream` with chunked transfer encoding.
- Built-in reconnection: browser automatically reconnects with `Last-Event-ID` header.
- Event format: `id:`, `event:`, `data:`, `retry:` fields.

### When to Use SSE vs WebSocket
- SSE: notifications, live feeds, dashboards, progress updates (server-initiated only).
- WebSocket: chat, gaming, collaborative editing (client needs to send data frequently).
- SSE advantages: works through all proxies/CDNs, automatic reconnection, simpler implementation.
- SSE limitations: text only, unidirectional, limited to ~6 connections per domain in HTTP/1.1.

### Interview Questions
1. When would you choose SSE over WebSocket for a real-time feature? Give three scenarios.
2. How does SSE handle reconnection and message replay? What is the `Last-Event-ID` mechanism?
3. Can you scale SSE through a CDN? How?
4. Design a deployment progress tracker using SSE. How do you handle long-running operations?
5. How do you work around the 6-connection-per-domain browser limit with SSE?

---

# 16.6 Caching Deep Dive

## Redis Architecture & Internals

### Data Structures (Beyond Basics)
- **Strings**: binary-safe up to 512MB; used for counters (INCR atomic), serialized objects, bitmaps.
- **Hashes**: field-value maps; memory-efficient for objects with many fields (ziplist encoding <128 fields).
- **Lists**: doubly-linked or ziplist; LPUSH/RPOP for queues, LRANGE for pagination.
- **Sets**: unique unordered; SINTER for mutual friends, SUNION for feed aggregation.
- **Sorted Sets (ZSets)**: skip list + hash table; ZRANGEBYSCORE for leaderboards, rate limiting windows.
- **Streams**: append-only log with consumer groups; Kafka-like semantics for event sourcing.
- **HyperLogLog**: probabilistic cardinality counting (~0.81% error, 12KB per key regardless of cardinality).
- **Bitmaps**: BITCOUNT/BITOP for daily active users, feature flags across millions of users.
- **Geospatial**: GEOADD/GEORADIUS for proximity search (sorted set internally with geohash).

### Memory Management
- **Eviction policies**: noeviction, allkeys-lru, volatile-lru, allkeys-lfu, volatile-lfu, allkeys-random, volatile-ttl.
- **LRU approximation**: samples 5 keys (configurable), evicts best candidate. Not true LRU.
- **LFU (Least Frequently Used)**: counter with logarithmic decay; better for access-pattern caches.
- **Memory fragmentation**: `INFO memory` → `mem_fragmentation_ratio`; use `MEMORY PURGE` or restart.
- **Key expiration**: passive (check on access) + active (periodic sampling of keys with TTL).
- **Lazy freeing**: `UNLINK` instead of `DEL` for large keys (async deletion in background thread).

### Cluster Architecture
- **Hash slots**: 16384 slots distributed across masters; CRC16(key) % 16384 determines slot.
- **Resharding**: `MIGRATE` moves slots between nodes; during migration, ASK/MOVED redirects.
- **Gossip protocol**: nodes exchange cluster state via ping/pong every 1 second.
- **Failover**: replica promotes when master is PFAIL (suspected fail) → FAIL (confirmed by majority).
- **Multi-key operations**: only work when all keys map to same slot; use hash tags `{user:1}:profile`.

### Redis Sentinel vs Cluster

| Feature | Sentinel | Cluster |
|---------|----------|---------|
| Sharding | No (single master) | Yes (16384 hash slots) |
| Max data | Single node RAM | Sum of all node RAM |
| Failover | Automatic (consensus) | Automatic (gossip) |
| Multi-key ops | All keys accessible | Same-slot only |
| Complexity | Low | High |
| Use case | HA for <50GB | Scale beyond single node |

### Advanced Patterns
- **Lua scripting**: atomic multi-command operations; EVAL/EVALSHA; used for rate limiters, locks.
- **Distributed lock (Redlock)**: acquire lock on N/2+1 instances; controversial (see Martin Kleppmann critique).
- **Pub/Sub**: fire-and-forget messaging; no persistence, no replay, no acknowledgment.
- **Streams with Consumer Groups**: persistent, acknowledged, replayable message processing.
- **Pipeline**: batch multiple commands in one round-trip; 5-10x throughput improvement.
- **Redis Functions**: server-side stored procedures replacing Lua EVAL (Redis 7+).

### Caching Strategies

| Strategy | Description | Consistency | Use Case |
|----------|-------------|-------------|----------|
| Cache-Aside | App reads/writes cache explicitly | Eventual | General purpose |
| Read-Through | Cache loads from DB on miss | Eventual | Read-heavy, simple |
| Write-Through | Write to cache and DB synchronously | Strong | Read-after-write needed |
| Write-Behind | Write to cache, async flush to DB | Eventual | Write-heavy, can tolerate lag |
| Refresh-Ahead | Proactively refresh before expiry | Eventual | Predictable access patterns |

### Cache Invalidation Patterns
- **TTL-based**: simple but stale data during TTL window.
- **Event-driven**: DB change events (CDC) trigger cache invalidation.
- **Version stamping**: include version in cache key; increment on change.
- **Tag-based**: associate keys with tags; invalidate all keys with a tag.

### Redis vs Memcached

| Feature | Redis | Memcached |
|---------|-------|-----------|
| Data structures | Rich (strings, lists, sets, hashes, streams) | Strings only |
| Persistence | RDB snapshots + AOF | None |
| Replication | Built-in master-replica | None (client-side) |
| Clustering | Redis Cluster (16384 slots) | Client-side consistent hashing |
| Scripting | Lua / Redis Functions | None |
| Memory efficiency | Higher overhead per key | Slab allocator, efficient for uniform sizes |
| Max value size | 512MB | 1MB default |
| Multithreading | I/O threads (Redis 6+), single command thread | Fully multithreaded |
| Use case | Complex data, persistence needed | Simple KV, session store, uniform objects |

### Interview Questions
1. Explain Redis cluster hash slot migration. What happens to requests during resharding?
2. Design a distributed rate limiter using Redis sorted sets. Handle the race condition.
3. Why is Redlock controversial? Explain the Kleppmann vs Antirez debate on distributed locks.
4. How does Redis achieve persistence with RDB and AOF? What are the tradeoffs of each?
5. Design a real-time leaderboard for 50M users with Redis. How do you handle ties?
6. Explain Redis memory fragmentation. How do you detect and fix it in production?
7. Compare Redis Streams vs Kafka for event sourcing. When would you choose each?
8. How do you handle cache stampede (thundering herd) when a popular key expires?
9. Design a session store with Redis. How do you handle Redis failures without losing sessions?
10. Explain the Redis single-threaded model. How does it achieve 100K+ ops/sec?
11. How do you implement cache warming for a new service deployment?
12. Design a pub/sub notification system with Redis. How do you handle subscriber failures?

---

# 16.7 Time-Series Databases

## TimescaleDB

### Architecture
- Extension on PostgreSQL: full SQL support, joins with relational tables, existing tooling.
- **Hypertables**: automatic partitioning by time (and optionally space/device_id).
- **Chunks**: each time partition is a separate PostgreSQL table; transparent to queries.
- Typically partition by 1 day or 1 week depending on ingestion rate.

### Key Features
- **Continuous Aggregates**: materialized views that auto-update as new data arrives; query pre-computed rollups.
- **Compression**: columnar compression on older chunks (90-95% compression ratio typical).
- **Data retention policies**: automatic DROP of chunks older than threshold (e.g., raw data 30 days, aggregates 1 year).
- **Real-time aggregates**: combine materialized aggregate with recent unmaterialized data.
- **Distributed hypertables**: shard across multiple PostgreSQL nodes for horizontal scale.

### Query Patterns
```sql
-- Time-bucket aggregation (TimescaleDB-specific)
SELECT time_bucket('5 minutes', time) AS bucket,
       device_id,
       AVG(temperature) AS avg_temp,
       MAX(temperature) AS max_temp
FROM sensor_data
WHERE time > NOW() - INTERVAL '24 hours'
GROUP BY bucket, device_id
ORDER BY bucket DESC;

-- Continuous aggregate definition
CREATE MATERIALIZED VIEW hourly_metrics
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 hour', time) AS hour,
       device_id,
       AVG(value), MIN(value), MAX(value), COUNT(*)
FROM raw_metrics
GROUP BY hour, device_id;
```

### TimescaleDB vs InfluxDB vs Prometheus

| Feature | TimescaleDB | InfluxDB | Prometheus |
|---------|-------------|----------|------------|
| Query language | SQL | InfluxQL / Flux | PromQL |
| Data model | Relational (wide table) | Tags + fields | Labels + metrics |
| Joins | Full SQL joins | Limited | None |
| Cardinality | Handles high cardinality well | Struggles at high cardinality | Struggles at high cardinality |
| Compression | 90-95% columnar | 80-90% | ~1.3 bytes/sample |
| Retention | Policy-based chunk drop | Retention policies | Block-based compaction |
| Scale | Distributed hypertables | Clustered (enterprise) | Federation / Thanos |
| Best for | IoT, analytics with joins | Metrics, events | Infrastructure monitoring |

### Interview Questions
1. How does TimescaleDB's hypertable partitioning differ from standard PostgreSQL partitioning?
2. Design a sensor data pipeline ingesting 1M data points/second. Which time-series DB and why?
3. Explain continuous aggregates. How do they handle late-arriving data?
4. How do you handle high-cardinality dimensions in time-series databases?
5. Compare chunk-based retention (TimescaleDB) vs block compaction (Prometheus). Tradeoffs?
6. Design a multi-tenant metrics platform. How do you isolate tenant data and queries?
7. How does columnar compression work in TimescaleDB? Why is it effective for time-series?
8. When would you use TimescaleDB over InfluxDB? Give three architectural reasons.


---

## 16.8 Observability & Monitoring Deep Dive

### Prometheus Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Exporters  │────▶│  Prometheus  │────▶│   Grafana   │
│  (Targets)  │     │   Server     │     │ Dashboards  │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                    ┌──────▼───────┐
                    │ Alertmanager │
                    └──────────────┘
```

**Core Components:**
| Component | Role | Key Config |
|-----------|------|------------|
| Prometheus Server | Scrapes & stores metrics (TSDB) | `scrape_interval`, `evaluation_interval` |
| Alertmanager | Routes & deduplicates alerts | `group_by`, `inhibit_rules`, `routes` |
| Pushgateway | For short-lived batch jobs | Push metrics before job exits |
| Exporters | Expose metrics in Prometheus format | node_exporter, blackbox_exporter |
| Service Discovery | Auto-find scrape targets | Kubernetes SD, Consul SD, DNS SD |

**PromQL Essentials:**
```promql
# Request rate per second (5-minute window)
rate(http_requests_total{job="api"}[5m])

# 99th percentile latency
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# Error rate percentage
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100

# Predict disk full in 4 hours
predict_linear(node_filesystem_free_bytes[1h], 4*3600) < 0
```

**Scaling Prometheus:**
| Approach | Use Case | Trade-off |
|----------|----------|-----------|
| Federation | Aggregate from multiple Prometheus instances | Loses granularity at higher levels |
| Thanos | Long-term storage + global view | Adds complexity (sidecar, store, compactor) |
| Cortex/Mimir | Multi-tenant, horizontally scalable | Heavy infrastructure requirement |
| VictoriaMetrics | Drop-in replacement, better compression | Smaller community than Thanos |
| Remote Write | Stream to external long-term store | Network bandwidth cost |

### VictoriaMetrics

**Architecture Advantages over Prometheus:**
- 10x better compression (less storage cost)
- Handles billions of time series
- MetricsQL (superset of PromQL with extensions)
- Supports multiple protocols: Prometheus, Graphite, InfluxDB, OpenTSDB
- Cluster mode with separate vminsert, vmselect, vmstorage

**Cluster Architecture:**
```
┌────────────┐     ┌────────────┐     ┌─────────────┐
│  vminsert  │────▶│ vmstorage  │◀────│  vmselect   │
│ (ingestion)│     │  (data)    │     │  (queries)  │
└────────────┘     └────────────┘     └─────────────┘
```

### Distributed Tracing

**OpenTelemetry Architecture:**
```
┌─────────────────────────────────────────────┐
│              Application                      │
│  ┌───────┐  ┌────────┐  ┌───────────────┐  │
│  │Traces │  │Metrics │  │    Logs       │  │
│  └───┬───┘  └───┬────┘  └──────┬────────┘  │
└──────┼──────────┼───────────────┼───────────┘
       └──────────┼───────────────┘
                  ▼
       ┌─────────────────────┐
       │  OTel Collector     │
       │  (Agent/Gateway)    │
       └─────────┬───────────┘
                 ▼
    ┌────────┬────────┬─────────┐
    │ Jaeger │ Zipkin │ Tempo   │
    └────────┴────────┴─────────┘
```

**Trace Propagation Context:**
| Header Format | Standard | Example |
|---------------|----------|---------|
| W3C TraceContext | `traceparent` | `00-{trace-id}-{span-id}-{flags}` |
| B3 (Zipkin) | `X-B3-TraceId` | Single or multi-header |
| Jaeger | `uber-trace-id` | `{trace-id}:{span-id}:{parent-id}:{flags}` |
| AWS X-Ray | `X-Amzn-Trace-Id` | `Root={trace-id};Parent={span-id}` |

**Sampling Strategies:**
| Strategy | Description | When to Use |
|----------|-------------|-------------|
| Always On | Trace every request | Dev/staging only |
| Probabilistic | Sample X% of requests | General production use |
| Rate Limiting | Max N traces/sec | High-traffic services |
| Tail-based | Decide after span completes (keep errors) | Need error traces without overhead |
| Parent-based | Follow parent's decision | Consistent across service boundaries |

### Observability Interview Questions

1. How would you design an alerting pipeline that avoids alert fatigue while ensuring critical issues are caught?
2. Explain the difference between black-box and white-box monitoring. When would you use each?
3. How does Prometheus handle high cardinality, and what strategies prevent cardinality explosion?
4. Design a distributed tracing system for a microservices architecture with 200+ services.
5. Compare push-based vs pull-based metrics collection. What are the failure modes of each?
6. How would you implement SLO-based alerting with error budgets?
7. Explain how Thanos achieves global query view across multiple Prometheus instances.
8. What's the difference between logging, metrics, and traces? When is each most appropriate?
9. How would you debug a latency spike that only affects p99 but not p50?
10. Design a log aggregation pipeline that handles 1TB/day with search latency under 2 seconds.

---

## 16.9 Infrastructure & Networking Deep Dive

### Load Balancers

**L4 vs L7 Comparison:**
| Feature | L4 (Transport) | L7 (Application) |
|---------|-----------------|-------------------|
| Layer | TCP/UDP | HTTP/HTTPS/gRPC |
| Speed | Faster (no payload inspection) | Slower (parses headers/body) |
| Routing | IP + Port | URL path, headers, cookies |
| SSL Termination | Pass-through or terminate | Always terminates |
| Session Persistence | Source IP hash | Cookie-based affinity |
| Health Checks | TCP connect / UDP | HTTP status code, body check |
| Use Case | Database, TCP services | Web apps, APIs, microservices |
| Examples | AWS NLB, HAProxy (TCP) | AWS ALB, Nginx, Envoy |

**Load Balancing Algorithms:**
| Algorithm | How It Works | Best For |
|-----------|--------------|----------|
| Round Robin | Sequential rotation | Equal-capacity servers |
| Weighted Round Robin | Rotation with weights | Mixed-capacity servers |
| Least Connections | Route to least-busy server | Variable request duration |
| Weighted Least Connections | Least connections + weights | Mixed capacity + variable duration |
| IP Hash | Hash source IP to server | Session persistence without cookies |
| Consistent Hashing | Hash ring for minimal redistribution | Cache servers, stateful routing |
| Random Two Choices | Pick 2 random, choose least loaded | Large server pools |
| Least Response Time | Route to fastest responding | Latency-sensitive applications |

**AWS ALB vs NLB vs CLB:**
| Feature | ALB | NLB | CLB (Legacy) |
|---------|-----|-----|--------------|
| Layer | 7 | 4 | 4/7 |
| Protocols | HTTP, HTTPS, gRPC | TCP, UDP, TLS | TCP, HTTP |
| WebSocket | Yes | Yes (TCP) | No |
| Static IP | No (use Global Accelerator) | Yes (Elastic IP per AZ) | No |
| Latency | ~ms added | ~µs added | ~ms added |
| Target Types | Instance, IP, Lambda | Instance, IP, ALB | Instance only |
| Path Routing | Yes | No | No |
| Cross-zone | Default on | Default off (cost) | Default on |

### API Gateway

**API Gateway Responsibilities:**
```
┌─────────────────────────────────────────────────────┐
│                   API Gateway                        │
│  ┌──────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │  Auth &  │ │   Rate   │ │  Request/Response │  │
│  │  AuthZ   │ │ Limiting │ │   Transformation  │  │
│  └──────────┘ └──────────┘ └───────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ Routing  │ │ Caching  │ │   Load Balancing  │  │
│  └──────────┘ └──────────┘ └───────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ Logging  │ │ Circuit  │ │   API Versioning  │  │
│  │& Metrics │ │ Breaker  │ │                   │  │
│  └──────────┘ └──────────┘ └───────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**API Gateway Comparison:**
| Feature | Kong | AWS API Gateway | Envoy | Nginx | Traefik |
|---------|------|-----------------|-------|-------|---------|
| Deployment | Self-hosted/Cloud | Managed | Sidecar/Edge | Self-hosted | Self-hosted |
| Protocol | HTTP, gRPC, TCP | HTTP, WebSocket | HTTP/2, gRPC, TCP | HTTP, TCP | HTTP, TCP, gRPC |
| Plugin System | Lua/Go plugins | Lambda authorizers | WASM/C++ filters | Lua/NJS | Middleware |
| Service Discovery | DNS, Consul | Built-in (AWS) | xDS API (Istio) | DNS, static | Docker, K8s, Consul |
| Observability | Prometheus, Datadog | CloudWatch | Built-in stats | Access logs | Prometheus, Datadog |
| Config Model | DB-backed (Postgres) | AWS Console/API | xDS (control plane) | File-based | Auto-discovery |

### Service Mesh

**Istio Architecture:**
```
┌────────────────── Control Plane ──────────────────┐
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐ │
│  │  Pilot │  │ Citadel│  │ Galley │  │ Mixer  │ │
│  │(config)│  │(certs) │  │(valid.)│  │(policy)│ │
│  └────────┘  └────────┘  └────────┘  └────────┘ │
└───────────────────────────────────────────────────┘
         ▲            ▲            ▲
         │            │            │
┌────────┼────────────┼────────────┼────────────────┐
│        ▼            ▼            ▼   Data Plane   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │  Envoy   │ │  Envoy   │ │  Envoy   │         │
│  │ (sidecar)│ │ (sidecar)│ │ (sidecar)│         │
│  └─────┬────┘ └─────┬────┘ └─────┬────┘         │
│  ┌─────▼────┐ ┌─────▼────┐ ┌─────▼────┐         │
│  │ Service A│ │ Service B│ │ Service C│         │
│  └──────────┘ └──────────┘ └──────────┘         │
└───────────────────────────────────────────────────┘
```

**Service Mesh Comparison:**
| Feature | Istio | Linkerd | Consul Connect | AWS App Mesh |
|---------|-------|---------|----------------|--------------|
| Proxy | Envoy | linkerd2-proxy (Rust) | Built-in / Envoy | Envoy |
| Complexity | High | Low | Medium | Medium |
| Performance Overhead | ~3-5ms p99 | ~1ms p99 | ~2-3ms p99 | ~2-3ms p99 |
| mTLS | Yes (auto) | Yes (auto) | Yes (manual/auto) | Yes |
| Multi-cluster | Yes | Yes | Yes (WAN Federation) | Cross-account |
| Protocol Support | HTTP/1.1, HTTP/2, gRPC, TCP | HTTP/1.1, HTTP/2, gRPC, TCP | HTTP, gRPC, TCP | HTTP, HTTP/2, gRPC |

### Infrastructure Interview Questions

1. Design a global load balancing strategy for a service deployed across 5 regions with failover requirements.
2. When would you choose an API Gateway over a service mesh, and vice versa?
3. How does consistent hashing improve cache hit rates during scaling events?
4. Explain how a CDN handles cache invalidation for dynamic content.
5. Design a DNS-based traffic management system with health checking and failover.
6. How would you implement zero-downtime deployments with blue-green and canary strategies at the load balancer level?
7. Compare sidecar proxy (Envoy) vs library-based (Hystrix) approaches to service communication.
8. How would you design connection draining during a rolling deployment?
9. Explain GeoDNS routing and its failure modes. How do you prevent cascading failures?
10. Design an API Gateway that handles 100K RPS with sub-10ms added latency.

---

## 16.10 Scaling Patterns Deep Dive

### Horizontal vs Vertical Scaling

| Aspect | Horizontal (Scale Out) | Vertical (Scale Up) |
|--------|----------------------|---------------------|
| Method | Add more machines | Add more resources to one machine |
| Limit | Theoretically unlimited | Hardware ceiling |
| Complexity | High (distributed systems) | Low (single machine) |
| Downtime | Zero (add/remove nodes) | Usually required for hardware changes |
| Cost Curve | Linear | Exponential at high end |
| Data Consistency | Requires coordination | Naturally consistent |
| Failure Impact | Partial degradation | Total failure |
| Best For | Stateless services, web tier | Databases, single-threaded workloads |

### Database Scaling Patterns

**Sharding Strategies:**
| Strategy | How It Works | Pros | Cons |
|----------|--------------|------|------|
| Range-based | Shard by value range (A-M, N-Z) | Simple, range queries work | Hotspots if data is skewed |
| Hash-based | Hash key to determine shard | Even distribution | Range queries span all shards |
| Geographic | Shard by region/location | Data locality, compliance | Cross-region queries expensive |
| Directory-based | Lookup table maps key→shard | Flexible rebalancing | Lookup table is SPOF |
| Consistent Hashing | Hash ring with virtual nodes | Minimal redistribution on scale | More complex implementation |

**Read Scaling Architecture:**
```
┌──────────┐     ┌──────────┐
│  Writes  │────▶│  Primary │
└──────────┘     └────┬─────┘
                      │ Replication
              ┌───────┼───────┐
              ▼       ▼       ▼
         ┌────────┐┌────────┐┌────────┐
         │Replica1││Replica2││Replica3│
         └────┬───┘└───┬────┘└───┬────┘
              └────────┼─────────┘
                       ▼
              ┌──────────────┐
              │    Reads     │
              └──────────────┘
```

**Replication Types:**
| Type | Consistency | Latency | Use Case |
|------|-------------|---------|----------|
| Synchronous | Strong | Higher write latency | Financial transactions |
| Asynchronous | Eventual | Lower write latency | Read-heavy workloads |
| Semi-synchronous | Middle ground | Moderate | Balance of both |
| Multi-master | Conflict resolution needed | Varies | Multi-region writes |

### CQRS (Command Query Responsibility Segregation)

```
┌───────────────────────────────────────────────────┐
│                   Commands                         │
│  ┌──────────┐    ┌───────────┐    ┌───────────┐  │
│  │  Client  │───▶│  Command  │───▶│  Write    │  │
│  │          │    │  Handler  │    │  Model    │  │
│  └──────────┘    └───────────┘    └─────┬─────┘  │
└─────────────────────────────────────────┼─────────┘
                                          │ Events
                                          ▼
                                   ┌─────────────┐
                                   │ Event Store │
                                   └──────┬──────┘
                                          │ Projection
                                          ▼
┌───────────────────────────────────────────────────┐
│                    Queries                          │
│  ┌──────────┐    ┌───────────┐    ┌───────────┐  │
│  │  Client  │◀───│  Query    │◀───│  Read     │  │
│  │          │    │  Handler  │    │  Model    │  │
│  └──────────┘    └───────────┘    └───────────┘  │
└───────────────────────────────────────────────────┘
```

**When to Use CQRS:**
| Use CQRS When | Avoid CQRS When |
|---------------|-----------------|
| Read/write patterns differ significantly | Simple CRUD application |
| Need different read/write models | Small team, limited complexity budget |
| High read:write ratio | Strong consistency required everywhere |
| Complex domain with event sourcing | Data model is simple and flat |
| Multiple read representations needed | Tight coupling between read/write is acceptable |

### Auto-Scaling Patterns

**Scaling Signals:**
| Signal | Metric | Threshold Example | Lag |
|--------|--------|-------------------|-----|
| CPU | Utilization % | Scale up > 70%, down < 30% | 2-3 min |
| Memory | Usage % | Scale up > 80% | 1-2 min |
| Request Rate | RPS per instance | Scale up > 1000 RPS/instance | 30s |
| Queue Depth | Messages pending | Scale up > 100 messages/worker | 10s |
| Response Time | p95 latency | Scale up > 500ms | 1-2 min |
| Custom | Business metric | Scale based on active users | Varies |

**Back-Pressure Mechanisms:**
| Mechanism | Implementation | Effect |
|-----------|---------------|--------|
| Request Queuing | Bounded queue with rejection | Producers slow down when queue full |
| Rate Limiting | Token bucket at ingress | Shed excess load early |
| Load Shedding | Drop low-priority requests | Protect critical paths |
| Circuit Breaker | Stop calling failing downstream | Prevent cascade |
| Adaptive Concurrency | Dynamic limit based on latency | Self-tuning capacity |
| Backoff Signals | HTTP 429 + Retry-After | Client-side cooperation |

### Connection Pooling

```
┌──────────────────────────────────────────┐
│            Application Server             │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │
│  │Req 1│ │Req 2│ │Req 3│ │Req N│       │
│  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘       │
│     └────────┼───────┼───────┘           │
│              ▼                            │
│     ┌─────────────────┐                  │
│     │ Connection Pool │                  │
│     │ (min:5, max:20) │                  │
│     └────────┬────────┘                  │
└──────────────┼───────────────────────────┘
               ▼
    ┌─────────────────────┐
    │    Database Server   │
    │  max_connections=100 │
    └─────────────────────┘
```

**Pool Sizing Formula:**
```
Pool Size = (Core Count * 2) + Effective Spindle Count
Example: 4 cores, SSD → (4 * 2) + 1 = 9 connections
```

### Scaling Interview Questions

1. Design an auto-scaling system that handles traffic spikes 10x normal within 60 seconds.
2. How would you implement database sharding for a social media platform with 500M users?
3. Explain the CAP theorem trade-offs when scaling a distributed database. Give real examples.
4. Design a CQRS system for an e-commerce platform. What consistency guarantees would you provide?
5. How do you handle connection pool exhaustion under load? What are the symptoms and fixes?
6. Compare horizontal scaling strategies for stateful vs stateless services.
7. Design a back-pressure system that gracefully degrades under 10x expected load.
8. How would you migrate from a monolithic database to a sharded architecture with zero downtime?
9. Explain read replica lag and its impact on user experience. How would you mitigate it?
10. Design a multi-region active-active database architecture. How do you handle conflicts?
11. What's the difference between load shedding and rate limiting? When would you use each?
12. How would you scale a WebSocket server to handle 10M concurrent connections?

---

## 16.11 Security Deep Dive

### OAuth 2.0 & OpenID Connect

```
┌──────────┐     ┌───────────────┐     ┌──────────────┐
│  Client  │────▶│ Authorization │────▶│   Resource   │
│   App    │◀────│    Server     │◀────│    Server    │
└──────────┘     └───────────────┘     └──────────────┘
      │                  │
      │  Authorization   │  Token
      │  Code Flow       │  Introspection
      ▼                  ▼
┌──────────┐     ┌───────────────┐
│  User    │     │  Token Store  │
│  Agent   │     │  (Redis/DB)   │
└──────────┘     └───────────────┘
```

#### OAuth 2.0 Grant Types

| Grant Type | Use Case | Security Level |
|---|---|---|
| Authorization Code + PKCE | SPAs, Mobile Apps | High |
| Client Credentials | Service-to-Service | High |
| Device Code | Smart TVs, CLI tools | Medium |
| Refresh Token | Long-lived sessions | Medium-High |
| ~~Implicit~~ (Deprecated) | Legacy SPAs | Low |
| ~~Resource Owner Password~~ (Deprecated) | Legacy migration | Low |

#### OIDC Token Types

| Token | Purpose | Format | Lifetime |
|---|---|---|---|
| ID Token | User identity assertion | JWT (signed) | 5-15 min |
| Access Token | API authorization | JWT or opaque | 5-60 min |
| Refresh Token | Obtain new access tokens | Opaque | 7-30 days |

#### PKCE (Proof Key for Code Exchange)

```
1. Client generates: code_verifier (random 43-128 chars)
2. Client computes: code_challenge = BASE64URL(SHA256(code_verifier))
3. Auth request includes: code_challenge + code_challenge_method=S256
4. Token request includes: code_verifier
5. Server verifies: SHA256(code_verifier) == stored code_challenge
```

### JWT Best Practices

#### JWT Structure & Validation

```json
// Header
{ "alg": "RS256", "typ": "JWT", "kid": "key-2026-01" }

// Payload
{
  "iss": "https://auth.example.com",
  "sub": "user-123",
  "aud": ["api.example.com"],
  "exp": 1737000000,
  "iat": 1736999100,
  "nbf": 1736999100,
  "jti": "unique-token-id",
  "scope": "read:users write:orders",
  "roles": ["admin"]
}

// Signature
RSASHA256(base64UrlEncode(header) + "." + base64UrlEncode(payload), privateKey)
```

#### JWT Security Checklist

| Practice | Rationale |
|---|---|
| Use RS256/ES256, never HS256 for public APIs | Asymmetric allows verification without secret |
| Validate `iss`, `aud`, `exp`, `nbf` | Prevents token misuse across services |
| Short expiry (5-15 min) | Limits window of compromise |
| Use `kid` for key rotation | Enables zero-downtime key changes |
| Store in HttpOnly cookies, not localStorage | Prevents XSS token theft |
| Implement token revocation list | Handles logout/compromise |
| Never store sensitive data in payload | JWTs are base64, not encrypted |
| Use `jti` claim for replay prevention | Detects reused tokens |

### Mutual TLS (mTLS)

```
┌────────┐                    ┌────────┐
│ Client │─────TLS Handshake──│ Server │
└────────┘                    └────────┘
    │                              │
    │ 1. ClientHello               │
    │─────────────────────────────▶│
    │                              │
    │ 2. ServerHello + ServerCert  │
    │◀─────────────────────────────│
    │                              │
    │ 3. CertificateRequest        │
    │◀─────────────────────────────│
    │                              │
    │ 4. ClientCert + Verify       │
    │─────────────────────────────▶│
    │                              │
    │ 5. Mutual Authentication ✓   │
    │◀────────────────────────────▶│
```

#### mTLS vs One-Way TLS

| Aspect | One-Way TLS | Mutual TLS |
|---|---|---|
| Server authenticated | Yes | Yes |
| Client authenticated | No (uses tokens) | Yes (certificate) |
| Use case | Public APIs | Service-to-service |
| Certificate management | Simple | Complex (both sides) |
| Performance overhead | Low | Medium (extra handshake) |
| Revocation | N/A for client | CRL/OCSP required |

### OWASP Top 10 (2021)

| # | Vulnerability | Mitigation |
|---|---|---|
| A01 | Broken Access Control | RBAC/ABAC, deny by default, server-side enforcement |
| A02 | Cryptographic Failures | TLS 1.3, AES-256-GCM, Argon2id for passwords |
| A03 | Injection | Parameterized queries, input validation, ORM usage |
| A04 | Insecure Design | Threat modeling, secure design patterns, abuse cases |
| A05 | Security Misconfiguration | Hardened defaults, automated scanning, IaC templates |
| A06 | Vulnerable Components | SCA scanning, dependency updates, SBOM |
| A07 | Auth Failures | MFA, credential stuffing protection, session management |
| A08 | Data Integrity Failures | Code signing, CI/CD pipeline security, SBOM verification |
| A09 | Logging & Monitoring | Centralized logging, alerting on auth failures, SIEM |
| A10 | SSRF | URL allowlists, network segmentation, disable redirects |

### API Security Patterns

#### Defense in Depth Layers

```
┌─────────────────────────────────────────────────────────┐
│                    WAF (Layer 7)                         │
│  DDoS protection, SQL injection, XSS filtering          │
├─────────────────────────────────────────────────────────┤
│                  API Gateway                            │
│  Rate limiting, authentication, request validation      │
├─────────────────────────────────────────────────────────┤
│                Service Mesh (mTLS)                       │
│  Service identity, encryption in transit                │
├─────────────────────────────────────────────────────────┤
│              Application Layer                           │
│  Authorization (RBAC/ABAC), input validation            │
├─────────────────────────────────────────────────────────┤
│                 Data Layer                               │
│  Encryption at rest, field-level encryption, masking    │
└─────────────────────────────────────────────────────────┘
```

#### API Security Headers

| Header | Value | Purpose |
|---|---|---|
| Strict-Transport-Security | max-age=31536000; includeSubDomains | Force HTTPS |
| Content-Security-Policy | default-src 'self' | Prevent XSS |
| X-Content-Type-Options | nosniff | Prevent MIME sniffing |
| X-Frame-Options | DENY | Prevent clickjacking |
| X-Request-Id | UUID | Request tracing |
| Cache-Control | no-store | Prevent caching sensitive data |

### Secrets Management

#### Architecture

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│  Application │────▶│  Secrets Agent  │────▶│    Vault     │
│              │◀────│  (Sidecar/Lib)  │◀────│   (KMS/HSM)  │
└──────────────┘     └─────────────────┘     └──────────────┘
                            │                        │
                     Lease Renewal            Audit Log
                     Auto-rotation            Access Policy
```

#### Secrets Management Comparison

| Solution | Type | Key Features | Best For |
|---|---|---|---|
| HashiCorp Vault | Self-hosted/Cloud | Dynamic secrets, PKI, encryption | Multi-cloud |
| AWS Secrets Manager | Cloud | Auto-rotation, RDS integration | AWS-native |
| Azure Key Vault | Cloud | HSM-backed, managed identities | Azure-native |
| GCP Secret Manager | Cloud | IAM-based, versioning | GCP-native |
| Doppler | SaaS | Universal sync, CLI-friendly | Startups |

#### Secret Rotation Strategy

| Secret Type | Rotation Frequency | Method |
|---|---|---|
| Database passwords | 30 days | Dynamic credentials (Vault) |
| API keys | 90 days | Dual-key rotation |
| TLS certificates | 90 days (Let's Encrypt auto) | ACME protocol |
| Encryption keys | 365 days | Key versioning with re-wrap |
| Service account tokens | 24 hours | Short-lived + auto-refresh |

### Zero Trust Architecture

#### Principles

```
┌─────────────────────────────────────────────────────────┐
│                  Zero Trust Pillars                      │
├──────────┬──────────┬──────────┬──────────┬────────────┤
│ Identity │ Device   │ Network  │ App/     │ Data       │
│          │          │          │ Workload │            │
├──────────┼──────────┼──────────┼──────────┼────────────┤
│ MFA      │ Health   │ Micro-   │ Runtime  │ Classifi-  │
│ SSO      │ Posture  │ segment  │ Integrity│ cation     │
│ RBAC     │ MDM      │ mTLS     │ SBOM     │ Encryption │
│ JIT      │ Zero-day │ East-West│ Secrets  │ DLP        │
│ Access   │ Patching │ Controls │ Mgmt     │ Masking    │
└──────────┴──────────┴──────────┴──────────┴────────────┘
```

#### Zero Trust vs Perimeter Security

| Aspect | Perimeter Security | Zero Trust |
|---|---|---|
| Trust model | Trust inside, verify outside | Never trust, always verify |
| Network access | VPN = full access | Per-resource access |
| Lateral movement | Easy once inside | Blocked by micro-segmentation |
| Authentication | Once at perimeter | Continuous, per request |
| Data protection | Network boundary | Data-centric, everywhere |

### Security Interview Questions

1. **Design a secure API authentication system for a multi-tenant SaaS platform**
   - How do you isolate tenant data? Token structure? Key rotation?
   - How do you handle compromised credentials at scale?

2. **Implement OAuth 2.0 + PKCE flow for a mobile application**
   - Why not implicit flow? How do you handle token refresh?
   - What happens when refresh tokens are stolen?

3. **Design a secrets management system for 500+ microservices**
   - Dynamic vs static secrets? Rotation strategy? Emergency revocation?
   - How do you audit secret access? Handle leaked secrets?

4. **Explain how to prevent and detect SSRF in a cloud environment**
   - What is the metadata service attack? Network-level vs application-level mitigations?
   - How do you handle user-provided URLs safely?

5. **Design a zero-trust architecture for a hybrid cloud deployment**
   - How do you authenticate service-to-service calls? Handle legacy systems?
   - What is the identity provider architecture? Network segmentation strategy?

6. **How would you implement field-level encryption for PII data?**
   - Key management? Searchable encryption? Performance impact?
   - How do you handle key rotation with encrypted data at rest?

7. **Design a WAF rule set for an API that accepts user-generated content**
   - How do you balance security with false positives?
   - What are the bypass techniques and how do you mitigate them?

8. **Explain mTLS certificate lifecycle management for a Kubernetes cluster**
   - Certificate issuance? Rotation? Revocation? Trust chain?
   - What happens when the CA is compromised?

9. **Design a comprehensive API rate limiting and abuse prevention system**
   - Multiple dimensions (user, IP, endpoint)? Distributed coordination?
   - How do you handle legitimate traffic spikes vs attacks?

10. **How do you implement secure multi-tenancy in a shared database?**
    - Row-level security? Schema isolation? Connection pooling?
    - How do you prevent cross-tenant data leakage?

---

## 16.12 Rate Limiting & Resilience Patterns

### Rate Limiting Algorithms

#### Token Bucket

```
┌─────────────────────────────────────────┐
│            Token Bucket                  │
│                                         │
│  Capacity: 10 tokens                    │
│  Refill Rate: 2 tokens/second           │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │ [●][●][●][●][●][●][ ][ ][ ][ ] │    │
│  │  6 tokens available              │    │
│  └─────────────────────────────────┘    │
│                                         │
│  Request arrives:                       │
│  - Token available → consume, allow     │
│  - No token → reject (429)             │
│                                         │
│  Allows bursts up to bucket capacity    │
└─────────────────────────────────────────┘
```

**Characteristics:**
- Allows burst traffic up to bucket size
- Smooth long-term rate enforcement
- Memory: O(1) per key (counter + timestamp)
- Used by: AWS API Gateway, Stripe

#### Leaky Bucket

```
┌─────────────────────────────────────────┐
│            Leaky Bucket                  │
│                                         │
│  Queue Size: 10 requests                │
│  Drain Rate: 2 requests/second          │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │ [R][R][R][R][R][ ][ ][ ][ ][ ] │    │
│  │  5 requests queued               │    │
│  └──────────────────────────┬──────┘    │
│                             │ drain     │
│                             ▼           │
│                     Process at fixed    │
│                     rate (2 req/s)      │
│                                         │
│  Queue full → reject (429)              │
│  Enforces strict output rate            │
└─────────────────────────────────────────┘
```

**Characteristics:**
- Strict constant output rate (no bursts)
- Smooths traffic shape completely
- Memory: O(1) per key (queue pointer + timestamp)
- Used by: Nginx (`limit_req`), network traffic shaping

#### Sliding Window Log

```
┌─────────────────────────────────────────┐
│        Sliding Window Log               │
│                                         │
│  Window: 60 seconds                     │
│  Limit: 100 requests                    │
│                                         │
│  Timestamps: [t1, t2, t3, ..., t87]    │
│                                         │
│  On request at time T:                  │
│  1. Remove entries where ts < T - 60s   │
│  2. Count remaining entries             │
│  3. If count < 100 → add T, allow      │
│  4. If count >= 100 → reject (429)     │
│                                         │
│  Memory: O(n) per key (all timestamps)  │
│  Most accurate but memory intensive     │
└─────────────────────────────────────────┘
```

#### Sliding Window Counter

```
┌─────────────────────────────────────────┐
│      Sliding Window Counter             │
│                                         │
│  Window: 60 seconds, Limit: 100        │
│  Current window: 40 requests            │
│  Previous window: 80 requests           │
│  Position in current window: 25%        │
│                                         │
│  Weighted count =                       │
│    current + previous × (1 - position)  │
│    40 + 80 × 0.75 = 100               │
│                                         │
│  100 >= limit → reject (429)           │
│                                         │
│  Memory: O(1) per key (2 counters)     │
│  Approximate but memory efficient       │
└─────────────────────────────────────────┘
```

#### Fixed Window Counter

```
┌─────────────────────────────────────────┐
│        Fixed Window Counter             │
│                                         │
│  Window: 60 seconds, Limit: 100        │
│                                         │
│  ┌──────────┐  ┌──────────┐            │
│  │ Window 1 │  │ Window 2 │            │
│  │ 0:00-1:00│  │ 1:00-2:00│            │
│  │ Count: 95│  │ Count: 23│            │
│  └──────────┘  └──────────┘            │
│                                         │
│  Problem: boundary burst                │
│  50 req at 0:59 + 50 req at 1:01       │
│  = 100 req in 2 seconds (passes!)      │
│                                         │
│  Memory: O(1) per key (counter)         │
│  Simple but has edge case at boundary   │
└─────────────────────────────────────────┘
```

#### Algorithm Comparison

| Algorithm | Burst Handling | Memory | Accuracy | Complexity |
|---|---|---|---|---|
| Token Bucket | Allows controlled bursts | O(1) | High | Low |
| Leaky Bucket | No bursts (strict rate) | O(1) | High | Low |
| Fixed Window | Boundary burst problem | O(1) | Low | Very Low |
| Sliding Window Log | No bursts | O(n) | Exact | Medium |
| Sliding Window Counter | Minimal boundary issue | O(1) | Approximate | Low |

### Distributed Rate Limiting

#### Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Server 1 │     │ Server 2 │     │ Server 3 │
└────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │
     └────────────────┼────────────────┘
                      │
              ┌───────▼───────┐
              │  Redis Cluster │
              │               │
              │  MULTI        │
              │  INCR key     │
              │  EXPIRE key   │
              │  EXEC         │
              └───────────────┘
```

#### Redis Lua Script for Sliding Window

```lua
-- Sliding window rate limiter in Redis
local key = KEYS[1]
local window = tonumber(ARGV[1])  -- window size in ms
local limit = tonumber(ARGV[2])   -- max requests
local now = tonumber(ARGV[3])     -- current timestamp ms

-- Remove expired entries
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- Count current entries
local count = redis.call('ZCARD', key)

if count < limit then
    -- Allow: add current timestamp
    redis.call('ZADD', key, now, now .. '-' .. math.random())
    redis.call('PEXPIRE', key, window)
    return {1, limit - count - 1}  -- allowed, remaining
else
    return {0, 0}  -- denied, remaining
end
```

#### Multi-Dimensional Rate Limiting

| Dimension | Limit | Purpose |
|---|---|---|
| Per User | 1000 req/min | Fair usage per account |
| Per IP | 100 req/min | Prevent anonymous abuse |
| Per Endpoint | 50 req/min | Protect expensive operations |
| Per Tenant | 10000 req/min | SaaS plan enforcement |
| Global | 100000 req/min | System protection |

### Circuit Breaker Pattern

#### State Machine

```
                 failure threshold
                    exceeded
    ┌──────────┐ ──────────────▶ ┌──────────┐
    │  CLOSED  │                 │   OPEN   │
    │          │ ◀────────────── │          │
    └──────────┘   reset after   └──────────┘
         ▲         success            │
         │                            │ timeout
         │                            │ expires
         │    ┌───────────────┐       │
         └────│  HALF-OPEN    │◀──────┘
   success    │               │
              │ (allow 1 req) │
              └───────────────┘
                    │
                    │ failure
                    ▼
              Back to OPEN
```

#### Circuit Breaker Configuration

| Parameter | Typical Value | Purpose |
|---|---|---|
| Failure Threshold | 5 failures in 60s | When to open circuit |
| Success Threshold | 3 consecutive | When to close from half-open |
| Timeout | 30-60 seconds | How long to stay open |
| Half-Open Max | 1-3 requests | Probe requests in half-open |
| Failure Types | 5xx, timeouts, connection errors | What counts as failure |
| Excluded | 4xx (client errors) | What does NOT count |

#### Circuit Breaker vs Retry

| Aspect | Retry | Circuit Breaker |
|---|---|---|
| Purpose | Handle transient failures | Prevent cascade failures |
| Behavior | Retry N times with backoff | Fail fast when service is down |
| Best for | Occasional failures | Sustained outages |
| Risk | Amplifies load on failing service | May reject during recovery |
| Combination | Retry inside circuit breaker | Open circuit after retries exhaust |

### Bulkhead Pattern

```
┌─────────────────────────────────────────────────────────┐
│                   Service Instance                       │
│                                                         │
│  ┌─────────────────┐  ┌─────────────────┐             │
│  │  Payment Pool   │  │  Catalog Pool   │             │
│  │  Max: 20 threads│  │  Max: 50 threads│             │
│  │  Queue: 10      │  │  Queue: 30      │             │
│  │                 │  │                 │             │
│  │  [████████░░]   │  │  [██████░░░░]   │             │
│  │  16/20 active   │  │  30/50 active   │             │
│  └─────────────────┘  └─────────────────┘             │
│                                                         │
│  Payment failure does NOT affect Catalog availability   │
└─────────────────────────────────────────────────────────┘
```

#### Bulkhead Types

| Type | Isolation | Use Case | Implementation |
|---|---|---|---|
| Thread Pool | Thread-level | Blocking I/O calls | Separate thread pools per dependency |
| Semaphore | Concurrency limit | Async/non-blocking | Counting semaphore per dependency |
| Process | Process-level | Critical workloads | Separate container/pod per dependency |
| Connection Pool | Connection-level | Database/HTTP | Dedicated pools per downstream |

### Resilience Pattern Combinations

```
┌─────────────────────────────────────────────────────────┐
│                Request Flow                             │
│                                                         │
│  Client                                                 │
│    │                                                    │
│    ▼                                                    │
│  [Timeout] ─── 5s max wait                             │
│    │                                                    │
│    ▼                                                    │
│  [Bulkhead] ─── max 20 concurrent                      │
│    │                                                    │
│    ▼                                                    │
│  [Circuit Breaker] ─── fail fast if open               │
│    │                                                    │
│    ▼                                                    │
│  [Retry] ─── 3 attempts, exponential backoff           │
│    │                                                    │
│    ▼                                                    │
│  [Rate Limiter] ─── respect downstream limits          │
│    │                                                    │
│    ▼                                                    │
│  Downstream Service                                     │
└─────────────────────────────────────────────────────────┘

Order matters: Timeout > Bulkhead > Circuit Breaker > Retry > Rate Limit
```

### Back-Pressure Mechanisms

| Mechanism | Implementation | When to Use |
|---|---|---|
| Load Shedding | Return 503 when queue > threshold | Protect from overload |
| Throttling | Delay responses progressively | Gradual degradation |
| Admission Control | Reject low-priority requests | Under resource pressure |
| Queue Limits | Bounded queues with rejection | Prevent memory exhaustion |
| Flow Control | TCP/gRPC window-based | Stream processing |
| Priority Queues | Process critical requests first | Mixed-priority traffic |

### Graceful Degradation Strategies

| Strategy | Description | Example |
|---|---|---|
| Feature Flags | Disable non-critical features | Turn off recommendations during peak |
| Fallback Data | Return cached/stale data | Show cached search results |
| Reduced Quality | Lower resolution/precision | Smaller images, approximate counts |
| Queue Deferral | Defer non-urgent work | Batch emails instead of real-time |
| Static Content | Serve pre-rendered pages | Static product pages during outage |
| Read-Only Mode | Disable writes | Allow browsing, block purchases |

### Chaos Engineering

#### Principles

| Principle | Description |
|---|---|
| Build Hypothesis | Define steady-state behavior and expected impact |
| Vary Real-World Events | Inject failures that could actually happen |
| Run in Production | Staging cannot replicate production complexity |
| Minimize Blast Radius | Start small, automated rollback, kill switch |
| Automate Experiments | Run continuously as part of CI/CD |

#### Chaos Tools

| Tool | Focus | Key Features |
|---|---|---|
| Chaos Monkey | Instance failure | Random instance termination |
| Litmus | Kubernetes | CRD-based, GitOps native |
| Gremlin | Enterprise | Attack catalog, gamedays, safety |
| Toxiproxy | Network | Latency, bandwidth, connection issues |
| Chaos Mesh | Kubernetes | Pod, network, I/O, time chaos |

### Rate Limiting & Resilience Interview Questions

1. **Design a distributed rate limiter for a global API serving 1M req/s**
   - How do you handle cross-region coordination?
   - What happens when Redis is unavailable? Local fallback?

2. **Implement a circuit breaker for a payment gateway integration**
   - What metrics trigger the open state? How do you handle partial failures?
   - How do you test the circuit breaker in production?

3. **Design a multi-tier rate limiting system (user → tenant → global)**
   - How do you handle limit inheritance? Priority overrides?
   - What is the race condition risk and how do you solve it?

4. **Explain how you would implement back-pressure in an event-driven system**
   - How does Kafka consumer lag signal back-pressure?
   - What is the relationship between partition count and back-pressure?

5. **Design a load shedding strategy for a system with mixed-priority traffic**
   - How do you classify requests? What signals determine shed priority?
   - How do you prevent priority inversion?

6. **Implement graceful degradation for an e-commerce checkout during Black Friday**
   - What features can be safely degraded? In what order?
   - How do you monitor degradation and auto-recover?

7. **Compare token bucket vs sliding window for API rate limiting**
   - When would you choose one over the other?
   - How does each handle burst traffic differently?

8. **Design a chaos engineering program for a microservices platform**
   - How do you start? What are the first experiments?
   - How do you prevent chaos experiments from causing real outages?

9. **Implement retry with exponential backoff and jitter for a distributed system**
   - Why is jitter important? Full vs decorrelated jitter?
   - How do you prevent retry storms across multiple clients?

10. **Design a bulkhead pattern for a service calling 10 downstream dependencies**
    - How do you size each bulkhead? What signals drive resizing?
    - How do you handle when multiple bulkheads are saturated simultaneously?

11. **How would you implement adaptive rate limiting that adjusts based on system load?**
    - What metrics drive the adaptation? CPU, queue depth, latency?
    - How do you prevent oscillation in the adaptive algorithm?

12. **Design an end-to-end resilience testing strategy for pre-production validation**
    - Load testing vs chaos testing vs fault injection?
    - How do you establish performance baselines and detect regressions?


# 17. Master Capstone Project

## Project: Production-Grade Event-Driven Commerce Platform

### Services

- API Gateway.
- Auth Service.
- User Service.
- Catalog Service.
- Cart Service.
- Inventory Service.
- Order Service.
- Payment Service.
- Shipment Service.
- Notification Service.
- Search Service.
- Recommendation Service.
- Analytics Service.
- Admin Service.

### Databases and Platforms

- PostgreSQL for transactional services.
- SQL Server optional for enterprise comparison.
- MongoDB for document catalog or content modeling.
- ScyllaDB for high-scale activity/event lookup experiments.
- Aerospike or Redis for low-latency profile/session/cache experiments.
- RocksDB for embedded state store experiments.
- Kafka for events.
- Redis for caching and rate limiting.
- Elasticsearch/OpenSearch for search.
- ClickHouse or Pinot for real-time analytics.
- Redshift/Snowflake/BigQuery-style warehouse for BI.
- Object storage + Iceberg/Delta/Hudi for lakehouse.

### Patterns to Implement

- Database per service.
- Transactional outbox.
- Inbox deduplication.
- Saga.
- CQRS read models.
- Event-carried state transfer.
- Idempotency keys.
- Retry with backoff and jitter.
- Circuit breaker.
- Bulkhead.
- Rate limiting.
- Cache-aside.
- DLQ.
- Schema registry.
- API gateway.
- BFF.
- Service discovery.
- Load balancing.
- CDN.
- OpenTelemetry tracing.
- Prometheus/Grafana dashboards.
- Kubernetes deployment.
- GitOps.
- Canary releases.
- Expand-contract migrations.

### Required Documents

- Business requirements.
- Non-functional requirements.
- Capacity plan.
- C4 context diagram.
- C4 container diagram.
- Service boundaries document.
- API contracts.
- Event contracts.
- Database schema.
- Sharding/partitioning plan.
- Caching plan.
- Failure-mode analysis.
- Security threat model.
- SLO document.
- Runbook.
- ADRs.
- Deployment diagram.
- Migration plan.
- Postmortem from simulated incident.

---

# 18. Weekly Aggressive Study Plan

## Daily 5-Hour Plan

| Time | Activity |
| --- | --- |
| 60 minutes | DSA pattern practice. |
| 60 minutes | Deep concept study. |
| 90 minutes | HLD or LLD design practice. |
| 60 minutes | Capstone coding/deployment/observability work. |
| 30 minutes | Notes, diagrams, and ADRs. |
| 20 minutes | Speak one concept aloud as interview practice. |

## Weekly Deliverables

- 5 DSA problems.
- 1 LLD design.
- 1 system design.
- 1 database deep dive.
- 1 distributed-systems concept lab.
- 1 microservice/event-driven implementation.
- 1 Kubernetes/deployment improvement.
- 1 observability dashboard or alert.
- 1 ADR.
- 1 mock interview recording.

---


# 19. Top Interview Problems and Practice Questions

---

## Top 50 System Design Interview Problems

### Social Media & Feed Systems
| # | Problem | Key Concepts |
|---|---------|--------------|
| 1 | Design Twitter/X | Fan-out, timeline service, celebrity problem, eventual consistency |
| 2 | Design Instagram | Photo storage, CDN, news feed ranking, stories |
| 3 | Design Facebook News Feed | Edge ranking, pull vs push, ML ranking, caching |
| 4 | Design LinkedIn | Graph database, connection degrees, feed relevance |
| 5 | Design TikTok | Video processing pipeline, recommendation engine, CDN |
| 6 | Design Reddit | Voting system, subreddit sharding, hot/top/new ranking |
| 7 | Design Pinterest | Image search, pin boards, recommendation, crawling |
| 8 | Design Quora | Question deduplication, topic graph, expert routing |

### Messaging & Real-Time Communication
| # | Problem | Key Concepts |
|---|---------|--------------|
| 9 | Design WhatsApp | End-to-end encryption, message queues, delivery receipts |
| 10 | Design Slack | Channels, workspace isolation, real-time sync, search |
| 11 | Design Discord | Voice channels, WebRTC, presence, server sharding |
| 12 | Design Facebook Messenger | Online status, group chat, media sharing |
| 13 | Design Zoom | Video conferencing, SFU vs MCU, screen sharing |
| 14 | Design a Notification System | Push/email/SMS, priority queues, rate limiting, templates |
| 15 | Design a Chat System with Online Presence | Heartbeat, WebSocket, fanout of presence updates |

### Storage & File Systems
| # | Problem | Key Concepts |
|---|---------|--------------|
| 16 | Design Google Drive | File sync, chunking, conflict resolution, versioning |
| 17 | Design Dropbox | Block-level dedup, delta sync, client-server protocol |
| 18 | Design a Distributed File System (GFS) | Chunk servers, master, replication, consistency |
| 19 | Design an Object Storage (S3) | Metadata service, erasure coding, multipart upload |
| 20 | Design a Key-Value Store | Consistent hashing, replication, vector clocks |
| 21 | Design a Distributed Cache (Memcached/Redis) | Eviction, partitioning, cache aside, write-through |

### Streaming & Content Delivery
| # | Problem | Key Concepts |
|---|---------|--------------|
| 22 | Design YouTube | Video transcoding, adaptive bitrate, CDN, recommendations |
| 23 | Design Netflix | Content delivery, microservices, chaos engineering |
| 24 | Design Spotify | Audio streaming, playlist service, offline mode |
| 25 | Design a Live Streaming Platform (Twitch) | RTMP ingest, HLS/DASH, low-latency delivery |
| 26 | Design a CDN | Edge caching, origin shield, cache invalidation, DNS routing |

### E-Commerce & Marketplace
| # | Problem | Key Concepts |
|---|---------|--------------|
| 27 | Design Amazon | Product catalog, cart, inventory, order pipeline |
| 28 | Design Uber/Lyft | Geospatial indexing, matching, surge pricing, ETA |
| 29 | Design Airbnb | Search ranking, availability calendar, booking |
| 30 | Design a Payment System (Stripe) | Idempotency, ledger, PCI compliance, reconciliation |
| 31 | Design an Online Ticketing System (BookMyShow) | Seat locking, distributed transactions, fairness |
| 32 | Design a Food Delivery System (DoorDash) | Real-time tracking, dispatch optimization, ETA |
| 33 | Design an Auction System (eBay) | Bidding engine, sniping protection, consistency |

### Infrastructure & Platform
| # | Problem | Key Concepts |
|---|---------|--------------|
| 34 | Design a URL Shortener (bit.ly) | Hashing, base62, redirection, analytics |
| 35 | Design a Web Crawler | Politeness, URL frontier, deduplication, distributed crawling |
| 36 | Design a Search Engine (Google) | Inverted index, PageRank, query parsing, ranking |
| 37 | Design a Rate Limiter | Token bucket, sliding window, distributed rate limiting |
| 38 | Design a Unique ID Generator (Snowflake) | Clock sync, datacenter ID, sequence numbers |
| 39 | Design a Task Scheduler | Priority queues, cron, distributed locking, at-least-once |
| 40 | Design an API Gateway | Routing, auth, rate limiting, circuit breaker |
| 41 | Design a Load Balancer | L4 vs L7, health checks, consistent hashing, sticky sessions |
| 42 | Design a Metrics/Monitoring System (Datadog) | Time-series DB, aggregation, alerting, dashboards |
| 43 | Design a Logging System (ELK/Splunk) | Log ingestion, indexing, search, retention |
| 44 | Design a Distributed Message Queue (Kafka) | Partitions, consumer groups, ordering, exactly-once |
| 45 | Design Google Maps | Tile serving, routing algorithms, real-time traffic |
| 46 | Design Typeahead/Autocomplete | Trie, prefix matching, ranking, personalization |
| 47 | Design a Collaborative Editor (Google Docs) | CRDT/OT, conflict resolution, cursor sync |
| 48 | Design Pastebin | Object storage, expiration, access control |
| 49 | Design a Proximity Service (Yelp) | Geohash, quadtree, spatial indexing |
| 50 | Design a Distributed Lock Service (Chubby/ZooKeeper) | Consensus, fencing tokens, lease-based locking |

---

## Top 50 LLD/OOD Interview Problems

### Games & Entertainment
| # | Problem | Key Focus |
|---|---------|-----------|
| 1 | Design Chess | Board representation, move validation, check/checkmate detection |
| 2 | Design Tic-Tac-Toe | Game state, win detection, AI opponent |
| 3 | Design Snake and Ladders | Board generation, dice, player turns |
| 4 | Design a Deck of Cards | Shuffle algorithm, inheritance, dealing |
| 5 | Design Minesweeper | Grid reveal (BFS/DFS), mine placement, flagging |
| 6 | Design Tetris | Piece rotation, collision detection, line clearing |
| 7 | Design Snakes Game | Deque for body, food generation, collision |
| 8 | Design a Sudoku Solver | Backtracking, constraint validation |
| 9 | Design Battleship | Ship placement, hit/miss tracking, game phases |
| 10 | Design a Card Game (Blackjack/Poker) | Hand evaluation, betting rounds, dealer logic |

### Systems & Infrastructure
| # | Problem | Key Focus |
|---|---------|-----------|
| 11 | Design a Parking Lot | Vehicle types, spot allocation, pricing strategy |
| 12 | Design an Elevator System | Scheduling algorithms (SCAN, LOOK), multi-elevator coordination |
| 13 | Design a Vending Machine | State machine, inventory, payment handling |
| 14 | Design a Traffic Signal System | State transitions, timing, pedestrian crossing |
| 15 | Design an ATM | Transaction types, concurrency, receipt generation |
| 16 | Design a Hotel Booking System | Room types, availability, reservation management |
| 17 | Design an Airline Reservation System | Seat selection, flight search, booking pipeline |
| 18 | Design a Library Management System | Catalog, borrowing, fines, reservations |
| 19 | Design a Movie Ticket Booking System | Show scheduling, seat locking, payment |
| 20 | Design a Car Rental System | Vehicle fleet, pricing, pickup/return |

### Applications & Platforms
| # | Problem | Key Focus |
|---|---------|-----------|
| 21 | Design an Online Shopping Cart | Item management, pricing rules, checkout flow |
| 22 | Design a Food Ordering System | Restaurant menu, order tracking, delivery assignment |
| 23 | Design Stack Overflow | Questions, answers, voting, reputation, tags |
| 24 | Design a Social Network (Facebook) | User profiles, friendships, posts, news feed |
| 25 | Design a File System | Directories, files, permissions, path resolution |
| 26 | Design a Spreadsheet (Excel) | Cell dependencies, formula evaluation, circular detection |
| 27 | Design a Text Editor | Buffer (rope/gap buffer), cursor, undo/redo |
| 28 | Design a Logger/Logging Framework | Log levels, handlers, formatters, rotation |
| 29 | Design a Cache (LRU/LFU) | Eviction policies, HashMap + DLL, thread safety |
| 30 | Design a Pub-Sub System | Topics, subscribers, message delivery, filtering |

### Design Patterns & Utilities
| # | Problem | Key Focus |
|---|---------|-----------|
| 31 | Design a Rate Limiter | Token bucket, sliding window, decorator pattern |
| 32 | Design a Task Scheduler (Cron) | Job scheduling, priority queue, recurring tasks |
| 33 | Design a Connection Pool | Resource management, health checks, timeout |
| 34 | Design an In-Memory Database | Data structures, indexing, transactions |
| 35 | Design a URL Shortener | Encoding, storage, analytics, redirect |
| 36 | Design a Hash Map | Collision handling, resizing, load factor |
| 37 | Design a Thread Pool | Worker threads, task queue, graceful shutdown |
| 38 | Design a Retry Mechanism | Exponential backoff, jitter, circuit breaker |
| 39 | Design an Event Bus | Event routing, handler registration, async dispatch |
| 40 | Design a Notification Service | Channel routing, templates, priority, batching |

### Domain-Specific
| # | Problem | Key Focus |
|---|---------|-----------|
| 41 | Design a Ride-Sharing Service (OOD) | Matching, pricing, trip lifecycle |
| 42 | Design a Hospital Management System | Patients, doctors, appointments, billing |
| 43 | Design a Music Player | Playlist management, playback controls, queue |
| 44 | Design a Calendar Application | Events, recurring events, conflict detection |
| 45 | Design an Inventory Management System | Stock tracking, reorder points, warehouses |
| 46 | Design a Auction System (OOD) | Bidding, time constraints, winner determination |
| 47 | Design a Payment Processing System | Payment methods, refunds, reconciliation |
| 48 | Design a Restaurant Management System | Tables, orders, kitchen queue, billing |
| 49 | Design a Chat Application (OOD) | Messages, conversations, typing indicators |
| 50 | Design a Meeting Scheduler | Availability, room booking, conflict resolution |

---

## Top 20 LeetCode Problems Per DSA Category

### 1. Arrays
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Two Sum | 1 | Easy |
| 2 | Best Time to Buy and Sell Stock | 121 | Easy |
| 3 | Contains Duplicate | 217 | Easy |
| 4 | Product of Array Except Self | 238 | Medium |
| 5 | Maximum Subarray | 53 | Medium |
| 6 | Maximum Product Subarray | 152 | Medium |
| 7 | Find Minimum in Rotated Sorted Array | 153 | Medium |
| 8 | Search in Rotated Sorted Array | 33 | Medium |
| 9 | 3Sum | 15 | Medium |
| 10 | Container With Most Water | 11 | Medium |
| 11 | Next Permutation | 31 | Medium |
| 12 | Merge Intervals | 56 | Medium |
| 13 | Sort Colors | 75 | Medium |
| 14 | Subarray Sum Equals K | 560 | Medium |
| 15 | Rotate Array | 189 | Medium |
| 16 | Trapping Rain Water | 42 | Hard |
| 17 | First Missing Positive | 41 | Hard |
| 18 | Longest Consecutive Sequence | 128 | Medium |
| 19 | 4Sum | 18 | Medium |
| 20 | Median of Two Sorted Arrays | 4 | Hard |

### 2. Hash Maps
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Two Sum | 1 | Easy |
| 2 | Group Anagrams | 49 | Medium |
| 3 | Valid Anagram | 242 | Easy |
| 4 | Longest Substring Without Repeating Characters | 3 | Medium |
| 5 | Top K Frequent Elements | 347 | Medium |
| 6 | Contains Duplicate II | 219 | Easy |
| 7 | Subarray Sum Equals K | 560 | Medium |
| 8 | Isomorphic Strings | 205 | Easy |
| 9 | Word Pattern | 290 | Easy |
| 10 | Longest Consecutive Sequence | 128 | Medium |
| 11 | 4Sum II | 454 | Medium |
| 12 | Minimum Window Substring | 76 | Hard |
| 13 | Copy List with Random Pointer | 138 | Medium |
| 14 | Happy Number | 202 | Easy |
| 15 | Insert Delete GetRandom O(1) | 380 | Medium |
| 16 | First Unique Character in a String | 387 | Easy |
| 17 | Design HashMap | 706 | Easy |
| 18 | LRU Cache | 146 | Medium |
| 19 | Brick Wall | 554 | Medium |
| 20 | Encode and Decode TinyURL | 535 | Medium |

### 3. Two Pointers
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Valid Palindrome | 125 | Easy |
| 2 | Two Sum II - Input Array Is Sorted | 167 | Medium |
| 3 | 3Sum | 15 | Medium |
| 4 | Container With Most Water | 11 | Medium |
| 5 | Trapping Rain Water | 42 | Hard |
| 6 | Remove Duplicates from Sorted Array | 26 | Easy |
| 7 | Move Zeroes | 283 | Easy |
| 8 | Sort Colors | 75 | Medium |
| 9 | Boats to Save People | 881 | Medium |
| 10 | 3Sum Closest | 16 | Medium |
| 11 | Backspace String Compare | 844 | Easy |
| 12 | Squares of a Sorted Array | 977 | Easy |
| 13 | 4Sum | 18 | Medium |
| 14 | Remove Nth Node From End of List | 19 | Medium |
| 15 | Linked List Cycle | 141 | Easy |
| 16 | Palindrome Linked List | 234 | Easy |
| 17 | Merge Sorted Array | 88 | Easy |
| 18 | Intersection of Two Arrays II | 350 | Easy |
| 19 | Longest Mountain in Array | 845 | Medium |
| 20 | Partition Labels | 763 | Medium |

### 4. Sliding Window
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Best Time to Buy and Sell Stock | 121 | Easy |
| 2 | Longest Substring Without Repeating Characters | 3 | Medium |
| 3 | Longest Repeating Character Replacement | 424 | Medium |
| 4 | Permutation in String | 567 | Medium |
| 5 | Minimum Window Substring | 76 | Hard |
| 6 | Sliding Window Maximum | 239 | Hard |
| 7 | Minimum Size Subarray Sum | 209 | Medium |
| 8 | Fruit Into Baskets | 904 | Medium |
| 9 | Subarrays with K Different Integers | 992 | Hard |
| 10 | Maximum Number of Vowels in a Substring | 1456 | Medium |
| 11 | Get Equal Substrings Within Budget | 1208 | Medium |
| 12 | Max Consecutive Ones III | 1004 | Medium |
| 13 | Grumpy Bookstore Owner | 1052 | Medium |
| 14 | Find All Anagrams in a String | 438 | Medium |
| 15 | Substring with Concatenation of All Words | 30 | Hard |
| 16 | Minimum Operations to Reduce X to Zero | 1658 | Medium |
| 17 | Count Number of Nice Subarrays | 1248 | Medium |
| 18 | Longest Subarray of 1s After Deleting One Element | 1493 | Medium |
| 19 | Maximum Points You Can Obtain from Cards | 1423 | Medium |
| 20 | Frequency of the Most Frequent Element | 1838 | Medium |

### 5. Stacks
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Valid Parentheses | 20 | Easy |
| 2 | Min Stack | 155 | Medium |
| 3 | Evaluate Reverse Polish Notation | 150 | Medium |
| 4 | Daily Temperatures | 739 | Medium |
| 5 | Car Fleet | 853 | Medium |
| 6 | Largest Rectangle in Histogram | 84 | Hard |
| 7 | Generate Parentheses | 22 | Medium |
| 8 | Asteroid Collision | 735 | Medium |
| 9 | Basic Calculator | 224 | Hard |
| 10 | Basic Calculator II | 227 | Medium |
| 11 | Decode String | 394 | Medium |
| 12 | Remove All Adjacent Duplicates in String II | 1209 | Medium |
| 13 | Trapping Rain Water | 42 | Hard |
| 14 | Next Greater Element I | 496 | Easy |
| 15 | Next Greater Element II | 503 | Medium |
| 16 | Online Stock Span | 901 | Medium |
| 17 | Simplify Path | 71 | Medium |
| 18 | Remove K Digits | 402 | Medium |
| 19 | Maximal Rectangle | 85 | Hard |
| 20 | Longest Valid Parentheses | 32 | Hard |

### 6. Queues
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Implement Queue using Stacks | 232 | Easy |
| 2 | Implement Stack using Queues | 225 | Easy |
| 3 | Number of Recent Calls | 933 | Easy |
| 4 | Design Circular Queue | 622 | Medium |
| 5 | Sliding Window Maximum | 239 | Hard |
| 6 | Rotting Oranges | 994 | Medium |
| 7 | Walls and Gates | 286 | Medium |
| 8 | Number of Islands | 200 | Medium |
| 9 | Open the Lock | 752 | Medium |
| 10 | Shortest Path in Binary Matrix | 1091 | Medium |
| 11 | Jump Game III | 1306 | Medium |
| 12 | Design Hit Counter | 362 | Medium |
| 13 | Moving Average from Data Stream | 346 | Easy |
| 14 | Snakes and Ladders | 909 | Medium |
| 15 | Perfect Squares | 279 | Medium |
| 16 | Word Ladder | 127 | Hard |
| 17 | Minimum Knight Moves | 1197 | Medium |
| 18 | Shortest Bridge | 934 | Medium |
| 19 | Bus Routes | 815 | Hard |
| 20 | Design Circular Deque | 641 | Medium |

### 7. Heaps / Priority Queues
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Kth Largest Element in an Array | 215 | Medium |
| 2 | Top K Frequent Elements | 347 | Medium |
| 3 | Find Median from Data Stream | 295 | Hard |
| 4 | Merge k Sorted Lists | 23 | Hard |
| 5 | Task Scheduler | 621 | Medium |
| 6 | K Closest Points to Origin | 973 | Medium |
| 7 | Reorganize String | 767 | Medium |
| 8 | Sort Characters By Frequency | 451 | Medium |
| 9 | Kth Smallest Element in a Sorted Matrix | 378 | Medium |
| 10 | Last Stone Weight | 1046 | Easy |
| 11 | Ugly Number II | 264 | Medium |
| 12 | Meeting Rooms II | 253 | Medium |
| 13 | Smallest Range Covering Elements from K Lists | 632 | Hard |
| 14 | IPO | 502 | Hard |
| 15 | Find K Pairs with Smallest Sums | 373 | Medium |
| 16 | Furthest Building You Can Reach | 1642 | Medium |
| 17 | Sliding Window Median | 480 | Hard |
| 18 | Maximum Performance of a Team | 1383 | Hard |
| 19 | Minimum Cost to Hire K Workers | 857 | Hard |
| 20 | Design Twitter | 355 | Medium |

### 8. Binary Search
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Binary Search | 704 | Easy |
| 2 | Search in Rotated Sorted Array | 33 | Medium |
| 3 | Find Minimum in Rotated Sorted Array | 153 | Medium |
| 4 | Search a 2D Matrix | 74 | Medium |
| 5 | Koko Eating Bananas | 875 | Medium |
| 6 | Find Peak Element | 162 | Medium |
| 7 | Median of Two Sorted Arrays | 4 | Hard |
| 8 | Time Based Key-Value Store | 981 | Medium |
| 9 | Search in Rotated Sorted Array II | 81 | Medium |
| 10 | Find First and Last Position of Element in Sorted Array | 34 | Medium |
| 11 | Capacity To Ship Packages Within D Days | 1011 | Medium |
| 12 | Split Array Largest Sum | 410 | Hard |
| 13 | Minimum Number of Days to Make m Bouquets | 1482 | Medium |
| 14 | Aggressive Cows (Binary Search on Answer) | — | Medium |
| 15 | Sqrt(x) | 69 | Easy |
| 16 | Single Element in a Sorted Array | 540 | Medium |
| 17 | Search Insert Position | 35 | Easy |
| 18 | Magnetic Force Between Two Balls | 1552 | Medium |
| 19 | Longest Increasing Subsequence (Binary Search) | 300 | Medium |
| 20 | Russian Doll Envelopes | 354 | Hard |

### 9. Intervals
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Merge Intervals | 56 | Medium |
| 2 | Insert Interval | 57 | Medium |
| 3 | Non-overlapping Intervals | 435 | Medium |
| 4 | Meeting Rooms | 252 | Easy |
| 5 | Meeting Rooms II | 253 | Medium |
| 6 | Minimum Number of Arrows to Burst Balloons | 452 | Medium |
| 7 | Interval List Intersections | 986 | Medium |
| 8 | Employee Free Time | 759 | Hard |
| 9 | Remove Covered Intervals | 1288 | Medium |
| 10 | My Calendar I | 729 | Medium |
| 11 | My Calendar II | 731 | Medium |
| 12 | Car Pooling | 1094 | Medium |
| 13 | Minimum Interval to Include Each Query | 1851 | Hard |
| 14 | Data Stream as Disjoint Intervals | 352 | Hard |
| 15 | Summary Ranges | 228 | Easy |
| 16 | Teemo Attacking | 495 | Easy |
| 17 | Video Stitching | 1024 | Medium |
| 18 | Maximum Length of Pair Chain | 646 | Medium |
| 19 | Add Bold Tag in String | 616 | Medium |
| 20 | Range Module | 715 | Hard |

### 10. Linked Lists
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Reverse Linked List | 206 | Easy |
| 2 | Merge Two Sorted Lists | 21 | Easy |
| 3 | Linked List Cycle | 141 | Easy |
| 4 | Linked List Cycle II | 142 | Medium |
| 5 | Remove Nth Node From End of List | 19 | Medium |
| 6 | Reorder List | 143 | Medium |
| 7 | Add Two Numbers | 2 | Medium |
| 8 | Copy List with Random Pointer | 138 | Medium |
| 9 | LRU Cache | 146 | Medium |
| 10 | Merge k Sorted Lists | 23 | Hard |
| 11 | Reverse Nodes in k-Group | 25 | Hard |
| 12 | Palindrome Linked List | 234 | Easy |
| 13 | Flatten a Multilevel Doubly Linked List | 430 | Medium |
| 14 | Sort List | 148 | Medium |
| 15 | Intersection of Two Linked Lists | 160 | Easy |
| 16 | Odd Even Linked List | 328 | Medium |
| 17 | Swap Nodes in Pairs | 24 | Medium |
| 18 | Rotate List | 61 | Medium |
| 19 | Remove Duplicates from Sorted List II | 82 | Medium |
| 20 | Design Linked List | 707 | Medium |

### 11. Trees (Binary Trees)
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Maximum Depth of Binary Tree | 104 | Easy |
| 2 | Invert Binary Tree | 226 | Easy |
| 3 | Same Tree | 100 | Easy |
| 4 | Binary Tree Level Order Traversal | 102 | Medium |
| 5 | Subtree of Another Tree | 572 | Easy |
| 6 | Construct Binary Tree from Preorder and Inorder | 105 | Medium |
| 7 | Binary Tree Right Side View | 199 | Medium |
| 8 | Lowest Common Ancestor of a Binary Tree | 236 | Medium |
| 9 | Binary Tree Zigzag Level Order Traversal | 103 | Medium |
| 10 | Diameter of Binary Tree | 543 | Easy |
| 11 | Balanced Binary Tree | 110 | Easy |
| 12 | Path Sum III | 437 | Medium |
| 13 | Binary Tree Maximum Path Sum | 124 | Hard |
| 14 | Serialize and Deserialize Binary Tree | 297 | Hard |
| 15 | Count Good Nodes in Binary Tree | 1448 | Medium |
| 16 | Flatten Binary Tree to Linked List | 114 | Medium |
| 17 | Populating Next Right Pointers in Each Node | 116 | Medium |
| 18 | Vertical Order Traversal of a Binary Tree | 987 | Hard |
| 19 | Sum Root to Leaf Numbers | 129 | Medium |
| 20 | All Nodes Distance K in Binary Tree | 863 | Medium |

### 12. Binary Search Trees (BST)
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Validate Binary Search Tree | 98 | Medium |
| 2 | Kth Smallest Element in a BST | 230 | Medium |
| 3 | Lowest Common Ancestor of a BST | 235 | Medium |
| 4 | Convert Sorted Array to BST | 108 | Easy |
| 5 | Delete Node in a BST | 450 | Medium |
| 6 | Insert into a Binary Search Tree | 701 | Medium |
| 7 | Inorder Successor in BST | 285 | Medium |
| 8 | Binary Search Tree Iterator | 173 | Medium |
| 9 | Recover Binary Search Tree | 99 | Medium |
| 10 | Trim a Binary Search Tree | 669 | Medium |
| 11 | Range Sum of BST | 938 | Easy |
| 12 | Two Sum IV - Input is a BST | 653 | Easy |
| 13 | Closest Binary Search Tree Value | 270 | Easy |
| 14 | Serialize and Deserialize BST | 449 | Medium |
| 15 | Balance a Binary Search Tree | 1382 | Medium |
| 16 | Convert BST to Greater Tree | 538 | Medium |
| 17 | Unique Binary Search Trees | 96 | Medium |
| 18 | Unique Binary Search Trees II | 95 | Medium |
| 19 | Minimum Absolute Difference in BST | 530 | Easy |
| 20 | Contains Duplicate III | 220 | Hard |

### 13. Tries
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Implement Trie (Prefix Tree) | 208 | Medium |
| 2 | Design Add and Search Words Data Structure | 211 | Medium |
| 3 | Word Search II | 212 | Hard |
| 4 | Replace Words | 648 | Medium |
| 5 | Longest Word in Dictionary | 720 | Medium |
| 6 | Map Sum Pairs | 677 | Medium |
| 7 | Search Suggestions System | 1268 | Medium |
| 8 | Maximum XOR of Two Numbers in an Array | 421 | Medium |
| 9 | Palindrome Pairs | 336 | Hard |
| 10 | Stream of Characters | 1032 | Hard |
| 11 | Word Search | 79 | Medium |
| 12 | Longest Common Prefix | 14 | Easy |
| 13 | Extra Characters in a String | 2707 | Medium |
| 14 | Count Prefixes of a Given String | 2255 | Easy |
| 15 | Implement Magic Dictionary | 676 | Medium |
| 16 | Concatenated Words | 472 | Hard |
| 17 | Short Encoding of Words | 820 | Medium |
| 18 | Prefix and Suffix Search | 745 | Hard |
| 19 | Design File System | 1166 | Medium |
| 20 | Camelcase Matching | 1023 | Medium |

### 14. Graphs (BFS/DFS)
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Number of Islands | 200 | Medium |
| 2 | Clone Graph | 133 | Medium |
| 3 | Pacific Atlantic Water Flow | 417 | Medium |
| 4 | Course Schedule | 207 | Medium |
| 5 | Course Schedule II | 210 | Medium |
| 6 | Number of Connected Components in an Undirected Graph | 323 | Medium |
| 7 | Graph Valid Tree | 261 | Medium |
| 8 | Word Ladder | 127 | Hard |
| 9 | Surrounded Regions | 130 | Medium |
| 10 | Accounts Merge | 721 | Medium |
| 11 | Evaluate Division | 399 | Medium |
| 12 | Shortest Path in Binary Matrix | 1091 | Medium |
| 13 | All Paths From Source to Target | 797 | Medium |
| 14 | Redundant Connection | 684 | Medium |
| 15 | Is Graph Bipartite? | 785 | Medium |
| 16 | Minimum Height Trees | 310 | Medium |
| 17 | Reconstruct Itinerary | 332 | Hard |
| 18 | Alien Dictionary | 269 | Hard |
| 19 | Cheapest Flights Within K Stops | 787 | Medium |
| 20 | Making A Large Island | 827 | Hard |

### 15. Topological Sort
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Course Schedule | 207 | Medium |
| 2 | Course Schedule II | 210 | Medium |
| 3 | Alien Dictionary | 269 | Hard |
| 4 | Sequence Reconstruction | 444 | Medium |
| 5 | Minimum Height Trees | 310 | Medium |
| 6 | Parallel Courses | 1136 | Medium |
| 7 | Parallel Courses III | 2050 | Hard |
| 8 | Longest Increasing Path in a Matrix | 329 | Hard |
| 9 | Sort Items by Groups Respecting Dependencies | 1203 | Hard |
| 10 | Find All Possible Recipes from Supplies | 2115 | Medium |
| 11 | Build a Matrix With Conditions | 2392 | Hard |
| 12 | Course Schedule IV | 1462 | Medium |
| 13 | Loud and Rich | 851 | Medium |
| 14 | All Ancestors of a Node in a DAG | 2192 | Medium |
| 15 | Largest Color Value in a Directed Graph | 1857 | Hard |
| 16 | Detect Cycles in 2D Grid | 1559 | Medium |
| 17 | Find Eventual Safe States | 802 | Medium |
| 18 | Longest Path With Different Adjacent Characters | 2246 | Hard |
| 19 | Minimum Number of Semesters to Graduate | 1494 | Hard |
| 20 | Restricted Paths From First to Last Node | 1786 | Medium |

### 16. Shortest Path
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Network Delay Time (Dijkstra) | 743 | Medium |
| 2 | Cheapest Flights Within K Stops (Bellman-Ford) | 787 | Medium |
| 3 | Path With Minimum Effort | 1631 | Medium |
| 4 | Swim in Rising Water | 778 | Hard |
| 5 | Shortest Path in Binary Matrix | 1091 | Medium |
| 6 | Path with Maximum Probability | 1514 | Medium |
| 7 | Find the City With the Smallest Number of Neighbors (Floyd-Warshall) | 1334 | Medium |
| 8 | Shortest Path to Get All Keys | 864 | Hard |
| 9 | Minimum Cost to Make at Least One Valid Path | 1368 | Hard |
| 10 | Shortest Path Visiting All Nodes | 847 | Hard |
| 11 | Word Ladder | 127 | Hard |
| 12 | Sliding Puzzle | 773 | Hard |
| 13 | Minimum Obstacle Removal to Reach Corner | 2290 | Hard |
| 14 | Shortest Path in a Grid with Obstacles Elimination | 1293 | Hard |
| 15 | Design Graph With Shortest Path Calculator | 2642 | Hard |
| 16 | Number of Ways to Arrive at Destination | 1976 | Medium |
| 17 | Reachable Nodes In Subdivided Graph | 882 | Hard |
| 18 | Minimum Weighted Subgraph With Required Paths | 2203 | Hard |
| 19 | Second Minimum Time to Reach Destination | 2045 | Hard |
| 20 | The Maze II | 505 | Medium |

### 17. Union Find (Disjoint Set)
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Number of Connected Components in an Undirected Graph | 323 | Medium |
| 2 | Redundant Connection | 684 | Medium |
| 3 | Graph Valid Tree | 261 | Medium |
| 4 | Accounts Merge | 721 | Medium |
| 5 | Longest Consecutive Sequence | 128 | Medium |
| 6 | Number of Islands II | 305 | Hard |
| 7 | Surrounded Regions | 130 | Medium |
| 8 | Most Stones Removed with Same Row or Column | 947 | Medium |
| 9 | Satisfiability of Equality Equations | 990 | Medium |
| 10 | Connecting Cities With Minimum Cost (Kruskal) | 1135 | Medium |
| 11 | Number of Operations to Make Network Connected | 1319 | Medium |
| 12 | Smallest String With Swaps | 1202 | Medium |
| 13 | Swim in Rising Water | 778 | Hard |
| 14 | Regions Cut By Slashes | 959 | Medium |
| 15 | Remove Max Number of Edges to Keep Graph Fully Traversable | 1579 | Hard |
| 16 | Optimize Water Distribution in a Village | 1168 | Hard |
| 17 | Checking Existence of Edge Length Limited Paths | 1697 | Hard |
| 18 | Min Cost to Connect All Points | 1584 | Medium |
| 19 | Lexicographically Smallest Equivalent String | 1061 | Medium |
| 20 | Making A Large Island | 827 | Hard |

### 18. Backtracking
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Subsets | 78 | Medium |
| 2 | Subsets II | 90 | Medium |
| 3 | Permutations | 46 | Medium |
| 4 | Permutations II | 47 | Medium |
| 5 | Combination Sum | 39 | Medium |
| 6 | Combination Sum II | 40 | Medium |
| 7 | Palindrome Partitioning | 131 | Medium |
| 8 | Letter Combinations of a Phone Number | 17 | Medium |
| 9 | Word Search | 79 | Medium |
| 10 | N-Queens | 51 | Hard |
| 11 | N-Queens II | 52 | Hard |
| 12 | Sudoku Solver | 37 | Hard |
| 13 | Generate Parentheses | 22 | Medium |
| 14 | Combinations | 77 | Medium |
| 15 | Restore IP Addresses | 93 | Medium |
| 16 | Partition to K Equal Sum Subsets | 698 | Medium |
| 17 | Splitting a String Into Descending Consecutive Values | 1849 | Medium |
| 18 | Maximum Length of a Concatenated String with Unique Characters | 1239 | Medium |
| 19 | Word Break II | 140 | Hard |
| 20 | Expression Add Operators | 282 | Hard |

### 19. Dynamic Programming
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Climbing Stairs | 70 | Easy |
| 2 | House Robber | 198 | Medium |
| 3 | House Robber II | 213 | Medium |
| 4 | Longest Increasing Subsequence | 300 | Medium |
| 5 | Coin Change | 322 | Medium |
| 6 | Word Break | 139 | Medium |
| 7 | Longest Common Subsequence | 1143 | Medium |
| 8 | Unique Paths | 62 | Medium |
| 9 | Jump Game | 55 | Medium |
| 10 | Decode Ways | 91 | Medium |
| 11 | Partition Equal Subset Sum | 416 | Medium |
| 12 | Target Sum | 494 | Medium |
| 13 | Edit Distance | 72 | Medium |
| 14 | 0/1 Knapsack (classic) | — | Medium |
| 15 | Longest Palindromic Substring | 5 | Medium |
| 16 | Palindromic Substrings | 647 | Medium |
| 17 | Minimum Path Sum | 64 | Medium |
| 18 | Maximal Square | 221 | Medium |
| 19 | Best Time to Buy and Sell Stock with Cooldown | 309 | Medium |
| 20 | Burst Balloons | 312 | Hard |

### 20. Greedy
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Jump Game | 55 | Medium |
| 2 | Jump Game II | 45 | Medium |
| 3 | Gas Station | 134 | Medium |
| 4 | Hand of Straights | 846 | Medium |
| 5 | Merge Triplets to Form Target Triplet | 1899 | Medium |
| 6 | Partition Labels | 763 | Medium |
| 7 | Valid Parenthesis String | 678 | Medium |
| 8 | Task Scheduler | 621 | Medium |
| 9 | Minimum Number of Arrows to Burst Balloons | 452 | Medium |
| 10 | Non-overlapping Intervals | 435 | Medium |
| 11 | Maximum Subarray | 53 | Medium |
| 12 | Best Time to Buy and Sell Stock II | 122 | Medium |
| 13 | Candy | 135 | Hard |
| 14 | Lemonade Change | 860 | Easy |
| 15 | Queue Reconstruction by Height | 406 | Medium |
| 16 | Boats to Save People | 881 | Medium |
| 17 | Minimum Platforms (Train Station) | — | Medium |
| 18 | Assign Cookies | 455 | Easy |
| 19 | Reorganize String | 767 | Medium |
| 20 | Wiggle Subsequence | 376 | Medium |

### 21. Bit Manipulation
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Single Number | 136 | Easy |
| 2 | Number of 1 Bits | 191 | Easy |
| 3 | Counting Bits | 338 | Easy |
| 4 | Reverse Bits | 190 | Easy |
| 5 | Missing Number | 268 | Easy |
| 6 | Sum of Two Integers | 371 | Medium |
| 7 | Single Number II | 137 | Medium |
| 8 | Single Number III | 260 | Medium |
| 9 | Bitwise AND of Numbers Range | 201 | Medium |
| 10 | Power of Two | 231 | Easy |
| 11 | Subsets (bit masking) | 78 | Medium |
| 12 | Hamming Distance | 461 | Easy |
| 13 | Total Hamming Distance | 477 | Medium |
| 14 | Maximum XOR of Two Numbers in an Array | 421 | Medium |
| 15 | Complement of Base 10 Integer | 1009 | Easy |
| 16 | UTF-8 Validation | 393 | Medium |
| 17 | Minimum Flips to Make a OR b Equal to c | 1318 | Medium |
| 18 | Decode XORed Permutation | 1734 | Medium |
| 19 | Find the Duplicate Number (bit approach) | 287 | Medium |
| 20 | Maximum Product of Word Lengths | 318 | Medium |

---

# 20. Architect Interview Expansion Pack

Use this section to close the remaining gaps for serious architect interviews. The earlier roadmap teaches the foundation; this section adds the concrete depth interviewers expect when they push past buzzwords.

## 20.1 Java and JVM Deep Mastery

Architect-level Java knowledge is not only syntax. You must explain how Java behaves under load, during garbage collection, during lock contention, and during failure.

### JVM Memory and Runtime

- Heap: young generation, old generation, allocation rate, promotion, fragmentation.
- Stack: method frames, local variables, recursion risk, stack overflow.
- Metaspace: class metadata, classloader leaks, dynamic proxy generation.
- Direct memory: Netty, NIO buffers, off-heap caches, native memory tracking.
- Object layout: object header, mark word, compressed ordinary object pointers, alignment.
- Escape analysis: stack allocation and lock elimination opportunities.
- JIT compilation: warmup, profiling, inlining, deoptimization.
- Class loading: bootstrap, platform, application, custom classloaders.

### Garbage Collection

- Generational hypothesis and why allocation is cheap until it is not.
- G1: regions, evacuation, mixed collections, remembered sets, pause-time goals.
- ZGC and Shenandoah concepts: low-pause concurrent compaction.
- Parallel GC vs G1 vs ZGC trade-offs.
- Stop-the-world pauses, safepoints, allocation stalls, promotion failures.
- GC tuning inputs: latency SLO, allocation rate, live-set size, heap size, CPU budget.
- Debugging: GC logs, Java Flight Recorder, heap dumps, allocation profiling.
- Interview rule: always connect GC choice to latency, throughput, memory cost, and operational risk.

### Java Memory Model and Concurrency

- Happens-before relationships.
- Visibility vs atomicity vs ordering.
- `volatile`: visibility and ordering, not compound atomicity.
- `synchronized`: monitor lock, reentrancy, visibility guarantees.
- `ReentrantLock`: explicit lock control, fairness, `tryLock`, interruptible lock waits.
- `ReadWriteLock` and `StampedLock`: read-heavy optimization with complexity trade-offs.
- `AtomicInteger`, `AtomicLong`, `AtomicReference`: CAS and lock-free updates.
- `LongAdder`: high-contention counters through striping.
- `ThreadLocal`: request context and leak risks in pools.
- ExecutorService: bounded queues, rejection policies, graceful shutdown.
- ForkJoinPool: work stealing and CPU-bound parallelism.
- CompletableFuture: async composition, executor selection, exception handling.
- Virtual threads: high-concurrency blocking workloads, pinning risks, and carrier threads.

### Hashing and Collections Internals

- `hashCode` and `equals` contract.
- Hash collision handling and bucket distribution.
- HashMap: array of buckets, load factor, resize, tree bins, fail-fast iterators.
- ConcurrentHashMap: lock striping/bin-level synchronization, CAS, weakly consistent iterators.
- LinkedHashMap: insertion/access order, LRU cache building block.
- TreeMap/TreeSet: red-black tree, ordered operations, comparator correctness.
- ArrayList vs LinkedList: locality, resizing, traversal, insertion trade-offs.
- CopyOnWriteArrayList: read-heavy iteration with expensive writes.
- BlockingQueue types: ArrayBlockingQueue, LinkedBlockingQueue, PriorityBlockingQueue, DelayQueue.
- Interview drill: implement a thread-safe LRU cache and explain lock granularity, eviction, and memory pressure.

### Locking, Mutexes, and Coordination

- Mutex, semaphore, monitor, condition variable, latch, barrier, phaser.
- Deadlock: circular wait, hold-and-wait, no preemption, mutual exclusion.
- Livelock and starvation.
- Lock ordering and timeout-based mitigation.
- Optimistic vs pessimistic locking.
- Spin locks vs blocking locks.
- Compare-and-swap and ABA problem.
- Fencing tokens for distributed locks.
- Redlock cautions and why clock assumptions matter.
- Database locks vs application locks vs distributed locks.

### Java Interview Build Targets

1. Implement `HashMap` with resizing and collision handling.
2. Implement LRU cache using HashMap plus doubly linked list.
3. Implement LFU cache.
4. Implement bounded blocking queue using `ReentrantLock` and `Condition`.
5. Implement thread pool with bounded work queue and rejection policy.
6. Implement rate limiter with token bucket and sliding window.
7. Implement concurrent counter benchmark using `AtomicLong` and `LongAdder`.
8. Implement producer-consumer with graceful shutdown.
9. Debug a simulated GC pause and explain remediation.
10. Build a Spring Boot API and trace one request through servlet thread, connection pool, DB transaction, and telemetry.

## 20.2 LLD Principles and Object Relationships

### SOLID in Interview Language

- Single Responsibility Principle: one reason to change; separate orchestration, domain rules, persistence, and transport.
- Open/Closed Principle: extend behavior through interfaces, strategy, plugin points, and configuration.
- Liskov Substitution Principle: subclasses must preserve parent contracts and invariants.
- Interface Segregation Principle: clients should not depend on methods they do not use.
- Dependency Inversion Principle: domain depends on abstractions, not framework or database details.

### OOD Relationship Types

- Inheritance: "is-a"; use only when subtype behavior truly preserves the base contract.
- Composition: strong "has-a"; child lifecycle is owned by parent; preferred for behavior reuse.
- Aggregation: weak "has-a"; referenced object can outlive the owner.
- Association: one object uses or knows another without ownership.
- Dependency: temporary use through method parameters or local variables.
- Polymorphism: call through a common interface while concrete behavior varies.
- Encapsulation: hide state and expose operations that preserve invariants.
- Abstraction: expose the essential contract, hide implementation details.

### Architect-Level LLD Checklist

1. Identify actors, use cases, and invariants.
2. Separate domain objects, services, repositories, factories, policies, and adapters.
3. Define state transitions explicitly.
4. Choose composition before inheritance unless polymorphic hierarchy is justified.
5. Make concurrency and idempotency part of the design, not an afterthought.
6. Describe persistence boundaries and transaction boundaries.
7. Add extension points only where change is realistic.
8. Prove testability with unit, integration, contract, concurrency, and property-style tests.

## 20.3 API Gateway, Load Balancing, and Edge Architecture

### API Gateway Responsibilities

- TLS termination or pass-through.
- Authentication and authorization integration.
- Request routing and version routing.
- Rate limiting and quota enforcement.
- Request validation and normalization.
- Response transformation where unavoidable.
- Correlation IDs and trace propagation.
- WAF integration and bot protection.
- Canary and shadow routing.
- Developer portal and API lifecycle governance.

### Load Balancer Deep Dive

- Layer 4 vs Layer 7 load balancing.
- Algorithms: round robin, least connections, weighted routing, consistent hashing, EWMA latency.
- Health checks: active, passive, readiness-aware, dependency-aware.
- Connection draining during deployment.
- Sticky sessions and why they hurt elasticity.
- Global load balancing with DNS, Anycast, or traffic managers.
- Fail-open vs fail-closed decisions.
- Overload protection and queue limits.

### Scaling Decisions

- Vertical scaling: simpler, bounded by machine limits.
- Horizontal scaling: needs stateless services or externalized state.
- Autoscaling signals: CPU, memory, RPS, queue depth, Kafka lag, custom SLO burn.
- Scale-out risks: database saturation, cache hot keys, connection storms, noisy neighbors.
- Backpressure: reject early, shed low-priority work, degrade gracefully.
- Capacity planning: peak traffic, p95/p99 latency, headroom, regional failover, cost.

## 20.4 Cloud and Deployment Deep Dive

### Cloud Architecture Must-Know

- AWS/Azure/GCP identity and IAM primitives.
- VPC/VNet design, subnets, route tables, NAT, private endpoints.
- DNS, service discovery, private hosted zones.
- Object storage: S3/GCS/Blob durability, consistency behavior, lifecycle, versioning, encryption, access policies.
- Compute choices: VM, container, serverless, managed Kubernetes, batch jobs.
- Managed database trade-offs: operational simplicity vs lock-in and limits.
- Multi-AZ vs multi-region design.
- DR: backup, restore, pilot light, warm standby, active-active.
- FinOps: unit economics, right sizing, storage tiering, data transfer, idle resources.

### Deployment and Release Engineering

- Rolling, blue-green, canary, shadow, dark launch, feature flags.
- Immutable artifacts and environment-specific configuration.
- Expand-contract database migration.
- Backward-compatible API and event changes.
- Rollback vs roll-forward decision.
- GitOps with drift detection.
- Policy as code for deployment guardrails.
- Progressive delivery with metrics gates.
- Release runbooks and incident rollback criteria.

### Kubernetes Production Depth

- Pod scheduling: requests, limits, QoS, affinity, topology spread, taints, tolerations.
- Reliability: readiness, liveness, startup probes, PodDisruptionBudget.
- Networking: Service, EndpointSlice, Ingress, Gateway API, NetworkPolicy, CNI.
- Scaling: HPA, VPA, Cluster Autoscaler, KEDA for event-driven scaling.
- Storage: PV, PVC, StorageClass, CSI, StatefulSet identity.
- Security: RBAC, ServiceAccount, Pod Security Standards, secrets, admission control.
- Operations: Helm, Kustomize, Argo CD, Flux, operators, CRDs.
- Troubleshooting: DNS, image pulls, crash loops, OOM, throttling, routing, RBAC, rollout status.

## 20.5 Database Families You Must Compare

Architect interviews often ask "which database and why?" Prepare by workload, not by product name.

| Family | Examples | Best Fit | Deep Topics |
| --- | --- | --- | --- |
| Relational OLTP | PostgreSQL, MySQL, SQL Server, Oracle | Transactions, constraints, complex queries | MVCC, WAL, isolation, indexes, query plans, replication, partitioning |
| Distributed SQL | Spanner, CockroachDB, YugabyteDB | Global relational consistency | consensus, clock uncertainty, geo-partitioning, transactional latency |
| Document | MongoDB, Couchbase | Flexible aggregates and product iteration | embedding vs reference, indexes, sharding, schema validation |
| Wide-column | Cassandra, ScyllaDB, HBase | Huge write scale and predictable queries | partition key, clustering key, compaction, tombstones, tunable consistency |
| Key-value | DynamoDB, Aerospike, Redis | Low-latency access by key | hot keys, TTL, conditional writes, capacity modes, eviction |
| Search | Elasticsearch, OpenSearch, Solr | Full-text search and relevance | inverted index, analyzers, scoring, shard sizing, refresh interval |
| Graph | Neo4j, JanusGraph | Relationship traversal | graph modeling, traversal depth, supernodes, index-backed lookup |
| Time-series | TimescaleDB, InfluxDB, Prometheus | Metrics and time-window queries | retention, downsampling, compression, cardinality |
| Columnar OLAP | ClickHouse, Pinot, Druid | Low-latency analytics | segments/parts, sort keys, indexes, ingestion, compaction |
| Warehouse | Snowflake, BigQuery, Redshift | BI and large-scale SQL analytics | partitioning, clustering, distribution, workload management |
| Lakehouse | Iceberg, Hudi, Delta on S3/GCS/ADLS | Open table analytics on object storage | snapshots, metadata, compaction, schema evolution, ACID table operations |
| Vector | pgvector, Milvus, Pinecone, Weaviate | Similarity search and RAG | embeddings, ANN indexes, recall/latency, metadata filters |

### Selection Rules

- Start with consistency and access patterns.
- Choose relational unless scale, schema, latency, or query shape forces another model.
- Do not use a cache, search index, or lake table as the primary source of truth without explicit durability and recovery design.
- For every database choice, explain failure mode, backup/restore, scaling limit, cost, and operational maturity.

### Additional Database Deep-Dive Targets

- MySQL/InnoDB: clustered primary key, secondary index lookup, buffer pool, redo/undo log, gap locks, replication, online DDL.
- Oracle: optimizer, indexes, partitioning, RAC concepts, Data Guard, PL/SQL trade-offs, enterprise HA.
- DynamoDB: partition key, sort key, GSIs, LSIs, adaptive capacity, conditional writes, streams, TTL, global tables.
- Cassandra/ScyllaDB: query-first modeling, compaction strategies, tombstones, read repair, consistency levels, repair operations.
- Elasticsearch/OpenSearch: analyzers, inverted index, doc values, refresh interval, shard sizing, index lifecycle management.
- Neo4j/graph databases: node/relationship modeling, traversal cost, supernode mitigation, graph indexes.
- TimescaleDB/InfluxDB: hypertables, chunks, retention, compression, downsampling, high-cardinality risks.
- Snowflake: virtual warehouses, micro-partitions, clustering, time travel, zero-copy clone, separation of storage and compute.
- BigQuery: slots, partitioned tables, clustered tables, storage pricing, query cost, streaming ingestion.
- Vector databases: HNSW/IVF concepts, recall vs latency, metadata filtering, re-ranking, embedding refresh strategy.

## 20.6 Kafka, Flink, S3, Hudi, Iceberg, and Lakehouse Depth

### Kafka Architect Depth

- Topic design: business event boundaries, partition count, retention, compaction.
- Partition key: ordering requirement vs load distribution.
- Producer: idempotence, acks, retries, batching, compression, linger, transactions.
- Consumer: groups, rebalancing, offset commit strategy, lag, idempotency.
- Delivery model: at-least-once by default; exactly-once requires constraints and careful sinks.
- Schema Registry: compatibility modes, schema evolution, field defaults.
- Kafka Connect: source/sink connectors, task scaling, offset storage, DLQs.
- MirrorMaker/Cluster Linking concepts for cross-region replication.
- Operations: broker sizing, ISR, under-replicated partitions, controller, disk, network, quotas.

### Flink Architect Depth

- Stateful stream processing and keyed state.
- Event time vs processing time.
- Watermarks and late events.
- Windows: tumbling, sliding, session, global.
- Checkpoints, savepoints, restart strategies.
- State backends and RocksDB state.
- Exactly-once sinks and two-phase commit concepts.
- Backpressure, operator parallelism, rescaling.
- Use cases: fraud detection, sessionization, real-time enrichment, CDC joins.

### Object Storage and Lakehouse

- Object storage is not a POSIX file system; design around object immutability, listing cost, prefix strategy, and eventual operational limits.
- S3/GCS/ADLS patterns: raw, bronze, silver, gold zones; lifecycle policies; versioning; encryption; access policies.
- File formats: Parquet, ORC, Avro, JSON; choose columnar for analytics and row/event formats for ingestion.
- Table formats: Iceberg, Hudi, Delta Lake.
- Iceberg concepts: snapshots, manifests, partition evolution, schema evolution, time travel, hidden partitioning, catalog integration.
- Hudi concepts: copy-on-write, merge-on-read, upserts, indexing, incremental pull, compaction.
- Delta concepts: transaction log, schema enforcement, time travel, optimize/vacuum concepts.
- Catalogs: Hive Metastore, AWS Glue, REST catalog.
- Query engines: Spark, Flink, Trino, Athena, Presto.
- Maintenance: compaction, clustering, small-file cleanup, snapshot expiration, metadata pruning.
- Governance: lineage, quality checks, PII tagging, access control, audit logs.

### Data Platform Interview Drill

Design a clickstream lakehouse:

1. Collect events through SDK/API gateway.
2. Validate schema and publish to Kafka.
3. Use Kafka Connect or Flink to land raw events in S3.
4. Write curated Iceberg/Hudi tables with partitioning based on query patterns.
5. Run stream enrichment in Flink with checkpoints and DLQ handling.
6. Run batch transforms with Spark/dbt.
7. Query through Trino/Athena and serve real-time dashboards through Pinot/ClickHouse.
8. Add lineage, data quality tests, RBAC, encryption, lifecycle, cost monitoring, and replay plan.

## 20.7 Observability, SRE, and Incident Depth

### Observability Must Cover

- Metrics: RED, USE, golden signals, business KPIs.
- Logs: structured JSON, trace IDs, sampling, PII redaction.
- Traces: spans, propagation, async boundaries, messaging spans.
- Profiles: CPU, allocation, lock contention, heap, wall-clock profiling.
- Events: deploy markers, config changes, feature flag flips.
- Dashboards: user journey, service health, dependency health, saturation, data freshness.
- Alerts: symptom-based, SLO burn rate, actionable owner, runbook link.

### Reliability Must Cover

- SLI, SLO, SLA distinction.
- Error budget policy and release gating.
- Graceful degradation and partial availability.
- Incident command, communication, and postmortem.
- Capacity tests, load tests, soak tests, chaos tests, failover drills.
- Backup and restore tests.
- Dependency risk register.
- Toil reduction and automation.

## 20.8 Security Depth for Architects

- Authentication: sessions, OAuth2, OIDC, device flows, token exchange.
- Authorization: RBAC, ABAC, ReBAC, policy engines.
- Identity propagation across microservices.
- mTLS and service identity.
- Secrets: rotation, dynamic secrets, envelope encryption.
- Data protection: classification, encryption, masking, tokenization.
- API security: rate limits, WAF, schema validation, replay protection.
- Threat modeling: STRIDE, attack trees, abuse cases.
- Supply chain: SBOM, SLSA concepts, signed artifacts, dependency scanning.
- Kubernetes security: admission policies, runtime security, image provenance, least privilege.
- Cloud security: IAM boundaries, private networking, logging, guardrails.
- Compliance: audit trails, data retention, deletion, residency, access reviews.

---

# 21. Top 50 System Design Problems by Category

Use this list for HLD practice. For every problem, produce requirements, scale estimates, APIs, data model, architecture, failure modes, observability, security, deployment, cost, and trade-offs.

| # | Problem | Category | Deep-Dive Focus |
| --- | --- | --- | --- |
| 1 | URL shortener | Core web scale | key generation, redirects, caching, analytics |
| 2 | Rate limiter | Edge/platform | token bucket, sliding window, distributed counters |
| 3 | API gateway | Platform | routing, auth, quotas, observability, canary |
| 4 | Load balancer | Infrastructure | L4/L7 routing, health checks, draining |
| 5 | CDN and static asset platform | Edge | cache invalidation, origin shielding, signed URLs |
| 6 | Distributed cache | Storage/platform | sharding, replication, eviction, hot keys |
| 7 | Distributed queue | Messaging | visibility timeout, retries, DLQ, ordering |
| 8 | Kafka-like event log | Streaming | partitions, replication, offsets, retention |
| 9 | Notification system | Product infra | fanout, preferences, retries, channels |
| 10 | Chat/messaging system | Realtime | WebSocket, ordering, presence, delivery receipts |
| 11 | WhatsApp/Signal-style messenger | Realtime/security | E2E encryption, device sync, media |
| 12 | News feed | Social | fanout-on-write/read, ranking, caching |
| 13 | Twitter/X timeline | Social | followers graph, ranking, celebrity users |
| 14 | Instagram/photo sharing | Social/media | media upload, feed, CDN, moderation |
| 15 | YouTube/video platform | Media | upload, transcoding, CDN, recommendations |
| 16 | Netflix/OTT streaming | Media | catalog, playback, DRM, regional CDN |
| 17 | Dropbox/Google Drive | Storage | chunks, sync, versioning, conflict resolution |
| 18 | Google Photos | Media/ML | dedupe, metadata search, thumbnailing |
| 19 | Search engine | Search | crawling, indexing, ranking, freshness |
| 20 | Autocomplete/typeahead | Search | trie, prefix index, ranking, latency |
| 21 | Web crawler | Search/data | frontier, politeness, dedupe, scheduling |
| 22 | E-commerce marketplace | Commerce | catalog, cart, order, inventory, payment |
| 23 | Shopping cart | Commerce | session state, pricing, inventory holds |
| 24 | Order management system | Commerce | state machine, saga, idempotency |
| 25 | Inventory reservation | Commerce | consistency, oversell prevention, locks |
| 26 | Payment gateway | Fintech | idempotency, PCI, retries, reconciliation |
| 27 | Digital wallet | Fintech | ledger, double-entry accounting, limits |
| 28 | Banking ledger | Fintech | correctness, audit, immutable entries |
| 29 | Fraud detection platform | Data/fintech | stream scoring, features, rules, feedback |
| 30 | Ride-hailing/Uber | Marketplace | matching, geo-indexing, surge, dispatch |
| 31 | Food delivery | Marketplace | order lifecycle, routing, partner integration |
| 32 | Hotel booking | Booking | availability, pricing, holds, overbooking |
| 33 | Movie ticket booking | Booking | seat locking, payment timeout, concurrency |
| 34 | Airline reservation | Booking | inventory classes, global distribution, consistency |
| 35 | Calendar scheduling | Productivity | recurrence, invites, conflict detection |
| 36 | Email service | Productivity | SMTP, inbox indexing, spam, storage |
| 37 | Collaborative document editing | Collaboration | CRDT/OT, presence, snapshots |
| 38 | Feature flag platform | Platform | targeting, consistency, SDK caching |
| 39 | Configuration service | Platform | versioning, rollout, watch, audit |
| 40 | Identity and access management | Security | auth, federation, RBAC, audit |
| 41 | Multi-tenant SaaS platform | SaaS | tenant isolation, quotas, billing, data partitioning |
| 42 | Metrics monitoring system | Observability | ingestion, aggregation, retention, alerting |
| 43 | Log aggregation platform | Observability | ingestion, indexing, storage tiers |
| 44 | Distributed tracing platform | Observability | trace ingestion, sampling, query |
| 45 | CI/CD platform | DevOps | pipeline execution, isolation, artifacts |
| 46 | Kubernetes-like scheduler | Infrastructure | scheduling constraints, bin packing, failures |
| 47 | IoT ingestion platform | IoT | device identity, MQTT, backpressure, time-series |
| 48 | Real-time analytics dashboard | Data | Kafka, Flink, OLAP serving, freshness |
| 49 | Recommendation system | ML/data | candidate generation, ranking, feedback loops |
| 50 | Data lakehouse platform | Data | S3, Iceberg/Hudi, Spark/Flink, governance |

---

# 22. Top 50 Low-Level Design Problems by Category

For each LLD problem, design classes, interfaces, relationships, state transitions, concurrency, persistence, error handling, and tests.

| # | Problem | Category | Deep-Dive Focus |
| --- | --- | --- | --- |
| 1 | Parking lot | Classic OOD | inheritance vs composition, pricing, allocation |
| 2 | Elevator system | State machine | scheduling, direction, concurrency |
| 3 | Vending machine | State pattern | inventory, payment, refunds |
| 4 | ATM | Banking | auth, cash dispenser, transaction boundaries |
| 5 | Library management | Domain model | books, copies, reservations, fines |
| 6 | Movie ticket booking | Concurrency | seat lock, expiry, payment |
| 7 | Hotel booking | Booking | room inventory, pricing, cancellation |
| 8 | Airline booking | Booking | seat classes, holds, itinerary |
| 9 | Meeting scheduler | Scheduling | participants, conflicts, recurrence |
| 10 | Calendar | Scheduling | recurrence rules, reminders, invites |
| 11 | Splitwise | Fintech | balance graph, simplification, settlement |
| 12 | Digital wallet | Fintech | ledger, idempotency, limits |
| 13 | Payment gateway | Fintech | provider strategy, retries, reconciliation |
| 14 | Shopping cart | Commerce | coupons, taxes, inventory checks |
| 15 | Order management | Commerce | state transitions, saga hooks |
| 16 | Inventory management | Commerce | reservations, stock movement, audit |
| 17 | Food delivery | Marketplace | order lifecycle, assignment, tracking |
| 18 | Ride sharing | Marketplace | driver matching, trip lifecycle |
| 19 | Auction system | Marketplace | bidding rules, timers, winner selection |
| 20 | Chess | Game | board, moves, rules, check/checkmate |
| 21 | Snake and ladder | Game | dice, board, players |
| 22 | Tic-tac-toe | Game | win detection, strategy extension |
| 23 | Bowling alley scorer | Game/scoring | scoring rules and frames |
| 24 | Card deck/blackjack | Game | deck, hands, scoring, shuffle |
| 25 | File system | Storage | directories, files, permissions |
| 26 | In-memory key-value store | Storage | TTL, eviction, snapshots |
| 27 | LRU cache | Data structure | hashmap, doubly linked list, concurrency |
| 28 | LFU cache | Data structure | frequency buckets, tie breaking |
| 29 | Custom HashMap | Data structure | hashing, resize, collisions |
| 30 | Concurrent HashMap | Concurrency | lock striping, CAS, resizing |
| 31 | Blocking queue | Concurrency | locks, conditions, producer-consumer |
| 32 | Thread pool | Concurrency | worker lifecycle, queue, rejection |
| 33 | Connection pool | Infrastructure | leasing, health, timeouts |
| 34 | Object pool | Infrastructure | lifecycle, reset, leak detection |
| 35 | Job scheduler | Infrastructure | priority, retries, recurring jobs |
| 36 | Rate limiter library | Infrastructure | token bucket, sliding window |
| 37 | Circuit breaker library | Resilience | states, thresholds, half-open |
| 38 | Retry framework | Resilience | backoff, jitter, idempotency |
| 39 | Logging framework | Observability | appenders, formatters, async logging |
| 40 | Metrics collector | Observability | counters, gauges, histograms |
| 41 | Notification service | Communication | channel strategy, templates, retries |
| 42 | Chat service LLD | Communication | conversations, messages, receipts |
| 43 | Pub-sub broker | Messaging | topics, subscriptions, delivery |
| 44 | Workflow engine | Platform | steps, transitions, compensation |
| 45 | Rule engine | Platform | predicates, actions, priority |
| 46 | Feature flag SDK | Platform | targeting, caching, rollout |
| 47 | RBAC/permission system | Security | roles, policies, inheritance |
| 48 | API gateway filter chain | Platform | chain of responsibility, plugins |
| 49 | URL shortener classes | Web | key generator, repository, redirect |
| 50 | Expense management | Enterprise | approvals, policies, audit |

---

# 23. DSA and Algorithms Interview Bank by Category

This section follows the LeetCode-style category map from the attached image. Treat each category as a 20-question sprint. For architect roles, solve the problem and also explain the production connection.

## 23.1 Array - Top 20

1. Two Sum
2. Best Time to Buy and Sell Stock
3. Product of Array Except Self
4. Maximum Subarray
5. Maximum Product Subarray
6. Contains Duplicate
7. Rotate Array
8. Move Zeroes
9. Merge Sorted Array
10. Majority Element
11. Missing Number
12. Find All Numbers Disappeared in an Array
13. First Missing Positive
14. Subarray Sum Equals K
15. 3Sum
16. Container With Most Water
17. Trapping Rain Water
18. Insert Interval
19. Merge Intervals
20. Minimum Size Subarray Sum

## 23.2 String - Top 20

1. Valid Anagram
2. Valid Palindrome
3. Longest Substring Without Repeating Characters
4. Longest Palindromic Substring
5. Palindromic Substrings
6. Group Anagrams
7. Encode and Decode Strings
8. String to Integer
9. Implement strStr
10. Reverse Words in a String
11. Minimum Window Substring
12. Longest Repeating Character Replacement
13. Valid Parentheses
14. Generate Parentheses
15. Decode String
16. Multiply Strings
17. Add Binary
18. Roman to Integer
19. Integer to Roman
20. Find All Anagrams in a String

## 23.3 Hash Table - Top 20

1. Two Sum
2. Group Anagrams
3. Top K Frequent Elements
4. Longest Consecutive Sequence
5. Subarray Sum Equals K
6. Valid Sudoku
7. Copy List with Random Pointer
8. LRU Cache
9. LFU Cache
10. Design HashMap
11. Design HashSet
12. Randomized Set
13. First Unique Character in a String
14. Isomorphic Strings
15. Word Pattern
16. Intersection of Two Arrays
17. Four Sum II
18. Find Duplicate File in System
19. Time Based Key-Value Store
20. Logger Rate Limiter

## 23.4 Math - Top 20

1. Reverse Integer
2. Palindrome Number
3. Pow(x, n)
4. Sqrt(x)
5. Plus One
6. Add Binary
7. Multiply Strings
8. Factorial Trailing Zeroes
9. Happy Number
10. Excel Sheet Column Number
11. Integer to Roman
12. Roman to Integer
13. Count Primes
14. Product of Array Except Self
15. Divide Two Integers
16. Fraction to Recurring Decimal
17. Random Pick with Weight
18. Rectangle Area
19. Max Points on a Line
20. Basic Calculator

## 23.5 Dynamic Programming - Top 20

1. Climbing Stairs
2. House Robber
3. House Robber II
4. Coin Change
5. Coin Change II
6. Longest Increasing Subsequence
7. Longest Common Subsequence
8. Edit Distance
9. Word Break
10. Decode Ways
11. Unique Paths
12. Minimum Path Sum
13. Maximum Product Subarray
14. Partition Equal Subset Sum
15. Target Sum
16. Palindromic Substrings
17. Longest Palindromic Substring
18. Best Time to Buy and Sell Stock with Cooldown
19. Burst Balloons
20. Regular Expression Matching

## 23.6 Sorting and Intervals - Top 20

1. Merge Intervals
2. Insert Interval
3. Non-overlapping Intervals
4. Meeting Rooms
5. Meeting Rooms II
6. Sort Colors
7. Kth Largest Element in an Array
8. Top K Frequent Elements
9. Largest Number
10. Merge Sorted Array
11. Merge k Sorted Lists
12. Queue Reconstruction by Height
13. Car Fleet
14. Minimum Number of Arrows to Burst Balloons
15. Employee Free Time
16. Accounts Merge
17. H-Index
18. Sort List
19. Relative Sort Array
20. Maximum Gap

## 23.7 Greedy - Top 20

1. Jump Game
2. Jump Game II
3. Gas Station
4. Candy
5. Best Time to Buy and Sell Stock II
6. Partition Labels
7. Task Scheduler
8. Non-overlapping Intervals
9. Minimum Number of Arrows to Burst Balloons
10. Queue Reconstruction by Height
11. Hand of Straights
12. Merge Triplets to Form Target Triplet
13. Valid Parenthesis String
14. Remove K Digits
15. Reorganize String
16. Meeting Rooms II
17. Minimum Cost to Hire K Workers
18. Boats to Save People
19. Car Pooling
20. Maximum Units on a Truck

## 23.8 Binary Search - Top 20

1. Binary Search
2. Search Insert Position
3. Search in Rotated Sorted Array
4. Find Minimum in Rotated Sorted Array
5. Find Peak Element
6. First Bad Version
7. Search a 2D Matrix
8. Median of Two Sorted Arrays
9. Koko Eating Bananas
10. Capacity To Ship Packages Within D Days
11. Split Array Largest Sum
12. Find K Closest Elements
13. Time Based Key-Value Store
14. Search in Rotated Sorted Array II
15. Find First and Last Position of Element in Sorted Array
16. Single Element in a Sorted Array
17. Successful Pairs of Spells and Potions
18. Minimized Maximum of Products Distributed to Any Store
19. Magnetic Force Between Two Balls
20. Minimize Max Distance to Gas Station

## 23.9 Depth-First Search - Top 20

1. Number of Islands
2. Max Area of Island
3. Clone Graph
4. Pacific Atlantic Water Flow
5. Surrounded Regions
6. Course Schedule
7. Course Schedule II
8. Word Search
9. Path Sum
10. Path Sum II
11. Binary Tree Maximum Path Sum
12. Diameter of Binary Tree
13. Same Tree
14. Subtree of Another Tree
15. Serialize and Deserialize Binary Tree
16. Decode String
17. Accounts Merge
18. Reconstruct Itinerary
19. Critical Connections in a Network
20. All Paths From Source to Target

## 23.10 Breadth-First Search - Top 20

1. Binary Tree Level Order Traversal
2. Rotting Oranges
3. Word Ladder
4. Minimum Genetic Mutation
5. Open the Lock
6. Shortest Path in Binary Matrix
7. Walls and Gates
8. Perfect Squares
9. 01 Matrix
10. Number of Islands
11. Clone Graph
12. Course Schedule
13. Bus Routes
14. Snakes and Ladders
15. Minimum Knight Moves
16. As Far from Land as Possible
17. Nearest Exit from Entrance in Maze
18. Shortest Bridge
19. Jump Game III
20. Race Car

## 23.11 Matrix - Top 20

1. Set Matrix Zeroes
2. Spiral Matrix
3. Rotate Image
4. Search a 2D Matrix
5. Search a 2D Matrix II
6. Word Search
7. Number of Islands
8. Max Area of Island
9. Surrounded Regions
10. Pacific Atlantic Water Flow
11. Rotting Oranges
12. 01 Matrix
13. Game of Life
14. Toeplitz Matrix
15. Valid Sudoku
16. Shortest Path in Binary Matrix
17. Minimum Path Sum
18. Unique Paths
19. Longest Increasing Path in a Matrix
20. Number of Enclaves

## 23.12 Tree and Binary Tree - Top 20

1. Maximum Depth of Binary Tree
2. Invert Binary Tree
3. Same Tree
4. Symmetric Tree
5. Diameter of Binary Tree
6. Balanced Binary Tree
7. Subtree of Another Tree
8. Binary Tree Level Order Traversal
9. Binary Tree Right Side View
10. Lowest Common Ancestor of a Binary Tree
11. Validate Binary Search Tree
12. Kth Smallest Element in a BST
13. Construct Binary Tree from Preorder and Inorder Traversal
14. Binary Tree Maximum Path Sum
15. Serialize and Deserialize Binary Tree
16. Flatten Binary Tree to Linked List
17. Path Sum
18. Path Sum II
19. Count Complete Tree Nodes
20. Recover Binary Search Tree

## 23.13 Graph Theory - Top 20

1. Clone Graph
2. Course Schedule
3. Course Schedule II
4. Number of Connected Components in an Undirected Graph
5. Graph Valid Tree
6. Redundant Connection
7. Accounts Merge
8. Network Delay Time
9. Cheapest Flights Within K Stops
10. Reconstruct Itinerary
11. Alien Dictionary
12. Minimum Height Trees
13. Critical Connections in a Network
14. Evaluate Division
15. Pacific Atlantic Water Flow
16. Word Ladder
17. Shortest Path in Binary Matrix
18. Min Cost to Connect All Points
19. Find if Path Exists in Graph
20. Detonate the Maximum Bombs

## 23.14 Two Pointers - Top 20

1. Valid Palindrome
2. Two Sum II - Input Array Is Sorted
3. 3Sum
4. 4Sum
5. Container With Most Water
6. Trapping Rain Water
7. Remove Duplicates from Sorted Array
8. Remove Element
9. Move Zeroes
10. Sort Colors
11. Merge Sorted Array
12. Linked List Cycle
13. Palindrome Linked List
14. Reverse String
15. Squares of a Sorted Array
16. Backspace String Compare
17. Partition Labels
18. Minimum Size Subarray Sum
19. Boats to Save People
20. Valid Palindrome II

## 23.15 Sliding Window - Top 20

1. Longest Substring Without Repeating Characters
2. Minimum Window Substring
3. Longest Repeating Character Replacement
4. Permutation in String
5. Find All Anagrams in a String
6. Sliding Window Maximum
7. Minimum Size Subarray Sum
8. Max Consecutive Ones III
9. Fruit Into Baskets
10. Subarrays with K Different Integers
11. Binary Subarrays With Sum
12. Count Number of Nice Subarrays
13. Frequency of the Most Frequent Element
14. Get Equal Substrings Within Budget
15. Grumpy Bookstore Owner
16. Longest Ones After Replacement
17. Maximum Average Subarray I
18. Minimum Operations to Reduce X to Zero
19. Maximize the Confusion of an Exam
20. Longest Subarray of 1s After Deleting One Element

## 23.16 Prefix Sum - Top 20

1. Range Sum Query - Immutable
2. Range Sum Query 2D - Immutable
3. Subarray Sum Equals K
4. Continuous Subarray Sum
5. Contiguous Array
6. Product of Array Except Self
7. Find Pivot Index
8. Maximum Size Subarray Sum Equals K
9. Minimum Operations to Reduce X to Zero
10. Car Pooling
11. Corporate Flight Bookings
12. Plates Between Candles
13. Path Sum III
14. Subarrays Divisible by K
15. Binary Subarrays With Sum
16. Count Number of Nice Subarrays
17. Maximum Sum of Two Non-Overlapping Subarrays
18. Minimum Value to Get Positive Step by Step Sum
19. Sum of Absolute Differences in a Sorted Array
20. Number of Ways to Split Array

## 23.17 Heap and Priority Queue - Top 20

1. Kth Largest Element in an Array
2. Top K Frequent Elements
3. Merge k Sorted Lists
4. Find Median from Data Stream
5. Task Scheduler
6. Meeting Rooms II
7. K Closest Points to Origin
8. Last Stone Weight
9. Reorganize String
10. Smallest Range Covering Elements from K Lists
11. Sliding Window Maximum
12. Trapping Rain Water II
13. IPO
14. The Skyline Problem
15. Minimum Cost to Connect Sticks
16. Single-Threaded CPU
17. Process Tasks Using Servers
18. Kth Smallest Element in a Sorted Matrix
19. Find K Pairs with Smallest Sums
20. Design Twitter

## 23.18 Stack and Monotonic Stack - Top 20

1. Valid Parentheses
2. Min Stack
3. Evaluate Reverse Polish Notation
4. Daily Temperatures
5. Next Greater Element I
6. Next Greater Element II
7. Largest Rectangle in Histogram
8. Trapping Rain Water
9. Basic Calculator
10. Basic Calculator II
11. Decode String
12. Remove K Digits
13. Asteroid Collision
14. Simplify Path
15. Online Stock Span
16. Car Fleet
17. Sum of Subarray Minimums
18. Maximal Rectangle
19. Remove Duplicate Letters
20. Design Browser History

## 23.19 Linked List - Top 20

1. Reverse Linked List
2. Merge Two Sorted Lists
3. Linked List Cycle
4. Linked List Cycle II
5. Remove Nth Node From End of List
6. Reorder List
7. Add Two Numbers
8. Copy List with Random Pointer
9. Merge k Sorted Lists
10. Sort List
11. Palindrome Linked List
12. Intersection of Two Linked Lists
13. Reverse Nodes in k-Group
14. Swap Nodes in Pairs
15. Rotate List
16. Partition List
17. Flatten a Multilevel Doubly Linked List
18. LRU Cache
19. Design Linked List
20. Delete Node in a Linked List

## 23.20 Backtracking - Top 20

1. Subsets
2. Subsets II
3. Permutations
4. Permutations II
5. Combination Sum
6. Combination Sum II
7. Combinations
8. Letter Combinations of a Phone Number
9. Generate Parentheses
10. Word Search
11. N-Queens
12. Sudoku Solver
13. Palindrome Partitioning
14. Restore IP Addresses
15. Word Break II
16. Matchsticks to Square
17. Partition to K Equal Sum Subsets
18. Expression Add Operators
19. Beautiful Arrangement
20. Unique Paths III

## 23.21 Trie - Top 20

1. Implement Trie
2. Design Add and Search Words Data Structure
3. Word Search II
4. Replace Words
5. Map Sum Pairs
6. Search Suggestions System
7. Maximum XOR of Two Numbers in an Array
8. Concatenated Words
9. Word Squares
10. Stream of Characters
11. Prefix and Suffix Search
12. Design Search Autocomplete System
13. Longest Word in Dictionary
14. Longest Word in Dictionary Through Deleting
15. Short Encoding of Words
16. Camelcase Matching
17. Count Pairs With XOR in a Range
18. Sum of Prefix Scores of Strings
19. Implement Magic Dictionary
20. Word Break

## 23.22 Union-Find - Top 20

1. Number of Islands
2. Number of Connected Components in an Undirected Graph
3. Graph Valid Tree
4. Redundant Connection
5. Accounts Merge
6. Sentence Similarity II
7. Satisfiability of Equality Equations
8. Most Stones Removed with Same Row or Column
9. Regions Cut By Slashes
10. Connecting Cities With Minimum Cost
11. Min Cost to Connect All Points
12. The Earliest Moment When Everyone Become Friends
13. Number of Provinces
14. Path With Minimum Effort
15. Swim in Rising Water
16. Similar String Groups
17. Number of Operations to Make Network Connected
18. Checking Existence of Edge Length Limited Paths
19. Bricks Falling When Hit
20. Remove Max Number of Edges to Keep Graph Fully Traversable

## 23.23 Bit Manipulation - Top 20

1. Single Number
2. Single Number II
3. Single Number III
4. Number of 1 Bits
5. Counting Bits
6. Reverse Bits
7. Missing Number
8. Sum of Two Integers
9. Bitwise AND of Numbers Range
10. Maximum XOR of Two Numbers in an Array
11. Subsets
12. Power of Two
13. Power of Four
14. Hamming Distance
15. Total Hamming Distance
16. Find the Difference
17. UTF-8 Validation
18. Integer Replacement
19. Minimum Flips to Make a OR b Equal to c
20. Minimum XOR Sum of Two Arrays

## 23.24 Database and SQL - Top 20

1. Combine Two Tables
2. Second Highest Salary
3. Nth Highest Salary
4. Rank Scores
5. Consecutive Numbers
6. Employees Earning More Than Their Managers
7. Duplicate Emails
8. Customers Who Never Order
9. Department Highest Salary
10. Department Top Three Salaries
11. Trips and Users
12. Game Play Analysis I
13. Game Play Analysis II
14. Game Play Analysis III
15. Game Play Analysis IV
16. Managers with at Least 5 Direct Reports
17. Rising Temperature
18. Delete Duplicate Emails
19. Exchange Seats
20. Human Traffic of Stadium

## 23.25 Design, Data Stream, and Concurrency - Top 20

1. LRU Cache
2. LFU Cache
3. Min Stack
4. Implement Trie
5. Design HashMap
6. Design HashSet
7. Design Add and Search Words Data Structure
8. Find Median from Data Stream
9. Moving Average from Data Stream
10. Time Based Key-Value Store
11. Design Twitter
12. Design Hit Counter
13. Logger Rate Limiter
14. Design Circular Queue
15. Design Browser History
16. Insert Delete GetRandom O(1)
17. Serialize and Deserialize Binary Tree
18. Print in Order
19. Building H2O
20. Design Bounded Blocking Queue

---

# 24. Final Architect Interview Readiness Checklist

You are ready when you can do the following without notes:

- Solve medium DSA problems in 25-35 minutes.
- Complete the DSA bank by category and explain each pattern's production use.
- Explain DSA patterns through production use cases.
- Design the top 50 LLD problems with classes, interfaces, relationships, concurrency, state, and tests.
- Design the top 50 HLD systems end to end.
- Explain Java/JVM internals: HashMap, ConcurrentHashMap, locking, thread pools, memory model, and garbage collection.
- Explain database internals: pages, WAL, MVCC, indexes, isolation, replication, sharding, backup, and query plans.
- Compare relational, distributed SQL, document, wide-column, key-value, search, graph, time-series, OLAP, warehouse, lakehouse, and vector databases.
- Explain CAP, PACELC, consistency models, consensus, leader election, split brain, vector clocks, Merkle trees, hinted handoff, and consistent hashing.
- Design microservices with database per service, saga, CQRS, outbox, inbox, CDC, and contract testing.
- Design Kafka topics, partition keys, ordering, replay, DLQ, retry, schema evolution, and idempotent consumers.
- Build batch and streaming pipelines with Kafka, Spark, Flink, Airflow, S3/object storage, Iceberg/Hudi/Delta, and OLAP serving.
- Use architecture styles and create ADRs, C4 diagrams, sequence diagrams, deployment diagrams, and migration plans.
- Define SLIs, SLOs, error budgets, dashboards, alerts, runbooks, and postmortems.
- Deploy to Kubernetes with Helm, GitOps, HPA, probes, RBAC, NetworkPolicy, canary, rollback, and observability.
- Discuss security, IAM, secrets, encryption, threat modeling, supply chain security, and compliance.
- Speak clearly about trade-offs, failure modes, cost, migration, and operations.

---

# 25. Official Documentation References for Continued Study

Use official/reference documentation whenever possible:

- Kubernetes concepts: https://kubernetes.io/docs/concepts/
- OpenTelemetry concepts: https://opentelemetry.io/docs/concepts/
- DORA metrics: https://dora.dev/guides/dora-metrics/
- PostgreSQL concurrency control: https://www.postgresql.org/docs/current/mvcc.html
- PostgreSQL transaction isolation: https://www.postgresql.org/docs/current/transaction-iso.html
- Apache Kafka documentation: https://kafka.apache.org/documentation/
- Apache Spark documentation: https://spark.apache.org/docs/latest/
- Apache Flink documentation: https://nightlies.apache.org/flink/flink-docs-stable/
- Apache Iceberg documentation: https://iceberg.apache.org/docs/latest/
- Apache Hudi documentation: https://hudi.apache.org/docs/
- AWS S3 user guide: https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html
- LeetCode problemset: https://leetcode.com/problemset/
- Microsoft SQL Server documentation: https://learn.microsoft.com/en-us/sql/sql-server/
- MongoDB manual: https://www.mongodb.com/docs/manual/
- Redis documentation: https://redis.io/docs/latest/
- RocksDB wiki: https://github.com/facebook/rocksdb/wiki
- Apache Pinot docs: https://docs.pinot.apache.org/
- ClickHouse docs: https://clickhouse.com/docs
- Amazon Redshift developer guide: https://docs.aws.amazon.com/redshift/latest/dg/welcome.html
- Aerospike documentation: https://aerospike.com/docs/

---

# 26. Final Rule

Do not prepare like someone who memorizes tool names. Prepare like someone who can own a production platform.

For every design, always cover:

```text
Requirements -> Scale -> APIs -> Data -> Architecture -> Failure -> Consistency -> Security -> Observability -> Deployment -> Cost -> Trade-offs -> Migration
```

That is the architect-level interview standard.
