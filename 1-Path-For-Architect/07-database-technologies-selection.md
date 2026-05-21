# Database Technologies and Selection

_Split from `../world_class_pro_architect_master_roadmap.md`. The original source file is intentionally untouched._

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


