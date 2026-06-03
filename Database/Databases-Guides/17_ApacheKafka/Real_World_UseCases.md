# Apache Kafka - Real World Use Cases & Production Guide

## Core Concepts

### Log-Structured Append-Only Commit Log

```
                    KAFKA COMMIT LOG (Per Partition)
    ┌─────────────────────────────────────────────────────────┐
    │ Offset: 0 │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │ 7 │ 8 │ 9 │ ... │
    │  [msg] [msg] [msg] [msg] [msg] [msg] [msg] [msg] [msg] │
    └─────────────────────────────────────────────────────────┘
      ▲                              ▲                    ▲
      │                              │                    │
   Earliest                    Consumer               Latest
   (retention)                 Position              (append)

    - Immutable, append-only sequential writes
    - O(1) disk writes (sequential I/O, no random seeks)
    - Zero-copy transfer (sendfile syscall) to consumers
    - Page cache leveraged for reads (OS manages caching)
    - Segments: Active segment + sealed segments on disk
```

### Partitions and Ordering

```
    Topic: "orders" (6 partitions)
    ┌──────────────────────────────────────────────────┐
    │  P0: [o1, o7, o13, o19, ...]  ← Key: user_A     │
    │  P1: [o2, o8, o14, o20, ...]  ← Key: user_B     │
    │  P2: [o3, o9, o15, o21, ...]  ← Key: user_C     │
    │  P3: [o4, o10, o16, o22, ...] ← Key: user_D     │
    │  P4: [o5, o11, o17, o23, ...] ← Key: user_E     │
    │  P5: [o6, o12, o18, o24, ...] ← Key: user_F     │
    └──────────────────────────────────────────────────┘

    Partition Assignment: hash(key) % num_partitions
    - Ordering guaranteed ONLY within a single partition
    - Same key always goes to same partition (sticky)
    - Repartitioning (adding partitions) breaks key affinity
```

### Consumer Groups and Offsets

```
    Consumer Group: "order-service" (3 instances)
    ┌────────────────────────────────────────────────┐
    │  Consumer-1: P0, P1  (2 partitions assigned)   │
    │  Consumer-2: P2, P3  (2 partitions assigned)   │
    │  Consumer-3: P4, P5  (2 partitions assigned)   │
    └────────────────────────────────────────────────┘

    __consumer_offsets (internal topic):
    ┌─────────────────────────────────────────────┐
    │ Group: order-service, Topic: orders, P0: 42 │
    │ Group: order-service, Topic: orders, P1: 38 │
    │ Group: order-service, Topic: orders, P2: 51 │
    └─────────────────────────────────────────────┘

    - Max parallelism = number of partitions
    - If consumers > partitions → some consumers idle
    - Rebalance triggered on: join/leave/crash/partition change
    - Cooperative Sticky Assignor (incremental rebalance, Kafka 3.x+)
```

### Exactly-Once Semantics (EOS)

```
    Idempotent Producer (enable.idempotence=true):
    ┌──────────────┐          ┌──────────────┐
    │   Producer   │─────────▶│    Broker    │
    │  PID=1       │  seq=5   │              │
    │  seq=5       │─────────▶│ Dedup check: │
    │              │  seq=5   │ seq<=last?   │
    │              │ (retry)  │ → discard    │
    └──────────────┘          └──────────────┘

    Transactional Producer (read-process-write):
    ┌──────────┐    ┌──────────────┐    ┌──────────┐
    │  Input   │───▶│  Kafka       │───▶│  Output  │
    │  Topic   │    │  Streams App │    │  Topic   │
    └──────────┘    │              │    └──────────┘
                    │ BEGIN TX     │    ┌──────────┐
                    │ read offset  │───▶│ Offset   │
                    │ produce out  │    │ Commit   │
                    │ COMMIT TX    │    └──────────┘
                    └──────────────┘
    - All or nothing: output + offset commit atomic
    - isolation.level=read_committed on consumers
    - Transaction coordinator on broker manages 2PC
```

### Log Compaction vs Retention

```
    Time-Based Retention (delete policy):
    ┌─────────────────────────────────────────┐
    │ [seg1: expired] [seg2: expired] [seg3]  │
    │    ← DELETE →    ← DELETE →     ← KEEP  │
    └─────────────────────────────────────────┘
    retention.ms=604800000 (7 days)

    Log Compaction (compact policy):
    Before: K1:V1, K2:V1, K1:V2, K3:V1, K2:V2, K1:V3
    After:  K1:V3, K2:V2, K3:V1 (latest value per key kept)

    Use cases:
    - Retention: Event streams, logs, metrics
    - Compaction: Changelogs, state stores, CDC snapshots
    - Both: cleanup.policy=compact,delete
```

### ISR and Acks

```
    acks=0:  Fire and forget (no confirmation)
    acks=1:  Leader acknowledges (leader crash = data loss)
    acks=all: All ISR replicas acknowledge (strongest)

    ┌────────────────────────────────────────────────┐
    │  Topic: payments, Partition 0, RF=3            │
    │                                                │
    │  Leader (Broker 1): offset 100 ✓              │
    │  Follower (Broker 2): offset 100 ✓  ← IN ISR │
    │  Follower (Broker 3): offset 98  ✗  ← LAGGING│
    │                                                │
    │  ISR = {1, 2}  (Broker 3 removed from ISR)   │
    │  min.insync.replicas=2 → writes still succeed │
    └────────────────────────────────────────────────┘
```

