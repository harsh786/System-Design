# Database Design and Internals

_Split from `../world_class_pro_architect_master_roadmap.md`. The original source file is intentionally untouched._

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


