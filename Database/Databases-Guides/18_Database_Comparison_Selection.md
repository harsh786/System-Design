# Database Comparison & Selection - Staff Architect Guide

## Table of Contents
1. [Database Categories & Use Cases](#database-categories--use-cases)
2. [CAP Theorem & PACELC](#cap-theorem--pacelc)
3. [Consistency Models Comparison](#consistency-models-comparison)
4. [Scalability Patterns](#scalability-patterns)
5. [Decision Matrix](#decision-matrix)
6. [Architecture Patterns](#architecture-patterns)
7. [Cross-Cutting Concerns](#cross-cutting-concerns)
8. [Staff Architect Interview Questions](#staff-architect-interview-questions)
9. [System Design Scenarios](#system-design-scenarios)

---

## Database Categories & Use Cases

### Category Map
```
┌─────────────────────────────────────────────────────────────────┐
│                    DATABASE LANDSCAPE                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  RELATIONAL (OLTP):                                              │
│  ├── PostgreSQL (extensible, advanced features)                  │
│  ├── MySQL (web-scale, replication ecosystem)                    │
│  ├── Oracle (enterprise, advanced analytics)                     │
│  ├── SQL Server (Microsoft ecosystem, BI)                        │
│  ├── CockroachDB (distributed SQL, serializable)                │
│  └── TiDB (MySQL-compatible, HTAP)                              │
│                                                                   │
│  DOCUMENT:                                                        │
│  ├── MongoDB (flexible schema, horizontal scale)                 │
│  └── Couchbase (mobile sync, key-value + document)              │
│                                                                   │
│  WIDE-COLUMN:                                                     │
│  ├── Cassandra (write-heavy, multi-DC, AP)                      │
│  ├── ScyllaDB (Cassandra-compatible, C++, low latency)          │
│  ├── HBase (Hadoop ecosystem, CP)                                │
│  └── DynamoDB (fully managed, serverless)                        │
│                                                                   │
│  KEY-VALUE:                                                       │
│  ├── Redis (in-memory, data structures, caching)                │
│  ├── Aerospike (SSD-optimized, sub-ms latency)                  │
│  ├── Memcached (simple caching, multi-threaded)                  │
│  └── etcd (distributed config, Raft consensus)                   │
│                                                                   │
│  ANALYTICAL (OLAP):                                              │
│  ├── ClickHouse (columnar, real-time analytics)                  │
│  ├── Apache Pinot (user-facing analytics, real-time)            │
│  ├── Apache Druid (time-series analytics)                        │
│  ├── Amazon Redshift (MPP data warehouse)                        │
│  ├── Google BigQuery (serverless, petabyte-scale)               │
│  └── Snowflake (multi-cloud, separation of compute/storage)     │
│                                                                   │
│  SEARCH:                                                          │
│  ├── Elasticsearch/OpenSearch (full-text, logs, analytics)      │
│  └── Meilisearch/Typesense (simple, fast, typo-tolerant)       │
│                                                                   │
│  GRAPH:                                                           │
│  ├── Neo4j (native graph, Cypher, algorithms)                    │
│  ├── Amazon Neptune (managed, multi-model graph)                │
│  └── JanusGraph (distributed, Cassandra/HBase backend)          │
│                                                                   │
│  TIME-SERIES:                                                     │
│  ├── InfluxDB (purpose-built, Flux query language)              │
│  ├── TimescaleDB (PostgreSQL extension)                          │
│  ├── Prometheus (monitoring metrics, pull-based)                │
│  └── QuestDB (high-performance, SQL)                            │
│                                                                   │
│  STREAMING/LOG:                                                   │
│  ├── Apache Kafka (event streaming, log storage)                │
│  ├── Apache Pulsar (multi-tenant, tiered storage)               │
│  └── Amazon Kinesis (managed streaming)                          │
│                                                                   │
│  EMBEDDED:                                                        │
│  ├── SQLite (local, zero-config, ubiquitous)                    │
│  ├── RocksDB (LSM, embedded KV, Facebook)                       │
│  └── DuckDB (embedded OLAP, columnar)                           │
│                                                                   │
│  MULTI-MODEL:                                                     │
│  ├── FoundationDB (KV foundation, build layers)                 │
│  ├── ArangoDB (graph + document + key-value)                    │
│  └── SurrealDB (multi-model, real-time, embedded or distributed)│
└─────────────────────────────────────────────────────────────────┘
```

---

## CAP Theorem & PACELC

### CAP Classification
```
CAP Theorem: In a network partition, choose Consistency OR Availability

CP (Consistency + Partition Tolerance):
- Choose consistency over availability during partition
- HBase, MongoDB (with majority write concern), etcd, ZooKeeper
- CockroachDB, Spanner, FoundationDB

AP (Availability + Partition Tolerance):
- Choose availability over consistency during partition
- Cassandra, DynamoDB (default), Riak, Couchbase
- CouchDB, ScyllaDB (AP mode)

CA (no network partitions):
- Only possible in single-node (not distributed)
- Traditional RDBMS (single node PostgreSQL, MySQL)

PACELC (more nuanced):
If Partition: Choose A or C
Else (normal operation): Choose Latency or Consistency

PA/EL: Cassandra, DynamoDB (eventual consistency, low latency)
PC/EC: CockroachDB, Spanner (consistent always, higher latency)
PA/EC: MongoDB (available during partition, consistent normally)
PC/EL: Not common (sacrifice latency in partition but not normally)
```

### Consistency Spectrum
```
Weakest ──────────────────────────────────────────── Strongest

Eventual     Causal      Read-Your-   Bounded     Sequential  Linearizable
Consistency  Consistency  Writes       Staleness   Consistency Consistency

Cassandra    MongoDB      DynamoDB     Cosmos DB   PostgreSQL  CockroachDB
(ONE)        (causal      (session     (5s bound)  (SSI)       Spanner
DynamoDB     sessions)    consistency)                         FoundationDB
(eventual)                                         
Redis                                              
(async                                             
replication)                                       
```

---

## Scalability Patterns

### Scaling Comparison
```
┌────────────────┬───────────────┬────────────────┬──────────────┐
│ Database       │ Read Scale    │ Write Scale    │ Max Practical│
├────────────────┼───────────────┼────────────────┼──────────────┤
│ PostgreSQL     │ Replicas      │ Vertical       │ ~10TB, 100K  │
│                │ (streaming)   │ (single writer)│ TPS          │
├────────────────┼───────────────┼────────────────┼──────────────┤
│ MySQL          │ Replicas      │ Vitess/shard   │ ~10TB per    │
│                │ (binlog)      │ (horizontal)   │ shard        │
├────────────────┼───────────────┼────────────────┼──────────────┤
│ CockroachDB    │ Leaseholder   │ Horizontal     │ PB scale,    │
│                │ reads         │ (auto-shard)   │ millions TPS │
├────────────────┼───────────────┼────────────────┼──────────────┤
│ MongoDB        │ Secondaries   │ Sharding       │ PB scale     │
│                │               │ (native)       │              │
├────────────────┼───────────────┼────────────────┼──────────────┤
│ Cassandra      │ Any node      │ Any node       │ PB scale,    │
│                │ (eventually)  │ (linear scale) │ millions TPS │
├────────────────┼───────────────┼────────────────┼──────────────┤
│ Redis          │ Replicas      │ Cluster shard  │ TB scale     │
│                │               │ (hash slots)   │ (memory)     │
├────────────────┼───────────────┼────────────────┼──────────────┤
│ ClickHouse     │ Replicas      │ Shards         │ PB scale     │
│                │               │ (distributed)  │ (analytics)  │
├────────────────┼───────────────┼────────────────┼──────────────┤
│ DynamoDB       │ Auto-scale    │ Auto-scale     │ Unlimited    │
│                │ (managed)     │ (partitions)   │ (managed)    │
├────────────────┼───────────────┼────────────────┼──────────────┤
│ Elasticsearch  │ Replicas      │ Shards         │ PB scale     │
│                │               │                │ (search)     │
└────────────────┴───────────────┴────────────────┴──────────────┘
```

---

## Decision Matrix

### When to Use What
```
┌────────────────────────────────────────────────────────────────┐
│ REQUIREMENT                    │ RECOMMENDED DATABASE            │
├────────────────────────────────┼────────────────────────────────┤
│ Complex queries + transactions │ PostgreSQL, CockroachDB        │
│ MySQL ecosystem/compatibility  │ MySQL, TiDB, Vitess            │
│ Flexible schema + scale       │ MongoDB                         │
│ Sub-ms caching                │ Redis, Memcached               │
│ Sub-ms at SSD scale           │ Aerospike, ScyllaDB            │
│ Write-heavy, multi-DC         │ Cassandra, ScyllaDB            │
│ Serverless, zero-ops          │ DynamoDB, PlanetScale, Neon    │
│ Real-time analytics           │ ClickHouse, Apache Pinot       │
│ Data warehouse                │ Redshift, BigQuery, Snowflake  │
│ Full-text search              │ Elasticsearch, OpenSearch      │
│ Graph traversals              │ Neo4j, Neptune                  │
│ Time-series metrics           │ TimescaleDB, InfluxDB          │
│ Event streaming               │ Kafka, Pulsar                  │
│ Global distribution + SQL     │ CockroachDB, Spanner           │
│ HTAP (OLTP + OLAP together)  │ TiDB, SingleStore              │
│ Multi-model flexibility       │ FoundationDB, ArangoDB         │
│ Embedded/local                │ SQLite, DuckDB, RocksDB        │
│ Financial transactions        │ PostgreSQL, CockroachDB, Oracle│
│ IoT high ingestion            │ TimescaleDB, InfluxDB, Kafka   │
│ ML vector search              │ Pinecone, Milvus, pgvector     │
└────────────────────────────────┴────────────────────────────────┘
```

---

## Architecture Patterns

### Polyglot Persistence
```
Modern applications use MULTIPLE databases:

┌───────────────────────────────────────────────────────────────┐
│                    Application Architecture                     │
│                                                                 │
│  ┌─────────┐     ┌─────────────┐     ┌──────────────────┐   │
│  │ API     │────→│ PostgreSQL  │     │ Redis (Cache)     │   │
│  │ Service │     │ (Primary DB)│     │ (Session, Hot)    │   │
│  │         │────→│             │     │                    │   │
│  └─────────┘     └──────┬──────┘     └──────────────────┘   │
│                          │ CDC (Debezium)                      │
│                          ▼                                     │
│                    ┌───────────┐                               │
│                    │   Kafka   │ (Event bus)                   │
│                    └─────┬─────┘                               │
│              ┌───────────┼───────────┐                        │
│              ▼           ▼           ▼                         │
│  ┌───────────────┐ ┌──────────┐ ┌────────────┐              │
│  │Elasticsearch  │ │ClickHouse│ │ Neo4j      │              │
│  │(Search)       │ │(Analytics)│ │(Graph/Reco)│              │
│  └───────────────┘ └──────────┘ └────────────┘              │
└───────────────────────────────────────────────────────────────┘

Each database optimized for its access pattern:
- PostgreSQL: ACID transactions, source of truth
- Redis: Sub-ms reads for hot data
- Elasticsearch: Full-text search, log analytics
- ClickHouse: Analytical queries, dashboards
- Neo4j: Recommendations, relationship queries
- Kafka: Event bus, decoupling, CDC
```

### CQRS (Command Query Responsibility Segregation)
```
Write Model (Commands):          Read Model (Queries):
┌──────────────┐                ┌──────────────────────┐
│ PostgreSQL   │  ──Events──→   │ Elasticsearch (search)│
│ (normalized, │  ──Events──→   │ Redis (cache)         │
│  ACID)       │  ──Events──→   │ ClickHouse (analytics)│
│              │  ──Events──→   │ DynamoDB (by access   │
└──────────────┘                │  pattern)             │
                                └──────────────────────┘

Benefits:
- Each side optimized independently
- Scale reads and writes separately
- Different models for different queries
- Event-driven consistency between sides
```

---

## Cross-Cutting Concerns

### Replication Comparison
```
┌────────────┬──────────────┬─────────────────┬────────────────────┐
│ Database   │ Replication  │ Consistency      │ Failover Time      │
├────────────┼──────────────┼─────────────────┼────────────────────┤
│ PostgreSQL │ Streaming    │ Sync/Async       │ 5-30s (Patroni)    │
│            │ (WAL-based)  │ configurable     │                    │
├────────────┼──────────────┼─────────────────┼────────────────────┤
│ MySQL      │ Binlog       │ Async/Semi-sync  │ 5-30s (InnoDB Cl.) │
│            │ (logical)    │ Group Replication│                    │
├────────────┼──────────────┼─────────────────┼────────────────────┤
│ MongoDB    │ Oplog        │ Majority write   │ 2-12s              │
│            │              │ concern          │                    │
├────────────┼──────────────┼─────────────────┼────────────────────┤
│ Cassandra  │ Gossip +     │ Tunable (CL)    │ 0s (masterless)    │
│            │ streaming    │                  │                    │
├────────────┼──────────────┼─────────────────┼────────────────────┤
│ CockroachDB│ Raft         │ Serializable     │ ~5-10s (Raft)      │
│            │ (per range)  │ (always)         │                    │
├────────────┼──────────────┼─────────────────┼────────────────────┤
│ Redis      │ Async stream │ Eventual         │ 5-30s (Sentinel)   │
│            │              │                  │                    │
├────────────┼──────────────┼─────────────────┼────────────────────┤
│ Kafka      │ ISR (pull)   │ Configurable     │ <1s (KRaft)        │
│            │              │ (acks setting)   │                    │
└────────────┴──────────────┴─────────────────┴────────────────────┘
```

### Transaction Support Comparison
```
┌──────────────┬─────────────┬──────────────────┬──────────────────┐
│ Database     │ ACID        │ Isolation Level   │ Distributed Txn  │
├──────────────┼─────────────┼──────────────────┼──────────────────┤
│ PostgreSQL   │ Full        │ Serializable(SSI) │ 2PC (limited)    │
│ MySQL        │ Full        │ Repeatable Read   │ XA               │
│ MongoDB      │ Full(4.0+)  │ Snapshot          │ 2PC (sharded)    │
│ CockroachDB  │ Full        │ Serializable      │ Native (Raft)    │
│ TiDB         │ Full        │ Snapshot          │ Percolator       │
│ Cassandra    │ LWT only    │ None (per-row)    │ No               │
│ Redis        │ MULTI(weak) │ None              │ No               │
│ DynamoDB     │ TransactWr  │ Serializable(txn) │ Yes (100 items)  │
│ ClickHouse   │ No          │ None              │ No               │
│ Elasticsearch│ No          │ None              │ No               │
│ FoundationDB │ Full        │ Serializable      │ Native           │
└──────────────┴─────────────┴──────────────────┴──────────────────┘
```

### Indexing Comparison
```
┌──────────────┬─────────────────────────────────────────────────┐
│ Database     │ Index Types                                       │
├──────────────┼─────────────────────────────────────────────────┤
│ PostgreSQL   │ B-Tree, Hash, GiST, GIN, BRIN, SP-GiST, Bloom │
│ MySQL        │ B+Tree, Hash, Fulltext, Spatial, Functional      │
│ MongoDB      │ B-Tree, Compound, Multikey, Text, Geo, Wildcard │
│ Cassandra    │ Primary(partition+clustering), Secondary(limited)│
│ Redis        │ None (data structure = access pattern)           │
│ ClickHouse   │ Sparse Primary, MinMax, Set, Bloom, Star-Tree   │
│ Elasticsearch│ Inverted, BKD-Tree, Doc Values, kNN (HNSW)     │
│ Neo4j        │ B-Tree, Fulltext, Range, Point, Token Lookup    │
│ DynamoDB     │ Primary(PK+SK), GSI, LSI                        │
└──────────────┴─────────────────────────────────────────────────┘
```

---

## Staff Architect Interview Questions

**Q1: You're designing a system that needs to handle 1M users, 10K requests/second, with complex queries. How do you choose your database(s)?**
**A:** Step-by-step analysis:
1. Identify access patterns (OLTP? OLAP? Search? Caching?)
2. Determine consistency requirements (financial? social? analytics?)
3. Estimate data volume (fits single node? Need sharding?)
4. Consider latency requirements (sub-ms? sub-second? seconds OK?)
5. Evaluate operational constraints (managed? self-hosted? team expertise?)

Likely answer for most web applications:
- Primary: PostgreSQL (relational, ACID, proven)
- Cache: Redis (hot data, sessions, rate limiting)
- Search: Elasticsearch (if full-text needed)
- Analytics: ClickHouse or materialized views (if dashboard needed)
- Queue: Kafka (if async processing needed)
Scale PostgreSQL first (read replicas, connection pooling), then polyglot.

**Q2: How do you handle the trade-off between consistency and availability in a global system?**
**A:**
- Classify data by consistency needs:
  - Financial: Strong consistency (CockroachDB, Spanner) — accept latency
  - User profiles: Eventual consistency fine (MongoDB, DynamoDB) — optimize latency
  - Counters/likes: Eventual (Redis, Cassandra) — speed matters most
  - Sessions: Read-your-writes (DynamoDB session consistency)
- Geographic routing: Keep data close to users (geo-partitioning)
- Accept trade-offs: Not all data needs same consistency level
- Use compensating transactions for eventually consistent paths

**Q3: When would you recommend a purpose-built database over a general-purpose one?**
**A:**
Use purpose-built when:
- Scale exceeds general-purpose limits (time-series: InfluxDB > PostgreSQL at 1M metrics/sec)
- Specific access pattern dominates (graph traversals: Neo4j >> PostgreSQL for 6-hop queries)
- Performance requirements are extreme (sub-ms cache: Redis, not PostgreSQL)
- Operational simplicity matters (DynamoDB vs self-managed Cassandra)

Stay general-purpose when:
- Multiple access patterns (PostgreSQL covers 80% of needs)
- Small to medium scale (<100GB, <10K TPS)
- Team expertise limited (fewer systems = fewer failure modes)
- Budget constraints (one database vs five)

**Q4: Design the data layer for a social media platform (100M users, 1B posts, real-time feeds).**
**A:**
```
┌────────────────────────────────────────────────────────────┐
│ Write Path:                                                 │
│ Post creation → PostgreSQL (source of truth)               │
│              → Kafka (fan-out to downstream)               │
│              → Redis (update feed caches)                  │
│              → Elasticsearch (index for search)            │
│                                                             │
│ Read Path:                                                  │
│ Feed: Redis (pre-computed, hot users)                      │
│       + PostgreSQL (cold users, pull-based)                │
│ Search: Elasticsearch                                       │
│ Profile: PostgreSQL (with Redis cache)                     │
│ Analytics: ClickHouse (engagement metrics)                 │
│ Recommendations: Neo4j (friend suggestions)                │
│                                                             │
│ Feed generation strategy:                                   │
│ - Celebrity posts: Fan-out on read (too many followers)    │
│ - Normal posts: Fan-out on write (push to follower feeds)  │
│ - Hybrid: Threshold at ~10K followers                      │
└────────────────────────────────────────────────────────────┘
```

**Q5: How do you evaluate a new database technology for production use?**
**A:** Evaluation framework:
1. **Maturity**: How long in production? Who uses it at scale?
2. **Community**: Active development? Issues resolved quickly?
3. **Operational**: Monitoring, backup, upgrades, debugging tools?
4. **Performance**: Benchmark with YOUR workload (not vendor's)
5. **Failure modes**: How does it fail? Data loss scenarios?
6. **Recovery**: Backup/restore time? Point-in-time recovery?
7. **Scalability**: How far does it scale? What breaks first?
8. **Lock-in**: Can you migrate away? Standard protocols?
9. **Cost**: License, hardware, operational overhead, expertise?
10. **Team**: Can your team operate it? Training available?

Red flags:
- No company running it at scale in production
- Single maintainer/company with unclear business model
- No clear upgrade/migration path
- Claims of "zero operational overhead" (nothing is zero)

---

## System Design Scenarios

### Scenario 1: E-Commerce Platform Database Architecture
```
Scale: 10M products, 50M users, 500M orders, peak 50K orders/minute

Data stores:
1. PostgreSQL (primary):
   - Users, orders, payments (ACID required)
   - Horizontal: Citus for sharding by customer_id
   - Connection pool: PgBouncer (transaction mode)

2. Elasticsearch:
   - Product catalog search (full-text, faceted)
   - Synced via Debezium → Kafka → ES connector

3. Redis:
   - Session store (1M concurrent sessions)
   - Shopping cart (temporary, TTL)
   - Rate limiting (sliding window)
   - Inventory cache (read-through, write-through)

4. ClickHouse:
   - Order analytics, GMV dashboards
   - Product performance metrics
   - Fed from Kafka CDC stream

5. Kafka:
   - Order events (payment processing pipeline)
   - Inventory updates
   - CDC from PostgreSQL
   - Notification triggers

Consistency design:
- Orders: Strong (PostgreSQL SERIALIZABLE for payment)
- Inventory: Eventually consistent (Redis cache + async sync)
  - Overselling prevention: Redis DECR + check (best effort)
  - Final check: PostgreSQL transaction (source of truth)
- Search: Eventual (1-2 second lag acceptable)
- Analytics: Eventual (minutes acceptable)
```

### Scenario 2: IoT Platform (1M Devices, 10B Events/Day)
```
Scale: 1M devices, 10B events/day (~115K events/sec sustained)

Data flow:
Devices → MQTT Broker → Kafka → [Processing] → Storage

Storage tier design:
1. Hot path (real-time):
   - Kafka: Event ingestion buffer (24h retention)
   - Redis: Latest device state (1M keys)
   - ClickHouse: Real-time analytics (last 7 days)

2. Warm path (recent history):
   - TimescaleDB: Last 30 days (compressed, queryable)
   - Or: ClickHouse with TWCS-like partitioning

3. Cold path (archival):
   - S3 + Parquet: Full history (years)
   - Queryable via: Athena, Spark, Redshift Spectrum

4. Alert system:
   - Kafka Streams: Real-time anomaly detection
   - Redis: Threshold state tracking
   - PostgreSQL: Alert rules, configurations

Scaling:
- Kafka: 20 brokers, 100 partitions per topic
- ClickHouse: 6 nodes (2 shards × 3 replicas)
- TimescaleDB: 3 nodes (distributed hypertable)
- Redis: 6-node cluster (3 masters + 3 replicas)
```

### Scenario 3: Global Financial Platform
```
Requirements: Multi-region, regulatory compliance, zero data loss

Architecture:
1. Primary database: CockroachDB (multi-region)
   - REGIONAL BY ROW for data residency
   - Serializable isolation for financial accuracy
   - 3 regions: US, EU, APAC (5 nodes each)
   
2. Audit trail: Kafka (immutable log)
   - Every transaction event captured
   - Infinite retention (compliance)
   - 3 data centers, RF=3

3. Reporting: Snowflake (data warehouse)
   - Fed from Kafka via streaming ingestion
   - Multi-region (data stays in region)
   - Regulatory reporting queries

4. Cache: Redis (per-region)
   - Account balance cache (invalidation via CDC)
   - Rate limiting
   - Session management

5. Fraud detection: Neo4j + ML pipeline
   - Transaction graph for pattern detection
   - Real-time scoring via Kafka Streams

Compliance design:
- Data residency: CockroachDB geo-partitioning (EU data stays in EU)
- Encryption: At-rest (AES-256) + in-transit (TLS 1.3)
- Audit: Immutable Kafka log + CockroachDB audit tables
- Recovery: RPO=0 (synchronous replication), RTO<30s
- Backup: Point-in-time recovery (PITR) with 30-day retention
```

---

## Quick Reference: Database Selection Flowchart

```
Start
  │
  ├── Need ACID transactions?
  │   ├── YES → Need horizontal write scaling?
  │   │         ├── YES → Need multi-region?
  │   │         │         ├── YES → CockroachDB / Google Spanner
  │   │         │         └── NO  → TiDB / Vitess+MySQL / Citus+PG
  │   │         └── NO  → PostgreSQL / MySQL
  │   └── NO →
  │
  ├── Primary use case?
  │   ├── Caching/Sub-ms reads → Redis / Aerospike
  │   ├── Full-text search → Elasticsearch / OpenSearch
  │   ├── Analytics/OLAP → ClickHouse / Redshift / BigQuery
  │   ├── Time-series → TimescaleDB / InfluxDB
  │   ├── Graph queries → Neo4j / Neptune
  │   ├── Document store → MongoDB / DynamoDB
  │   ├── Write-heavy, AP → Cassandra / ScyllaDB
  │   ├── Event streaming → Kafka / Pulsar
  │   └── Serverless/managed → DynamoDB / PlanetScale / Neon
  │
  └── Budget/operational constraints?
      ├── Minimal ops team → Managed services (RDS, Atlas, DynamoDB)
      ├── Cost-sensitive → PostgreSQL (open-source, versatile)
      └── Vendor lock-in concern → Open-source (PG, MySQL, Kafka, ClickHouse)
```