### KRaft Consensus (ZooKeeper Replacement)

```
    KRaft Mode (Kafka 3.3+ production ready):
    ┌──────────────────────────────────────────────┐
    │  Controller Quorum (Raft-based)              │
    │                                              │
    │  ┌─────────┐  ┌─────────┐  ┌─────────┐    │
    │  │Controller│  │Controller│  │Controller│    │
    │  │ (Leader) │  │(Follower)│  │(Follower)│    │
    │  │ Node 1   │  │ Node 2   │  │ Node 3   │    │
    │  └─────────┘  └─────────┘  └─────────┘    │
    │       │                                      │
    │       ▼  Metadata log (replicated)           │
    │  ┌─────────────────────────────────────┐    │
    │  │ Topic configs, partitions, ISR,     │    │
    │  │ broker registrations, ACLs          │    │
    │  └─────────────────────────────────────┘    │
    └──────────────────────────────────────────────┘

    Advantages over ZooKeeper:
    - Single process (no separate ZK cluster)
    - Millions of partitions (vs ~200K with ZK)
    - Faster controller failover (~seconds vs minutes)
    - Simpler deployment and operations
```

---

## Throughput Benchmarks

| Metric | Single Broker | 6-Broker Cluster | Notes |
|--------|--------------|------------------|-------|
| Write throughput | 600-800 MB/s | 3-5 GB/s | Sequential I/O, batch compression |
| Messages/sec (small) | 2M msg/s | 10-12M msg/s | 100-byte messages |
| Messages/sec (1KB) | 700K msg/s | 4M msg/s | With lz4 compression |
| Read throughput | 1-2 GB/s | 6-10 GB/s | Page cache hits, zero-copy |
| P99 latency (acks=1) | 2-5 ms | 2-5 ms | Single partition |
| P99 latency (acks=all) | 5-15 ms | 5-15 ms | RF=3, min.insync=2 |
| Partitions/broker | 4,000 | 24,000 total | KRaft: up to 200K+ cluster-wide |
| Consumer lag recovery | 500 MB/s | - | Catch-up reads from disk |

---

## Real-World Use Cases

### 1. LinkedIn Activity Stream

**Scale:** 7+ trillion messages/day, 100+ PB storage, 7M+ msg/sec peak

LinkedIn created Kafka in 2010 to solve their activity stream pipeline.

```
    ┌──────────────────────────────────────────────────────────────┐
    │                    LINKEDIN KAFKA ARCHITECTURE                │
    │                                                              │
    │  PRODUCERS                BROKERS              CONSUMERS     │
    │  ┌──────────┐    ┌─────────────────────┐                    │
    │  │ Web App  │───▶│                     │    ┌────────────┐  │
    │  │ Servers  │    │   Kafka Cluster      │───▶│ Hadoop/    │  │
    │  │ (1000s)  │    │   (1800+ brokers)    │    │ Spark ETL  │  │
    │  └──────────┘    │                     │    └────────────┘  │
    │  ┌──────────┐    │   KRaft Controllers  │    ┌────────────┐  │
    │  │ Mobile   │───▶│   (5-node quorum)    │───▶│ Real-time  │  │
    │  │ Backend  │    │                     │    │ Rec Engine │  │
    │  └──────────┘    │   Topics: ~100K      │    └────────────┘  │
    │  ┌──────────┐    │   Partitions: 500K+  │    ┌────────────┐  │
    │  │ Service  │───▶│                     │───▶│ Search     │  │
    │  │ Mesh     │    └─────────────────────┘    │ Indexing   │  │
    │  └──────────┘                                └────────────┘  │
    │                                              ┌────────────┐  │
    │                                              │ Monitoring │  │
    │                                              │ & Alerts   │  │
    │                                              └────────────┘  │
    └──────────────────────────────────────────────────────────────┘
```

**Topic Design:**
```properties
# Activity events topic
topic.name=member-activity
num.partitions=512
replication.factor=3
retention.ms=604800000          # 7 days hot
cleanup.policy=delete
compression.type=lz4
min.insync.replicas=2

# Member profile changes (compacted)
topic.name=member-profile-changelog
num.partitions=256
replication.factor=3
cleanup.policy=compact
min.compaction.lag.ms=3600000   # 1 hour before compacting
```

**Exactly-Once Pattern:**
- Idempotent producers for deduplication across retries
- Transactional producers for cross-topic atomic writes (activity + analytics)
- Consumer group per downstream service with `read_committed` isolation

---

### 2. Netflix Real-time Data Pipeline

**Scale:** 1.4 trillion events/day, 8M+ events/sec, 24 PB/day ingested

