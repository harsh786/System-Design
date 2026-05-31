# Apache Kafka (as a Database/Log) - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Log-Based Storage](#log-based-storage)
3. [Partitioning & Replication](#partitioning--replication)
4. [Exactly-Once Semantics](#exactly-once-semantics)
5. [Kafka as a Database (Event Sourcing)](#kafka-as-a-database)
6. [KRaft (No ZooKeeper)](#kraft-no-zookeeper)
7. [Staff Architect Interview Questions](#staff-architect-interview-questions)
8. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### Kafka Architecture
```
┌────────────────────────────────────────────────────────┐
│                    Kafka Cluster                         │
│                                                          │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐          │
│  │ Broker 1  │  │ Broker 2  │  │ Broker 3  │          │
│  │           │  │           │  │           │          │
│  │ Topic A   │  │ Topic A   │  │ Topic A   │          │
│  │ P0(L) P1  │  │ P0  P1(L)│  │ P0  P1    │          │
│  │           │  │           │  │ P2(L)     │          │
│  │ Topic B   │  │ Topic B   │  │ Topic B   │          │
│  │ P0(L)     │  │ P0  P1(L)│  │ P1        │          │
│  └───────────┘  └───────────┘  └───────────┘          │
│                                                          │
│  P = Partition, L = Leader, others = Followers          │
│                                                          │
│  Controller (KRaft since 3.x):                          │
│  Metadata management, leader election                    │
└────────────────────────────────────────────────────────┘

Producers → Kafka Partitions → Consumers (Consumer Groups)
```

---

## Log-Based Storage

### Partition as an Immutable Log
```
Partition = Ordered, immutable sequence of records

Partition 0:
┌─────┬─────┬─────┬─────┬─────┬─────┬─────┐
│  0  │  1  │  2  │  3  │  4  │  5  │  6  │  ← Offsets
│msg_a│msg_b│msg_c│msg_d│msg_e│msg_f│msg_g│
└─────┴─────┴─────┴─────┴─────┴─────┴─────┘
                                        ↑ Log End Offset

Storage on disk:
├── topic-partition-0/
│   ├── 00000000000000000000.log    (segment file, up to 1GB)
│   ├── 00000000000000000000.index  (offset → position mapping)
│   ├── 00000000000000000000.timeindex (timestamp → offset)
│   ├── 00000000000050000000.log    (next segment at offset 50M)
│   └── ...

Key properties:
- Append-only (no modification of existing records)
- Sequential I/O (fastest possible disk access pattern)
- Zero-copy (sendfile() from page cache to network)
- Retention by time or size (not consume-based)
- Multiple consumers read independently (different offsets)
```

### Why Kafka is Fast
```
1. Sequential I/O only:
   - Writes append to end of log (no random seeks)
   - Reads are sequential within consumer position
   - HDDs: Sequential I/O = 600MB/s, Random I/O = 100 IOPS

2. Zero-copy (sendfile):
   - Data goes: Disk → Page Cache → NIC (kernel space only)
   - No copy to user space
   - Eliminates 2 copy operations + 4 context switches

3. Batch everything:
   - Producers batch multiple messages per request
   - Compression at batch level (better ratio)
   - Consumers fetch large batches

4. Page cache utilization:
   - Recent messages served from OS page cache
   - No JVM heap / GC overhead for data
   - More RAM = more data in cache

5. Minimal per-message overhead:
   - No per-message index
   - Offset-based lookup (O(1) with index files)

Performance: 1M+ messages/sec per broker, 100MB/s+ throughput
```

---

## Partitioning & Replication

### Partition Strategy
```
Producer → Topic → Partition:
- Key-based: hash(key) % num_partitions (ordered per key)
- Round-robin: No key, distribute evenly
- Custom partitioner: Application logic (e.g., geo-based)

Ordering guarantees:
- Within partition: Total order (guaranteed)
- Across partitions: No ordering guarantee
- Design: Choose partition key to group related events

Number of partitions:
- More partitions = more parallelism (consumer instances)
- More partitions = more memory, file handles, leader elections
- Rule of thumb: Start with max(throughput_target / throughput_per_partition, consumer_instances)
- Single partition throughput: ~10-100 MB/s
```

### Replication
```
ISR (In-Sync Replicas):
- Leader handles all reads/writes for partition
- Followers pull from leader, try to stay in sync
- ISR: Set of replicas that are "caught up"
- Replica falls out of ISR if lag > replica.lag.time.max.ms

Acks configuration (producer):
- acks=0: Fire and forget (no durability guarantee)
- acks=1: Leader acknowledges (leader failure = potential loss)
- acks=all: All ISR members acknowledge (strongest durability)
  Combined with min.insync.replicas=2: Guarantees 2 copies before ack

Leader election:
- When leader fails, new leader elected from ISR
- unclean.leader.election.enable=false: Only ISR members can become leader
  (prevents data loss at cost of reduced availability)
```

---

## Exactly-Once Semantics

### Idempotent Producer
```
enable.idempotence=true (default since Kafka 3.0):
- Producer assigns sequence number to each message
- Broker deduplicates by (ProducerID, PartitionID, SequenceNumber)
- Prevents duplicate delivery from producer retries
- Guarantees exactly-once within single partition per producer session
```

### Transactional Producer
```java
producer.initTransactions();
try {
    producer.beginTransaction();
    producer.send(record1);
    producer.send(record2);
    producer.sendOffsetsToTransaction(offsets, groupId); // atomic with sends
    producer.commitTransaction();
} catch (Exception e) {
    producer.abortTransaction();
}

// Properties:
// - Atomic multi-partition writes
// - Atomic commit of consumer offsets + produced messages
// - Enables exactly-once stream processing (consume-transform-produce)
// - isolation.level=read_committed on consumer to only see committed

// Under the hood:
// - Transaction coordinator (one per transactional.id)
// - Two-phase commit (prepare + commit markers in partitions)
// - Abort markers for failed transactions (consumers skip these)
```

---

## Kafka as a Database (Event Sourcing)

### Event Sourcing Pattern
```
Traditional: Store current state (overwrite on update)
Event Sourcing: Store all events (derive state by replaying)

Events (in Kafka topic with infinite retention):
Offset 0: AccountCreated {id: 123, name: "Alice"}
Offset 1: MoneyDeposited {id: 123, amount: 1000}
Offset 2: MoneyWithdrawn {id: 123, amount: 200}
Offset 3: MoneyDeposited {id: 123, amount: 500}

Current state (derived): Balance = 1000 - 200 + 500 = 1300

Benefits:
- Complete audit trail
- Time-travel queries (replay to any point)
- Event-driven architecture (react to events)
- Multiple views from same events

Kafka as event store:
- Infinite retention (log.retention.ms=-1 or tiered storage)
- Compacted topics for state snapshots
- Schema registry for event evolution
```

### Compacted Topics (Changelog)
```
Log compaction: Keep only latest value per key

Before compaction:
Offset: 0   1   2   3   4   5   6   7
Key:    A   B   A   C   B   A   C   B
Value:  v1  v1  v2  v1  v2  v3  v2  v3

After compaction:
Offset: 5   6   7
Key:    A   C   B
Value:  v3  v2  v3

Use cases:
- Database changelog (CDC)
- KTable in Kafka Streams (materialized view)
- Configuration distribution
- Cache-like semantics (latest state per key)

Key = null → tombstone (marks key for deletion)
```

### Kafka Streams / ksqlDB
```
Kafka Streams (library, not a cluster):
- Stateful stream processing within application
- State stores backed by changelog topics (RocksDB local)
- Exactly-once processing guarantees

KTable (materialized view):
- Topic consumed as changelog
- Maintains latest value per key in state store
- Join streams with tables (enrichment)

Example: Real-time user session aggregation
KStream<String, Event> events = builder.stream("user-events");
KTable<String, SessionState> sessions = events
    .groupByKey()
    .windowedBy(SessionWindows.ofInactivityGapWithNoGrace(Duration.ofMinutes(30)))
    .aggregate(
        SessionState::new,
        (key, event, state) -> state.update(event),
        Materialized.as("session-store")
    );
```

---

## KRaft (No ZooKeeper)

### KRaft Architecture (Kafka 3.3+ production ready)
```
Before (with ZooKeeper):
Kafka Brokers ←→ ZooKeeper Ensemble (separate cluster)
- ZK: Metadata, leader election, broker registration
- Complex: Two systems to manage, different failure modes

After (KRaft):
Kafka Brokers with Controller role built-in
┌──────────────────────────────────────────┐
│ Controller Quorum (3 nodes, Raft-based)  │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│ │Active    │ │Follower  │ │Follower  │ │
│ │Controller│ │Controller│ │Controller│ │
│ └──────────┘ └──────────┘ └──────────┘ │
└──────────────────────────────────────────┘
          │ Metadata updates (Raft log)
          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ Broker 1 │ │ Broker 2 │ │ Broker 3 │
└──────────┘ └──────────┘ └──────────┘

Benefits:
- Single system (simpler operations)
- Faster metadata propagation
- Better scalability (millions of partitions)
- Faster controller failover
- No ZooKeeper dependency
```

---

## Staff Architect Interview Questions

**Q1: Can Kafka replace a traditional database?**
**A:** Partially, in specific patterns:
- Yes for: Event sourcing, audit logs, CDC changelog, stream processing state
- No for: Ad-hoc queries, point lookups, complex aggregations, transactions across topics
- Kafka + Kafka Streams: Can maintain queryable state (KTables)
- Kafka + ksqlDB: SQL-like queries over streams
- Reality: Kafka as source of truth + derived databases for serving (CQRS pattern)

**Q2: How does Kafka achieve exactly-once end-to-end?**
**A:** Three components:
1. Idempotent producer (dedup within partition)
2. Transactional producer (atomic multi-partition writes)
3. Consumer read_committed isolation (skip uncommitted/aborted)
Combined: Consume → Process → Produce atomically:
- Consumer offset commit + produced messages in same transaction
- If crash: Transaction aborted, consumer re-reads from last committed offset
- Guarantee: Each input record processed exactly once to output

**Q3: How would you design Kafka for 100TB daily throughput?**
**A:**
```
Cluster sizing:
- 100TB/day = ~1.2GB/s sustained write throughput
- With RF=3: 3.6GB/s total write
- Per broker: ~300MB/s (reasonable for modern hardware)
- Minimum: 12 brokers for write capacity (with headroom: 20 brokers)
- 3 controller nodes (separate from data brokers, or combined)

Hardware per broker:
- CPU: 16+ cores (compression, network processing)
- RAM: 64GB+ (page cache for recent data)
- Disk: 12× 4TB HDDs (JBOD, sequential I/O) or NVMe for low latency
- Network: 25Gbps (network is often bottleneck)

Configuration:
- num.partitions: Based on parallelism needs (e.g., 100-1000 per topic)
- replication.factor: 3
- min.insync.replicas: 2
- compression.type: lz4 or zstd (reduces I/O and network)
- log.retention.hours: Based on use case (72h typical)
- log.segment.bytes: 1GB
- num.io.threads: 16
- num.network.threads: 8

Tiered storage (Kafka 3.6+):
- Hot data: Local disk (recent, fast access)
- Cold data: S3/HDFS (older, cheaper, transparently fetched)
- Enables: Long retention without proportional local disk
```

---

## Scenario-Based Questions

### Scenario 1: Event-Driven Microservices Architecture

```
Services communicate via Kafka topics:

Order Service → topic: "orders"
    → Inventory Service (reserve stock)
    → Payment Service (charge customer)
    → Notification Service (send email)
    → Analytics Service (track metrics)

Saga pattern for distributed transactions:
1. Order Service creates order, publishes OrderCreated
2. Payment Service processes payment, publishes PaymentCompleted/Failed
3. Inventory Service reserves stock, publishes StockReserved/Failed
4. If any fails: Compensation events trigger rollback

Key design:
- Each service has own consumer group (independent processing)
- Retry topics for failed processing (orders-retry-1, orders-retry-2, orders-dlq)
- Schema registry for event contract management
- Exactly-once processing within each service
```

### Scenario 2: CDC Pipeline (Database → Kafka → Downstream)

```
Source DB (MySQL/PostgreSQL)
    │ Debezium (CDC connector)
    ▼
Kafka (changelog topics per table)
    │
    ├──→ Elasticsearch (search index)
    ├──→ Redis (cache invalidation)
    ├──→ Data Warehouse (analytics)
    └──→ Other Microservices (event-driven)

Debezium configuration:
- Captures binlog/WAL changes in real-time
- Produces to Kafka topics: "dbserver1.schema.table"
- Message: {before: {...}, after: {...}, op: "u", ts_ms: ...}

Benefits:
- No dual-write (single source of truth in DB)
- No ETL batch jobs (real-time)
- Decoupled systems (change once, propagate everywhere)
- Event replay (re-derive downstream from Kafka)

Guarantees:
- At-least-once delivery (Debezium + Kafka producers)
- Ordering within partition (usually keyed by primary key)
- For exactly-once downstream: Idempotent consumers
```