```
    ┌──────────────────────────────────────────────────────────────┐
    │              NETFLIX KEYSTONE PIPELINE                        │
    │                                                              │
    │  PRODUCERS                                                   │
    │  ┌──────────┐    ┌─────────────────────┐                    │
    │  │ Streaming│    │                     │    ┌────────────┐  │
    │  │ Servers  │───▶│  Fronting Kafka      │───▶│ Flink      │  │
    │  │ (CDN)    │    │  (Router Cluster)    │    │ Real-time  │  │
    │  └──────────┘    │  ~36 clusters        │    │ Analytics  │  │
    │  ┌──────────┐    │  across regions      │    └────────────┘  │
    │  │ App/UI   │───▶│                     │    ┌────────────┐  │
    │  │ Events   │    │  KRaft Controllers   │───▶│ Druid/     │  │
    │  └──────────┘    │  (per cluster)       │    │ Iceberg    │  │
    │  ┌──────────┐    │                     │    └────────────┘  │
    │  │ Backend  │───▶│  MirrorMaker 2       │    ┌────────────┐  │
    │  │ Services │    │  (cross-region)      │───▶│ Elastic-   │  │
    │  └──────────┘    └─────────────────────┘    │ search     │  │
    │  ┌──────────┐                                └────────────┘  │
    │  │ QoE      │    Router topics route to      ┌────────────┐  │
    │  │ Metrics  │    consumer Kafka clusters     │ S3 (Tiered │  │
    │  └──────────┘                                │ Storage)   │  │
    │                                              └────────────┘  │
    └──────────────────────────────────────────────────────────────┘
```

**Topic Design:**
```properties
# Playback events
topic.name=playback-events
num.partitions=1024
replication.factor=3
retention.ms=86400000           # 1 day hot
remote.storage.enable=true      # Tiered to S3 after 2 hours
local.retention.ms=7200000
compression.type=zstd
max.message.bytes=1048576       # 1MB max

# QoE (Quality of Experience) metrics
topic.name=streaming-qoe
num.partitions=512
replication.factor=3
retention.ms=43200000           # 12 hours
compression.type=lz4
```

**Key Patterns:**
- Router cluster pattern: single ingestion point, routes to downstream Kafka clusters
- Cross-region replication via MirrorMaker 2 (active-active)
- Tiered storage to S3 for cost optimization (hot/cold separation)
- Schema Registry with Avro for all events (backward-compatible evolution)

---

### 3. Uber Trip Events

**Scale:** Millions of trips/sec, 30+ Kafka clusters, petabytes/day

```
    ┌──────────────────────────────────────────────────────────────┐
    │                UBER KAFKA ARCHITECTURE                        │
    │                                                              │
    │  PRODUCERS                                                   │
    │  ┌──────────┐    ┌─────────────────────┐                    │
    │  │ Driver   │    │                     │    ┌────────────┐  │
    │  │ App GPS  │───▶│  Regional Kafka      │───▶│ Real-time  │  │
    │  │ (1M+    │    │  Cluster             │    │ Dispatch   │  │
    │  │  active) │    │  (100+ brokers)      │    │ (matching) │  │
    │  └──────────┘    │                     │    └────────────┘  │
    │  ┌──────────┐    │  KRaft Quorum        │    ┌────────────┐  │
    │  │ Rider    │───▶│  (5 controllers)     │───▶│ ETA/       │  │
    │  │ App      │    │                     │    │ Pricing    │  │
    │  └──────────┘    │  Topic: trip-events  │    └────────────┘  │
    │  ┌──────────┐    │  Partitions: 2048    │    ┌────────────┐  │
    │  │ Payment  │───▶│  RF: 3              │───▶│ Flink      │  │
    │  │ Service  │    │                     │    │ Fraud Det. │  │
    │  └──────────┘    └─────────────────────┘    └────────────┘  │
    │  ┌──────────┐         │                      ┌────────────┐  │
    │  │ Mapping  │─────────┘                     │ HDFS/Hudi  │  │
    │  │ Service  │                                │ Analytics  │  │
    │  └──────────┘                                └────────────┘  │
    └──────────────────────────────────────────────────────────────┘
```

**Topic Design:**
```properties
# Trip lifecycle events
topic.name=trip-events
num.partitions=2048
replication.factor=3
min.insync.replicas=2
retention.ms=259200000          # 3 days
compression.type=zstd
message.timestamp.type=LogAppendTime

# GPS location stream (high volume, short retention)
topic.name=driver-locations
num.partitions=4096
replication.factor=2            # Lower RF acceptable for ephemeral data
retention.ms=3600000            # 1 hour
cleanup.policy=delete
compression.type=lz4

# Payment events (exactly-once critical)
topic.name=payment-events
num.partitions=512
replication.factor=3
min.insync.replicas=2
enable.idempotence=true         # Producer-side
```

**Exactly-Once for Payments:**
```java
// Uber uses transactional producers for payment flows
Properties props = new Properties();
props.put("transactional.id", "payment-processor-" + instanceId);
props.put("enable.idempotence", "true");
props.put("acks", "all");

producer.initTransactions();
producer.beginTransaction();
producer.send(new ProducerRecord<>("payment-completed", key, value));
producer.sendOffsetsToTransaction(offsets, groupMetadata);
producer.commitTransaction();
```

---

### 4. Walmart Real-time Inventory

**Scale:** 10,500+ stores, 100M+ SKUs, sub-second inventory updates

```
    ┌──────────────────────────────────────────────────────────────┐
    │           WALMART INVENTORY PIPELINE                          │
    │                                                              │
    │  PRODUCERS                                                   │
    │  ┌──────────┐    ┌─────────────────────┐                    │
    │  │ POS      │    │                     │    ┌────────────┐  │
    │  │ Systems  │───▶│  Kafka Cluster       │───▶│ Inventory  │  │
    │  │ (10K+   │    │  (200+ brokers)      │    │ Service    │  │
    │  │  stores) │    │                     │    │ (real-time)│  │
    │  └──────────┘    │  KRaft Quorum        │    └────────────┘  │
    │  ┌──────────┐    │                     │    ┌────────────┐  │
    │  │ Warehouse│───▶│  Topic: inventory-   │───▶│ Store      │  │
    │  │ Mgmt     │    │    updates           │    │ Fulfillment│  │
    │  └──────────┘    │  Partitions: 1024    │    └────────────┘  │
    │  ┌──────────┐    │  Key: store_id+sku   │    ┌────────────┐  │
    │  │ eCommerce│───▶│                     │───▶│ Online     │  │
    │  │ Orders   │    │  Compacted changelog: │    │ Stock API  │  │
    │  └──────────┘    │  inventory-state      │    └────────────┘  │
    │  ┌──────────┐    │                     │    ┌────────────┐  │
    │  │ Supplier │───▶│                     │───▶│ Analytics/ │  │
    │  │ Feeds    │    └─────────────────────┘    │ Demand     │  │
    │  └──────────┘                                └────────────┘  │
    └──────────────────────────────────────────────────────────────┘
```

**Topic Design:**
```properties
# Inventory change events (event sourcing)
topic.name=inventory-updates
num.partitions=1024
replication.factor=3
min.insync.replicas=2
retention.ms=604800000          # 7 days
compression.type=zstd
# Key: store_id:sku_id → ensures ordering per item per store

# Inventory state snapshot (compacted)
topic.name=inventory-state
num.partitions=1024
replication.factor=3
cleanup.policy=compact
min.compaction.lag.ms=60000     # 1 min before compacting
segment.ms=3600000              # Hourly segments
# Key: store_id:sku_id, Value: current quantity + metadata
```

**Exactly-Once Pattern:**
- Kafka Streams with exactly-once (`processing.guarantee=exactly_once_v2`)
- KTable backed by `inventory-state` compacted topic
- Idempotent updates keyed by `store_id:sku_id:event_id`

---

### 5. Confluent Data Mesh (Microservices Backbone)

**Pattern:** Kafka as the central nervous system connecting microservices

```
    ┌──────────────────────────────────────────────────────────────┐
    │            DATA MESH / EVENT-DRIVEN ARCHITECTURE              │
    │                                                              │
    │  Domain: Orders    Domain: Payments    Domain: Shipping      │
    │  ┌──────────┐     ┌──────────┐        ┌──────────┐         │
    │  │ Order    │     │ Payment  │        │ Shipping │         │
    │  │ Service  │     │ Service  │        │ Service  │         │
    │  └────┬─────┘     └────┬─────┘        └────┬─────┘         │
    │       │                │                    │               │
    │       ▼                ▼                    ▼               │
    │  ┌─────────────────────────────────────────────────────┐   │
    │  │              KAFKA (Shared Nothing)                   │   │
    │  │                                                     │   │
    │  │  orders.created    payments.completed  shipments.*   │   │
    │  │  orders.updated    payments.failed     tracking.*    │   │
    │  │  orders.cancelled  refunds.*                         │   │
    │  │                                                     │   │
    │  │  Schema Registry (Avro/Protobuf contracts)          │   │
    │  │  ┌─────────────────────────────────────────────┐   │   │
    │  │  │ orders-value: v1, v2, v3 (backward compat)  │   │   │
    │  │  │ payments-value: v1, v2 (full compat)        │   │   │
    │  │  └─────────────────────────────────────────────┘   │   │
    │  │                                                     │   │
    │  │  KRaft Controllers (3-5 nodes)                      │   │
    │  │  Brokers: 12-30 (per environment)                   │   │
    │  └─────────────────────────────────────────────────────┘   │
    │       │                │                    │               │
    │       ▼                ▼                    ▼               │
    │  ┌──────────┐     ┌──────────┐        ┌──────────┐         │
    │  │ Analytics│     │ Notif.   │        │ Customer │         │
    │  │ (Flink)  │     │ Service  │        │ Service  │         │
    │  └──────────┘     └──────────┘        └──────────┘         │
    └──────────────────────────────────────────────────────────────┘
```

**Topic Design (Domain-Driven):**
```properties
# Domain event topics follow: <domain>.<entity>.<event>
topic.name=orders.order.created
num.partitions=64
replication.factor=3
min.insync.replicas=2
retention.ms=2592000000         # 30 days
cleanup.policy=delete
compression.type=zstd

# CQRS materialized view (compacted)
topic.name=orders.order.state
num.partitions=64
replication.factor=3
cleanup.policy=compact

# Dead letter queue
topic.name=orders.order.dlq
num.partitions=8
replication.factor=3
retention.ms=604800000          # 7 days
```

**Exactly-Once Pattern (Saga/Choreography):**
```
Order Created → Payment Service reads → Payment Completed → Shipping reads → Shipment Created
     │                                         │
     └─── (on failure) ────────────────────────┘──→ Compensation events
```
- Each service: transactional producer (consume + produce atomically)
- Outbox pattern alternative: CDC from DB → Kafka via Debezium connector
- Schema Registry enforces API contracts between domains

---

## Replication Deep Dive

### ISR (In-Sync Replicas) Diagram

```
    Topic: payments, Partition 0, Replication Factor = 3

    ┌─────────────────────────────────────────────────────────┐
    │                                                         │
    │   Broker 1 (LEADER)         Writes: offset 0─100       │
    │   ┌───────────────────────────────────────────┐        │
    │   │ 0 │ 1 │ 2 │ ... │ 98 │ 99 │ 100 │        │        │
    │   └───────────────────────────────────────────┘        │
    │              HW (High Watermark) = 99                   │
    │                                                         │
    │   Broker 2 (FOLLOWER, IN ISR)   Caught up              │
    │   ┌───────────────────────────────────────────┐        │
    │   │ 0 │ 1 │ 2 │ ... │ 98 │ 99 │              │        │
    │   └───────────────────────────────────────────┘        │
    │              LEO = 99  ✓ (within replica.lag.time)      │
    │                                                         │
    │   Broker 3 (FOLLOWER, OUT OF ISR)  Lagging             │
    │   ┌────────────────────────────────┐                   │
    │   │ 0 │ 1 │ 2 │ ... │ 85 │        │                   │
    │   └────────────────────────────────┘                   │
    │              LEO = 85  ✗ (exceeded replica.lag.time)    │
    │                                                         │
    │   ISR = {Broker 1, Broker 2}                           │
    │   HW = min(LEO of all ISR members) = 99                │
    │   Consumers can only read up to HW                     │
    └─────────────────────────────────────────────────────────┘

    replica.lag.time.max.ms=30000  (30s before removal from ISR)
```

### Leader Election

```
    Normal Leader Election:
    1. Leader (Broker 1) fails / shuts down
    2. Controller detects via heartbeat timeout
    3. Controller picks new leader from ISR (Broker 2)
    4. Controller updates metadata, notifies all brokers
    5. Producers/Consumers redirect to new leader
    
    Timeline: ~100-500ms with KRaft (seconds with ZooKeeper)
```

### Unclean Leader Election Trade-offs

```
    Scenario: All ISR replicas are down, only out-of-sync replica available

    unclean.leader.election.enable=true:
    ┌──────────────────────────────────────────┐
    │ + Availability: partition comes online    │
    │ - Durability: messages 86-100 are LOST   │
    │ - Consistency: consumers see gap          │
    │                                          │
    │ Use for: Metrics, logs, non-critical data│
    └──────────────────────────────────────────┘

    unclean.leader.election.enable=false (DEFAULT):
    ┌──────────────────────────────────────────┐
    │ + Durability: no data loss               │
    │ - Availability: partition OFFLINE until   │
    │   an ISR member recovers                 │
    │                                          │
    │ Use for: Payments, orders, financial data│
    └──────────────────────────────────────────┘
```

### min.insync.replicas

```
    RF=3, min.insync.replicas=2, acks=all:

    Scenario A: All 3 replicas healthy
    → Write succeeds (3 >= 2) ✓

    Scenario B: 1 follower down, ISR={leader, follower}
    → Write succeeds (2 >= 2) ✓

    Scenario C: 2 followers down, ISR={leader}
    → Write REJECTED: NotEnoughReplicasException (1 < 2) ✗
    → Guarantees data written to at least 2 nodes

    Golden Rule: RF >= min.insync.replicas + 1
    (allows 1 broker to be down for maintenance)
```

### Rack-Aware Replication

```
    broker.rack=us-east-1a  (Broker 1, 4)
    broker.rack=us-east-1b  (Broker 2, 5)
    broker.rack=us-east-1c  (Broker 3, 6)

    Topic with RF=3:
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │  Rack A    │  │  Rack B    │  │  Rack C    │
    │            │  │            │  │            │
    │ Broker 1   │  │ Broker 2   │  │ Broker 3   │
    │ P0:Leader  │  │ P0:Follower│  │ P0:Follower│
    │ P1:Follower│  │ P1:Leader  │  │ P1:Follower│
    │ P2:Follower│  │ P2:Follower│  │ P2:Leader  │
    └────────────┘  └────────────┘  └────────────┘

    Survives entire rack failure with zero data loss
```

### MirrorMaker 2 (Cross-DC Replication)

```
    ┌─────────────────┐          ┌─────────────────┐
    │  DC: us-east    │          │  DC: us-west    │
    │                 │          │                 │
    │  Kafka Cluster  │◀────────▶│  Kafka Cluster  │
    │  (Primary)      │  MM2     │  (Secondary)    │
    │                 │ (async)  │                 │
    │  orders         │────────▶ │  us-east.orders │
    │  payments       │────────▶ │  us-east.payments│
    │                 │          │                 │
    │  us-west.events │◀──────── │  events         │
    └─────────────────┘          └─────────────────┘

    MirrorMaker 2 Features:
    - Preserves offsets (offset translation)
    - Topic renaming (source.topic prefix)
    - Active-Active or Active-Passive
    - Automatic consumer group offset sync
    - RPO: seconds (async), depends on cross-DC latency
```

---

## Scalability

### Partition-Based Parallelism

```
    SCALING CONSUMERS WITH PARTITIONS

    Topic: events (12 partitions)

    Phase 1: 3 consumers
    ┌────────────────────────────────────────┐
    │  Consumer 1: P0, P1, P2, P3           │
    │  Consumer 2: P4, P5, P6, P7           │
    │  Consumer 3: P8, P9, P10, P11         │
    └────────────────────────────────────────┘
    Throughput: 3x single consumer

    Phase 2: Scale to 6 consumers (rebalance)
    ┌────────────────────────────────────────┐
    │  Consumer 1: P0, P1                   │
    │  Consumer 2: P2, P3                   │
    │  Consumer 3: P4, P5                   │
    │  Consumer 4: P6, P7                   │
    │  Consumer 5: P8, P9                   │
    │  Consumer 6: P10, P11                 │
    └────────────────────────────────────────┘
    Throughput: 6x single consumer

    Phase 3: Scale to 12 consumers (max parallelism)
    ┌────────────────────────────────────────┐
    │  Consumer 1-12: one partition each     │
    └────────────────────────────────────────┘
    Throughput: 12x single consumer (MAX)

    Phase 4: 13+ consumers → one is IDLE
```

### Broker Scaling

```
    Adding Broker to Cluster:

    Before (3 brokers, 12 partitions):
    Broker 1: P0,P1,P2,P3     (4 partitions, leader for 4)
    Broker 2: P4,P5,P6,P7     (4 partitions, leader for 4)
    Broker 3: P8,P9,P10,P11   (4 partitions, leader for 4)

    After adding Broker 4 (manual reassignment needed):
    Broker 1: P0,P1,P2        (3 partitions)
    Broker 2: P3,P4,P5        (3 partitions)
    Broker 3: P6,P7,P8        (3 partitions)
    Broker 4: P9,P10,P11      (3 partitions)

    Tools:
    - kafka-reassign-partitions.sh (manual)
    - Cruise Control (LinkedIn, automated rebalancing)
    - Confluent Auto Data Balancer
```

### Consumer Group Rebalancing

```
    Rebalance Strategies:

    1. Eager (stop-the-world):
       All consumers release all partitions → reassign
       Downtime: seconds to minutes

    2. Cooperative Sticky (incremental, Kafka 2.4+):
       Only affected partitions revoked → reassign
       Downtime: minimal (only migrating partitions pause)

    Config:
    partition.assignment.strategy=
      org.apache.kafka.clients.consumer.CooperativeStickyAssignor

    Static Group Membership (reduce rebalances):
    group.instance.id=consumer-host-1  # Stable identity
    session.timeout.ms=300000          # 5 min (tolerates restarts)
```

### Kafka Connect, Streams, ksqlDB

```
    ┌──────────────────────────────────────────────────────────┐
    │                 KAFKA ECOSYSTEM                           │
    │                                                          │
    │  ┌──────────────┐    ┌───────────┐    ┌──────────────┐ │
    │  │ Kafka Connect │    │   Kafka   │    │   ksqlDB     │ │
    │  │              │    │  Streams  │    │              │ │
    │  │ Source:      │    │           │    │ CREATE STREAM│ │
    │  │  - Debezium  │───▶│ Stateless:│───▶│ AS SELECT .. │ │
    │  │  - JDBC      │    │  filter   │    │ FROM stream  │ │
    │  │  - S3        │    │  map      │    │ WHERE ...    │ │
    │  │              │    │  flatMap  │    │ GROUP BY ... │ │
    │  │ Sink:        │    │           │    │ EMIT CHANGES │ │
    │  │  - Elastic   │◀───│ Stateful: │◀───│              │ │
    │  │  - JDBC      │    │  aggregate│    │ Materialized │ │
    │  │  - S3        │    │  join     │    │ Views (pull  │ │
    │  │  - BigQuery  │    │  window   │    │ queries)     │ │
    │  └──────────────┘    └───────────┘    └──────────────┘ │
    │                                                          │
    │  Connect: 100+ connectors, distributed mode, SMTs       │
    │  Streams: Library (no separate cluster), exactly-once   │
    │  ksqlDB: SQL interface over Streams, good for prototyping│
    └──────────────────────────────────────────────────────────┘
```

### Tiered Storage (KIP-405)

```
    ┌──────────────────────────────────────────────────────┐
    │            TIERED STORAGE ARCHITECTURE                │
    │                                                      │
    │  Broker Local Disk (NVMe/SSD):                       │
    │  ┌────────────────────────────────────────────┐     │
    │  │ Active Segment │ Recent Segments (hot data) │     │
    │  │ (writes here)  │ (last 2-6 hours)           │     │
    │  └────────────────────────────────────────────┘     │
    │            │ (background upload)                      │
    │            ▼                                          │
    │  Remote Storage (S3/GCS/ADLS):                       │
    │  ┌────────────────────────────────────────────┐     │
    │  │ Older Segments (cold data, days/months)     │     │
    │  │ Cost: ~$0.023/GB/month (S3 Standard)        │     │
    │  │ vs $0.10+/GB/month (EBS gp3)               │     │
    │  └────────────────────────────────────────────┘     │
    │                                                      │
    │  Benefits:                                           │
    │  - 10x+ storage cost reduction                      │
    │  - Broker scaling independent of storage             │
    │  - Infinite retention practical                      │
    │  - Faster broker recovery (less local data)          │
    └──────────────────────────────────────────────────────┘

    Config:
    remote.log.storage.system.enable=true
    remote.log.storage.manager.class.name=...S3RemoteLogStorageManager
    local.retention.ms=7200000     # 2 hours local
    retention.ms=2592000000        # 30 days total (remote)
```

---

## Production Setup

### Broker Configuration

```properties
# ─── KRaft Mode (server.properties) ───
process.roles=broker              # Or: controller, or: broker,controller (combined)
node.id=1
controller.quorum.voters=1@ctrl1:9093,2@ctrl2:9093,3@ctrl3:9093
controller.listener.names=CONTROLLER

# ─── Core Broker Settings ───
num.partitions=12                 # Default for auto-created topics
default.replication.factor=3
min.insync.replicas=2
auto.create.topics.enable=false   # ALWAYS false in production

# ─── Log Settings ───
log.dirs=/data/kafka-logs-1,/data/kafka-logs-2  # Multiple disks
log.retention.hours=168           # 7 days default
log.retention.bytes=-1            # Unlimited (use time-based)
log.segment.bytes=1073741824      # 1GB segments
log.cleanup.policy=delete

# ─── Replication ───
num.replica.fetchers=4
replica.lag.time.max.ms=30000
unclean.leader.election.enable=false

# ─── Network & Threads ───
num.network.threads=8             # Network I/O threads
num.io.threads=16                 # Disk I/O threads
socket.send.buffer.bytes=102400
socket.receive.buffer.bytes=102400
socket.request.max.bytes=104857600

# ─── Performance ───
compression.type=producer         # Honor producer's compression
message.max.bytes=1048576         # 1MB max message
replica.fetch.max.bytes=1048576
```

### JVM & OS Tuning

```bash
# ─── JVM Settings (kafka-server-start.sh) ───
export KAFKA_HEAP_OPTS="-Xms6g -Xmx6g"    # 6GB heap (don't go higher, page cache matters more)
export KAFKA_JVM_PERFORMANCE_OPTS="
  -server
  -XX:+UseG1GC
  -XX:MaxGCPauseMillis=20
  -XX:InitiatingHeapOccupancyPercent=35
  -XX:+ExplicitGCInvokesConcurrent
  -XX:G1HeapRegionSize=16M
  -XX:MetaspaceSize=96m
  -XX:MinMetaspaceFreeRatio=50
  -XX:MaxMetaspaceFreeRatio=80
  -Djava.net.preferIPv4Stack=true"

# ─── OS Tuning (sysctl.conf) ───
# File descriptors (Kafka opens many files)
fs.file-max=1000000
# ulimit -n 100000 (per process)

# Virtual memory
vm.swappiness=1                   # Avoid swap at all costs
vm.dirty_ratio=60
vm.dirty_background_ratio=5

# Network
net.core.wmem_default=131072
net.core.rmem_default=131072
net.core.wmem_max=2097152
net.core.rmem_max=2097152
net.ipv4.tcp_window_scaling=1
net.ipv4.tcp_max_syn_backlog=4096

# ─── Disk ───
# Use XFS filesystem
# Mount with noatime,nodiratime
# Separate disks for logs vs OS
# RAID-10 or JBOD (Kafka handles replication)
```

### KRaft Mode Setup

```properties
# Controller nodes (dedicated or combined with broker):
# server.properties for controller-only node
process.roles=controller
node.id=1
controller.quorum.voters=1@ctrl1:9093,2@ctrl2:9093,3@ctrl3:9093
controller.listener.names=CONTROLLER
listeners=CONTROLLER://ctrl1:9093

# Format storage (one-time):
# kafka-storage.sh format -t <cluster-id> -c server.properties

# Migration from ZooKeeper:
# 1. Deploy controllers alongside ZK
# 2. Enable migration mode
# 3. Migrate brokers one by one
# 4. Decommission ZooKeeper
```

### Monitoring

```
    ┌─────────────────────────────────────────────────────────┐
    │                MONITORING STACK                          │
    │                                                         │
    │  Kafka Broker JMX ──▶ Prometheus JMX Exporter ──▶ Prom │
    │                                                    │    │
    │  Key Metrics:                                 Grafana   │
    │  ├─ UnderReplicatedPartitions (>0 = problem)       │    │
    │  ├─ ActiveControllerCount (must be 1)              │    │
    │  ├─ OfflinePartitionsCount (must be 0)             │    │
    │  ├─ RequestHandlerAvgIdlePercent (<0.3 = overload) │    │
    │  ├─ NetworkProcessorAvgIdlePercent                  │    │
    │  ├─ BytesInPerSec / BytesOutPerSec                 │    │
    │  ├─ MessagesInPerSec                               │    │
    │  ├─ FetchConsumerTotalTimeMs (P99)                 │    │
    │  ├─ ProduceTotalTimeMs (P99)                       │    │
    │  └─ LogFlushRateAndTimeMs                          │    │
    │                                                         │
    │  Consumer Lag:                                           │
    │  ├─ kafka_consumer_group_lag (per partition)            │
    │  └─ Burrow (LinkedIn lag monitoring)                    │
    │                                                         │
    │  Alerts:                                                │
    │  ├─ UnderReplicatedPartitions > 0 for 5min → P1        │
    │  ├─ OfflinePartitions > 0 → P0 (page)                  │
    │  ├─ Consumer lag growing > 10min → P2                   │
    │  └─ Disk usage > 80% → P2                              │
    └─────────────────────────────────────────────────────────┘
```

### Schema Registry

```
    ┌────────────────────────────────────────────────────┐
    │  Producer ──▶ Schema Registry ──▶ Broker           │
    │     │              │                    │          │
    │     │  1. Register │schema (Avro/Proto) │          │
    │     │  2. Get schema ID                 │          │
    │     │  3. Serialize: [magic][id][data]  │          │
    │     │                                   │          │
    │  Consumer ◀── Schema Registry           │          │
    │     │  1. Read schema ID from message   │          │
    │     │  2. Fetch schema by ID (cached)   │          │
    │     │  3. Deserialize                   │          │
    └────────────────────────────────────────────────────┘

    Compatibility Modes:
    - BACKWARD (default): new schema can read old data
    - FORWARD: old schema can read new data
    - FULL: both directions
    - NONE: no compatibility check (dangerous)

    Best Practice: BACKWARD_TRANSITIVE for event schemas
```

### Security

```properties
# ─── Encryption (SSL/TLS) ───
listeners=PLAINTEXT://internal:9092,SSL://external:9093
ssl.keystore.location=/var/ssl/kafka.keystore.jks
ssl.keystore.password=${KEYSTORE_PASS}
ssl.key.password=${KEY_PASS}
ssl.truststore.location=/var/ssl/kafka.truststore.jks
ssl.client.auth=required          # Mutual TLS

# ─── Authentication (SASL) ───
listeners=SASL_SSL://broker:9094
sasl.enabled.mechanisms=SCRAM-SHA-512
# Or: OAUTHBEARER for token-based (Keycloak, Azure AD)
sasl.mechanism.inter.broker.protocol=SCRAM-SHA-512

# ─── Authorization (ACLs) ───
authorizer.class.name=kafka.security.authorizer.AclAuthorizer
super.users=User:admin

# Example ACLs:
# kafka-acls.sh --add --allow-principal User:order-service \
#   --operation Read --operation Write --topic orders \
#   --group order-consumer-group

# ─── Production Security Checklist ───
# ✓ SASL_SSL for all client connections
# ✓ SSL for inter-broker communication
# ✓ ACLs with least-privilege per service
# ✓ Encrypt data at rest (disk encryption)
# ✓ Network segmentation (brokers in private subnet)
# ✓ Audit logging enabled
# ✓ Schema Registry with authentication
```

### Capacity Planning

```
    Formula:
    ┌────────────────────────────────────────────────────────┐
    │  Storage per broker per day =                          │
    │    (msg_size × msgs_per_sec × 86400 × RF) / brokers   │
    │                                                        │
    │  Example: 1KB × 100K/s × 86400 × 3 / 6 brokers       │
    │         = 4.3 TB/broker/day                            │
    │                                                        │
    │  With 7-day retention: 4.3 × 7 = 30 TB/broker         │
    │  With compression (4:1): ~7.5 TB/broker                │
    ├────────────────────────────────────────────────────────┤
    │  Network per broker =                                  │
    │    ingress: (msg_size × msgs_per_sec) / brokers        │
    │    egress: ingress × (RF-1 + num_consumers)            │
    │                                                        │
    │  Example: 1KB × 100K/s / 6 = 16 MB/s ingress          │
    │  Egress: 16 × (2 replication + 3 consumers) = 80 MB/s │
    │  → 10Gbps NIC recommended                              │
    ├────────────────────────────────────────────────────────┤
    │  Hardware Recommendations (per broker):                 │
    │  CPU: 16-24 cores                                      │
    │  RAM: 32-64 GB (6GB heap + rest for page cache)        │
    │  Disk: 6-12 × 2TB NVMe SSD (JBOD)                     │
    │  Network: 10 Gbps (25 Gbps for high-throughput)        │
    │  OS: Linux (RHEL/Ubuntu), XFS filesystem               │
    └────────────────────────────────────────────────────────┘

    Partition Count Guidelines:
    - Target: 100 MB/s per partition throughput
    - partitions = max(throughput/100MB, consumer_parallelism)
    - Upper bound: 4000 partitions/broker (KRaft)
    - More partitions = more memory, longer rebalance, more files
```

---

## Quick Reference: Production Checklist

| Category | Setting | Value | Why |
|----------|---------|-------|-----|
| Durability | `acks` | `all` | No data loss |
| Durability | `min.insync.replicas` | `2` | Survive 1 broker loss |
| Durability | `replication.factor` | `3` | Standard for production |
| Durability | `unclean.leader.election` | `false` | Prevent data loss |
| Performance | `compression.type` | `lz4` or `zstd` | 4x less network/disk |
| Performance | `batch.size` (producer) | `65536` | Batch for throughput |
| Performance | `linger.ms` (producer) | `5-20` | Allow batching |
| Performance | `fetch.min.bytes` (consumer) | `1048576` | Reduce fetch requests |
| Reliability | `enable.idempotence` | `true` | Deduplicate retries |
| Reliability | `max.in.flight.requests` | `5` | Safe with idempotence |
| Operations | `auto.create.topics.enable` | `false` | Explicit topic mgmt |
| Operations | `log.retention.hours` | `168` | 7 days default |
| Operations | `num.partitions` | `12-64` | Based on throughput needs |
