# Apache Kafka - Staff Architect Deep Dive

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Internal Mechanics](#2-internal-mechanics)
3. [Producer Internals](#3-producer-internals)
4. [Consumer Internals](#4-consumer-internals)
5. [Kafka Streams](#5-kafka-streams)
6. [Kafka Connect](#6-kafka-connect)
7. [Performance Tuning](#7-performance-tuning)
8. [Schema Registry](#8-schema-registry)
9. [Security](#9-security)
10. [KRaft Mode](#10-kraft-mode)
11. [Exactly-Once Semantics](#11-exactly-once-semantics)
12. [Multi-DC Deployment](#12-multi-dc-deployment)
13. [Capacity Planning](#13-capacity-planning)
14. [Common Anti-Patterns](#14-common-anti-patterns)

---

## 1. Architecture Overview

### Core Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      KAFKA CLUSTER                              │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Broker 0 │  │ Broker 1 │  │ Broker 2 │  │ Broker 3 │       │
│  │          │  │          │  │          │  │          │       │
│  │ Topic-A  │  │ Topic-A  │  │ Topic-A  │  │ Topic-B  │       │
│  │ P0(L)    │  │ P0(F)    │  │ P1(L)    │  │ P0(L)    │       │
│  │ P1(F)    │  │ P2(L)    │  │ P2(F)    │  │ P1(L)    │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │              │              │              │             │
│  ┌────┴──────────────┴──────────────┴──────────────┴─────┐      │
│  │              ZooKeeper / KRaft Quorum                  │      │
│  │  (Metadata, Leader Election, Configuration)           │      │
│  └───────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
         ▲                                        │
         │                                        ▼
┌────────┴────────┐                    ┌──────────────────┐
│   Producers     │                    │    Consumers      │
│                 │                    │  (Consumer Groups) │
│ App1, App2, ... │                    │  CG1, CG2, ...    │
└─────────────────┘                    └──────────────────┘
```

### Broker Architecture

A Kafka broker is a JVM process that:
- Stores data on local disk as **log segments**
- Handles produce/fetch requests from clients
- Participates in replication protocol
- Reports metadata to ZooKeeper/KRaft controller

**Key broker components:**

```
┌──────────────────────────────────────────────────────┐
│                    KAFKA BROKER                       │
│                                                      │
│  ┌──────────────┐    ┌────────────────────────┐      │
│  │ Network Layer │    │   Request Handler Pool  │      │
│  │ (Acceptor +   │───▶│   (num.io.threads)      │      │
│  │  Processors)  │    │                        │      │
│  └──────────────┘    └──────────┬─────────────┘      │
│                                 │                     │
│  ┌──────────────┐    ┌──────────▼─────────────┐      │
│  │  Purgatory    │    │    API Layer            │      │
│  │ (Delayed Ops) │    │  Produce/Fetch/Admin    │      │
│  └──────────────┘    └──────────┬─────────────┘      │
│                                 │                     │
│  ┌──────────────┐    ┌──────────▼─────────────┐      │
│  │  Replica Mgr  │    │    Log Manager          │      │
│  │  (ISR, HW,    │◀──▶│  (Segments, Index,      │      │
│  │   Leader)     │    │   Compaction)           │      │
│  └──────────────┘    └──────────┬─────────────┘      │
│                                 │                     │
│                      ┌──────────▼─────────────┐      │
│                      │    OS Page Cache         │      │
│                      │    + Disk (Zero-Copy)    │      │
│                      └────────────────────────┘      │
└──────────────────────────────────────────────────────┘
```

### Topics, Partitions, and Segments

**Topic** = Logical stream of records, split into partitions.

**Partition** = Ordered, immutable append-only log. Each record gets a monotonically increasing **offset**.

```
Topic: orders (3 partitions, replication-factor=3)

Partition 0:  [0] [1] [2] [3] [4] [5] [6] [7] [8] ...
Partition 1:  [0] [1] [2] [3] [4] [5] ...
Partition 2:  [0] [1] [2] [3] [4] [5] [6] [7] [8] [9] [10] ...
                                                         ▲
                                                     Log End Offset
```

**Segment** = Physical file on disk. Each partition is broken into segments.

```
Partition Directory: /data/kafka-logs/orders-0/
├── 00000000000000000000.log      ← Base offset 0 (closed/immutable)
├── 00000000000000000000.index    ← Offset index
├── 00000000000000000000.timeindex← Time index
├── 00000000000005242880.log      ← Base offset 5242880 (active)
├── 00000000000005242880.index
├── 00000000000005242880.timeindex
├── leader-epoch-checkpoint
└── partition.metadata
```

**Segment rolling conditions** (new segment created when any is met):
- `log.segment.bytes` (default: 1GB)
- `log.roll.ms` / `log.roll.hours` (default: 7 days)
- Index file is full (`log.index.size.max.bytes`, default: 10MB)

### Log Structure Internals

Each `.log` file contains record batches:

```
┌─────────────────────────────────────────────────────┐
│                  Record Batch                        │
├─────────────────────────────────────────────────────┤
│ Base Offset (8 bytes)                                │
│ Batch Length (4 bytes)                                │
│ Partition Leader Epoch (4 bytes)                     │
│ Magic (1 byte) = 2                                   │
│ CRC (4 bytes)                                        │
│ Attributes (2 bytes) - compression, timestamp type   │
│ Last Offset Delta (4 bytes)                          │
│ First Timestamp (8 bytes)                            │
│ Max Timestamp (8 bytes)                              │
│ Producer ID (8 bytes)                                │
│ Producer Epoch (2 bytes)                             │
│ First Sequence (4 bytes)                             │
│ Number of Records (4 bytes)                          │
├─────────────────────────────────────────────────────┤
│ Record 0: [length, attrs, timestampDelta,            │
│            offsetDelta, key, value, headers]          │
│ Record 1: ...                                        │
│ Record N: ...                                        │
└─────────────────────────────────────────────────────┘
```

**Index file** = Sparse index mapping offset → position in .log file:
```
Offset 0     → Position 0
Offset 4096  → Position 65732
Offset 8192  → Position 131287
...
```

Controlled by `log.index.interval.bytes` (default: 4KB). Every 4KB of messages written, one index entry is added.

**Time Index** = Maps timestamp → offset for time-based lookups.

---

## 2. Internal Mechanics

### Leader Election

Every partition has exactly ONE leader and zero or more followers.

```
Partition 0: Leader=Broker0, Followers=[Broker1, Broker2]

Broker 0 (Leader)        Broker 1 (Follower)     Broker 2 (Follower)
┌────────────┐           ┌────────────┐           ┌────────────┐
│ [0][1][2]  │──fetch──▶ │ [0][1][2]  │           │ [0][1]     │
│ [3][4][5]  │           │ [3][4]     │           │            │
│     ▲      │           │            │           │            │
│  Producers │           │  (ISR)     │           │  (NOT ISR) │
│  write here│           │            │           │  (catching  │
└────────────┘           └────────────┘           │   up)      │
                                                  └────────────┘
```

**Leader election process (ZooKeeper mode):**
1. Controller (one broker elected via ZK ephemeral node) monitors broker liveness
2. When leader broker fails, controller selects new leader from ISR
3. Controller writes new leader info to ZooKeeper
4. Controller sends LeaderAndIsr request to all replicas
5. New leader starts accepting produce/fetch requests

**Leader election process (KRaft mode):**
1. Controller quorum (Raft-based) maintains metadata log
2. Active controller detects broker failure via heartbeats
3. Selects new leader from ISR
4. Propagates via metadata log to all brokers

### In-Sync Replicas (ISR)

ISR = Set of replicas that are "caught up" to the leader.

**A replica is removed from ISR when:**
- It hasn't fetched from leader for `replica.lag.time.max.ms` (default: 30s)
- (Pre-0.9: also based on `replica.lag.max.messages` - REMOVED)

**ISR shrinking/expanding timeline:**
```
Time 0s:    ISR = [0, 1, 2]  (all caught up)
Time 15s:   Broker 2 slows down (GC pause)
Time 30s:   Broker 2 exceeds replica.lag.time.max.ms
            ISR = [0, 1]  (ISR SHRINK - URP increases)
Time 35s:   Broker 2 recovers, catches up
Time 36s:   ISR = [0, 1, 2]  (ISR EXPAND)
```

**Key metrics to monitor:**
- `kafka.server:type=ReplicaManager,name=UnderReplicatedPartitions`
- `kafka.server:type=ReplicaManager,name=IsrShrinksPerSec`
- `kafka.server:type=ReplicaManager,name=IsrExpandsPerSec`

### High Watermark (HW) and Log End Offset (LEO)

```
Leader (Broker 0):
Offset:  [0] [1] [2] [3] [4] [5] [6] [7]
                              ▲           ▲
                              HW          LEO

Follower 1 (Broker 1):
Offset:  [0] [1] [2] [3] [4] [5]
                              ▲    ▲
                              HW   LEO

Follower 2 (Broker 2):
Offset:  [0] [1] [2] [3] [4]
                         ▲    ▲
                         HW   LEO
```

**HW** = Minimum LEO across all ISR replicas. Consumers can only read up to HW.
**LEO** = Offset of next record to be written to this replica.

**HW update flow:**
1. Producer sends record to leader → Leader appends → LEO increases
2. Followers fetch from leader → Followers append → Their LEO increases
3. Followers report their LEO in fetch request
4. Leader calculates HW = min(LEO of all ISR replicas)
5. Leader returns HW in fetch response to followers
6. Followers update their local HW

### Leader Epoch

**Problem with HW-only approach (pre-0.11):**
After leader failure + follower truncation, data inconsistency is possible.

**Leader Epoch** = Monotonically increasing number assigned to each new leader. Stored in `leader-epoch-checkpoint` file.

```
Leader Epoch File:
0  0       ← Epoch 0 started at offset 0
1  5242880 ← Epoch 1 started at offset 5242880
2  7340032 ← Epoch 2 started at offset 7340032
```

**Truncation with epochs:**
1. Follower restarts
2. Sends OffsetsForLeaderEpochRequest to leader
3. Leader responds with end offset for that epoch
4. Follower truncates to that offset (not HW)
5. Resumes fetching

### Unclean Leader Election

`unclean.leader.election.enable=false` (default since 0.11):
- If ALL ISR replicas are down, partition becomes unavailable
- No data loss, but availability is sacrificed

`unclean.leader.election.enable=true`:
- An out-of-sync replica can become leader
- **DATA LOSS RISK**: Messages acknowledged by old leader but not replicated will be lost
- Use only when availability > durability (e.g., metrics, logs)

---

## 3. Producer Internals

### Producer Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        KAFKA PRODUCER                            │
│                                                                  │
│  ┌────────┐     ┌──────────┐     ┌───────────────┐              │
│  │ User   │────▶│Serializer│────▶│  Partitioner   │              │
│  │ Thread │     │(Key+Val) │     │(RoundRobin/    │              │
│  └────────┘     └──────────┘     │ Hash/Sticky/   │              │
│                                  │ Custom)        │              │
│                                  └───────┬────────┘              │
│                                          │                       │
│                                  ┌───────▼────────┐              │
│                                  │ Record          │              │
│                                  │ Accumulator     │              │
│                                  │                 │              │
│                                  │ ┌─────────────┐│              │
│                                  │ │TP0: [batch1]││              │
│                                  │ │TP1: [batch1]││              │
│                                  │ │TP2: [batch1]││              │
│                                  │ └─────────────┘│              │
│                                  └───────┬────────┘              │
│                                          │                       │
│  ┌───────────────────────────────────────▼──────────────────┐    │
│  │              Sender Thread (Background I/O)               │    │
│  │  ┌──────────┐  ┌───────────┐  ┌──────────────────┐       │    │
│  │  │  Drain   │─▶│  Group by │─▶│  NetworkClient    │       │    │
│  │  │ Batches  │  │  Broker   │  │  (Produce Request)│       │    │
│  │  └──────────┘  └───────────┘  └──────────────────┘       │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

### Key Producer Configurations

| Config | Default | Description | Staff-Level Insight |
|--------|---------|-------------|---------------------|
| `acks` | `all` (3.0+) | 0=fire-and-forget, 1=leader ack, all=ISR ack | `all` with `min.insync.replicas=2` is the gold standard |
| `batch.size` | 16384 | Max bytes per batch | Increase to 65536-131072 for throughput |
| `linger.ms` | 0 | Wait time before sending batch | Set 5-100ms to improve batching |
| `buffer.memory` | 33554432 | Total producer buffer | 64MB-128MB for high throughput |
| `max.in.flight.requests.per.connection` | 5 | Pipelined requests | Set to 1 if ordering matters without idempotency; with idempotency can be ≤5 |
| `compression.type` | `none` | lz4, zstd, snappy, gzip | `lz4` for latency, `zstd` for ratio |
| `retries` | 2147483647 | Retry count | Combined with `delivery.timeout.ms` |
| `delivery.timeout.ms` | 120000 | Upper bound on send time | Includes retries + backoff |
| `enable.idempotence` | `true` (3.0+) | Deduplication on broker | ALWAYS enable in production |
| `transactional.id` | null | For exactly-once | Required for transactional producer |

### Batching Deep Dive

```
Timeline with linger.ms=20, batch.size=16KB:

t=0ms:   Record A arrives → New batch created for TP0
t=5ms:   Record B arrives → Added to same batch
t=10ms:  Record C arrives → Added to same batch (total 12KB)
t=20ms:  linger.ms expires → Batch sent (12KB < 16KB batch.size)

Alternatively:
t=0ms:   Record A arrives (8KB) → New batch
t=2ms:   Record B arrives (9KB) → Batch full (17KB > 16KB)
         → Batch with A sent immediately, B starts new batch
```

### Idempotent Producer

**Problem:** Network failure after broker receives message → producer retries → duplicate.

**Solution:** Producer ID (PID) + Sequence Number per partition.

```
Producer (PID=1000):
  Send to P0: seq=0, seq=1, seq=2, seq=3, ...

Broker tracks per (PID, Partition):
  Expected next seq = current_seq + 1

Scenarios:
  seq=3 received, expected=3 → ACCEPT
  seq=3 received, expected=4 → DUPLICATE (already have it), return success
  seq=5 received, expected=4 → OUT_OF_ORDER → OutOfOrderSequenceException
```

**Broker-side state:** Stored in memory + `__transaction_state` log for durability.
- Tracks last 5 batches per PID per partition
- PID assigned by any broker via `InitProducerIdRequest`
- PID expired after `transactional.id.expiration.ms` (default: 7 days)

### Transactional Producer

Enables atomic writes across multiple partitions and topics.

```java
// Java example - Exactly-once transactional producer
Properties props = new Properties();
props.put("bootstrap.servers", "kafka1:9092,kafka2:9092");
props.put("transactional.id", "order-processor-1");
props.put("enable.idempotence", "true");
props.put("acks", "all");

KafkaProducer<String, String> producer = new KafkaProducer<>(props);
producer.initTransactions();

try {
    producer.beginTransaction();
    
    // Write to multiple topics/partitions atomically
    producer.send(new ProducerRecord<>("orders", orderKey, orderValue));
    producer.send(new ProducerRecord<>("inventory", skuKey, inventoryUpdate));
    producer.send(new ProducerRecord<>("notifications", userId, notification));
    
    // Commit offsets as part of transaction (consume-transform-produce)
    producer.sendOffsetsToTransaction(offsets, consumerGroupMetadata);
    
    producer.commitTransaction();
} catch (ProducerFencedException | OutOfOrderSequenceException e) {
    producer.close(); // Fatal - cannot recover
} catch (KafkaException e) {
    producer.abortTransaction(); // Abort and retry
}
```

**Transaction flow:**

```
┌──────────┐          ┌──────────────────┐          ┌──────────┐
│ Producer │          │ Transaction      │          │ Brokers  │
│          │          │ Coordinator      │          │(Partitions│
│          │          │ (__transaction_  │          │          │
│          │          │   state)         │          │          │
└────┬─────┘          └────────┬─────────┘          └────┬─────┘
     │ 1. InitProducerId       │                         │
     │ (transactional.id) ────▶│                         │
     │◀── PID + Epoch ────────│                         │
     │                         │                         │
     │ 2. BeginTransaction     │                         │
     │ (local only)            │                         │
     │                         │                         │
     │ 3. AddPartitionsToTxn ─▶│                         │
     │                         │ (mark partitions in txn)│
     │                         │                         │
     │ 4. Produce ─────────────┼────────────────────────▶│
     │    (PID, Epoch, Seq)    │                  (write with│
     │                         │                   txn marker)│
     │                         │                         │
     │ 5. AddOffsetsToTxn ────▶│                         │
     │ (consumer group offsets)│                         │
     │                         │ 6. TxnOffsetCommit ────▶│
     │                         │   (__consumer_offsets)   │
     │                         │                         │
     │ 7. EndTxn(COMMIT) ────▶│                         │
     │                         │ 8. WriteTxnMarker ─────▶│
     │                         │   (COMMIT marker to all │
     │                         │    partitions)           │
     │◀── Success ────────────│                         │
```

### Partitioner Strategies

**Default Partitioner (pre-2.4):**
- Key present → `hash(key) % numPartitions` (murmur2)
- Key null → round-robin

**Sticky Partitioner (2.4+, default):**
- Key present → Same as above
- Key null → Pick one partition, stick to it until batch is full or `linger.ms` expires
- Result: Better batching, higher throughput, ~50% latency reduction in benchmarks

```python
# Python - Custom partitioner example
from kafka import KafkaProducer

def geo_partitioner(key, all_partitions, available_partitions):
    """Route by geographic region for data locality"""
    region = key.decode('utf-8').split(':')[0]  # key format: "US:user123"
    region_map = {'US': 0, 'EU': 1, 'APAC': 2}
    partition = region_map.get(region, hash(key) % len(all_partitions))
    return partition

producer = KafkaProducer(
    bootstrap_servers=['kafka1:9092'],
    partitioner=geo_partitioner
)
```

---

## 4. Consumer Internals

### Consumer Group Architecture

```
Topic: orders (6 partitions)

Consumer Group: order-processing

┌──────────┐  ┌──────────┐  ┌──────────┐
│Consumer 0│  │Consumer 1│  │Consumer 2│
│ P0, P1   │  │ P2, P3   │  │ P4, P5   │
└──────────┘  └──────────┘  └──────────┘

If Consumer 2 dies → Rebalance:
┌──────────┐  ┌──────────┐
│Consumer 0│  │Consumer 1│
│ P0, P1,  │  │ P3, P4,  │
│ P2       │  │ P5       │
└──────────┘  └──────────┘
```

### Rebalancing Protocols

#### Eager Rebalancing (Legacy)
1. All consumers revoke ALL partitions
2. All consumers rejoin group
3. Group coordinator assigns partitions
4. **Problem:** Stop-the-world — zero processing during rebalance

#### Cooperative (Incremental) Rebalancing (2.4+)
1. First rebalance: Coordinator identifies which partitions need to move
2. Only affected consumers revoke moved partitions
3. Second rebalance: Revoked partitions assigned to new consumers
4. **Benefit:** Non-affected consumers continue processing

```
# Enable cooperative rebalancing
partition.assignment.strategy=org.apache.kafka.clients.consumer.CooperativeStickyAssignor
```

#### Static Group Membership (2.3+)
```
group.instance.id=consumer-host-1
session.timeout.ms=300000  # 5 minutes
```
- Consumer gets stable identity
- Restarts within `session.timeout.ms` don't trigger rebalance
- Ideal for rolling deployments

### Offset Management

```
__consumer_offsets (internal topic, 50 partitions):

Key: (group_id, topic, partition)
Value: (offset, metadata, timestamp)

Partition assignment: hash(group_id) % 50

Example:
Key: ("order-processors", "orders", 0) → Offset: 45231
Key: ("order-processors", "orders", 1) → Offset: 38912
```

**Commit strategies:**

```java
// Auto-commit (default, at-least-once)
props.put("enable.auto.commit", "true");
props.put("auto.commit.interval.ms", "5000");

// Manual sync commit (at-least-once, blocking)
consumer.commitSync();

// Manual async commit (at-least-once, non-blocking)
consumer.commitAsync((offsets, exception) -> {
    if (exception != null) log.error("Commit failed", exception);
});

// Commit specific offsets
Map<TopicPartition, OffsetAndMetadata> offsets = new HashMap<>();
offsets.put(new TopicPartition("orders", 0), 
            new OffsetAndMetadata(lastProcessedOffset + 1));
consumer.commitSync(offsets);
```

### Consumer Fetch Mechanics

```
Consumer                    Broker (Leader)
   │                            │
   │── FetchRequest ──────────▶│
   │   topic, partition,        │
   │   fetchOffset=100,         │
   │   maxBytes=1048576,        │
   │   minBytes=1,              │
   │   maxWaitMs=500            │
   │                            │
   │   Broker checks:           │
   │   - Is fetchOffset valid?  │
   │   - Is there minBytes of   │
   │     data available?        │
   │   - If not, wait up to     │
   │     maxWaitMs              │
   │                            │
   │◀── FetchResponse ─────────│
   │   records, HW, LEO,        │
   │   abortedTransactions      │
```

**Key fetch configurations:**

| Config | Default | Purpose |
|--------|---------|---------|
| `fetch.min.bytes` | 1 | Min data per fetch (latency vs throughput) |
| `fetch.max.bytes` | 52428800 | Max data per fetch response |
| `fetch.max.wait.ms` | 500 | Max wait if `fetch.min.bytes` not available |
| `max.partition.fetch.bytes` | 1048576 | Max per partition per fetch |
| `max.poll.records` | 500 | Max records per `poll()` call |
| `max.poll.interval.ms` | 300000 | Max time between polls before rebalance |
| `heartbeat.interval.ms` | 3000 | Heartbeat frequency |
| `session.timeout.ms` | 45000 | Consumer failure detection |

### Consumer Threading Model

```
┌────────────────────────────────────────────────┐
│              Consumer Application               │
│                                                 │
│  ┌───────────────────────────────────────┐      │
│  │         User Thread (poll loop)       │      │
│  │                                       │      │
│  │  while(true) {                        │      │
│  │    records = consumer.poll(100ms);     │      │
│  │    process(records);                   │      │
│  │    consumer.commitSync();             │      │
│  │  }                                    │      │
│  └───────────────┬───────────────────────┘      │
│                  │                               │
│  ┌───────────────▼───────────────────────┐      │
│  │      Heartbeat Thread (background)     │      │
│  │  Sends heartbeats every 3s             │      │
│  │  Handles rebalance notifications       │      │
│  └───────────────────────────────────────┘      │
│                                                 │
│  ┌───────────────────────────────────────┐      │
│  │      Network Thread (background)       │      │
│  │  Handles TCP connections, I/O          │      │
│  └───────────────────────────────────────┘      │
└────────────────────────────────────────────────┘
```

**Critical:** If `process(records)` takes longer than `max.poll.interval.ms`, the consumer is considered dead → rebalance triggered.

---

## 5. Kafka Streams

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Kafka Streams Application                │
│                   (JVM Process)                           │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │              StreamThread-0                        │    │
│  │  ┌─────────────┐  ┌─────────────┐                │    │
│  │  │  StreamTask  │  │  StreamTask  │                │    │
│  │  │  (P0)        │  │  (P1)        │                │    │
│  │  │ ┌─────────┐  │  │ ┌─────────┐  │                │    │
│  │  │ │Processor│  │  │ │Processor│  │                │    │
│  │  │ │Topology │  │  │ │Topology │  │                │    │
│  │  │ └─────────┘  │  │ └─────────┘  │                │    │
│  │  │ ┌─────────┐  │  │ ┌─────────┐  │                │    │
│  │  │ │State    │  │  │ │State    │  │                │    │
│  │  │ │Store    │  │  │ │Store    │  │                │    │
│  │  │ │(RocksDB)│  │  │ │(RocksDB)│  │                │    │
│  │  │ └─────────┘  │  │ └─────────┘  │                │    │
│  │  └─────────────┘  └─────────────┘                │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │              StreamThread-1                        │    │
│  │  ┌─────────────┐  ┌─────────────┐                │    │
│  │  │  StreamTask  │  │  StreamTask  │                │    │
│  │  │  (P2)        │  │  (P3)        │                │    │
│  │  └─────────────┘  └─────────────┘                │    │
│  └──────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### KStream vs KTable vs GlobalKTable

```java
// KStream - unbounded stream of events (INSERT semantics)
KStream<String, Order> orders = builder.stream("orders");

// KTable - changelog stream (UPSERT semantics, latest value per key)
KTable<String, CustomerProfile> customers = builder.table("customers");

// GlobalKTable - full copy on every instance (for small lookup tables)
GlobalKTable<String, Country> countries = builder.globalTable("countries");
```

**Differences:**

| Feature | KStream | KTable | GlobalKTable |
|---------|---------|--------|-------------|
| Semantics | INSERT | UPSERT | UPSERT |
| Partitioned | Yes | Yes | No (full copy) |
| Backed by | Changelog topic | Changelog topic | Changelog topic |
| Join with KStream | Yes (windowed) | Yes (non-windowed) | Yes (non-windowed) |
| Size constraint | Unbounded | Bounded by key space | Must fit in memory |

### State Stores and RocksDB

```java
// Custom state store usage in Processor API
public class DeduplicationProcessor implements Processor<String, Event, String, Event> {
    private KeyValueStore<String, Long> seenEvents;
    
    @Override
    public void init(ProcessorContext<String, Event> context) {
        seenEvents = context.getStateStore("seen-events");
    }
    
    @Override
    public void process(Record<String, Event> record) {
        String eventId = record.value().getId();
        if (seenEvents.get(eventId) == null) {
            seenEvents.put(eventId, record.timestamp());
            context().forward(record);
        }
    }
}
```

**RocksDB tuning for Kafka Streams:**

```java
// Custom RocksDB config
props.put(StreamsConfig.ROCKSDB_CONFIG_SETTER_CLASS_CONFIG, 
          CustomRocksDBConfig.class);

public class CustomRocksDBConfig implements RocksDBConfigSetter {
    @Override
    public void setConfig(String storeName, Options options, 
                          Map<String, Object> configs) {
        BlockBasedTableConfig tableConfig = new BlockBasedTableConfig();
        tableConfig.setBlockCacheSize(256 * 1024 * 1024L);  // 256MB
        tableConfig.setBlockSize(16 * 1024);                  // 16KB
        tableConfig.setCacheIndexAndFilterBlocks(true);
        
        options.setTableFormatConfig(tableConfig);
        options.setMaxWriteBufferNumber(4);
        options.setWriteBufferSize(64 * 1024 * 1024);  // 64MB
        options.setMaxBytesForLevelBase(256 * 1024 * 1024);
        options.setCompactionStyle(CompactionStyle.LEVEL);
    }
}
```

### Interactive Queries

```java
// Query state store from another service via REST
ReadOnlyKeyValueStore<String, Long> store = 
    streams.store(
        StoreQueryParameters.fromNameAndType(
            "word-count-store", 
            QueryableStoreTypes.keyValueStore()
        )
    );

// Point lookup
Long count = store.get("hello");

// Range scan
KeyValueIterator<String, Long> range = store.range("a", "z");

// For distributed queries, use StreamsMetadata
Collection<StreamsMetadata> metadata = streams.metadataForAllStateStores();
// Route query to correct instance based on key
StreamsMetadata meta = streams.queryMetadataForKey(
    "word-count-store", "hello", Serdes.String().serializer()
);
```

---

## 6. Kafka Connect

### Architecture

```
┌──────────────────────────────────────────────────────┐
│                 Kafka Connect Cluster                  │
│                                                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐     │
│  │  Worker 0   │  │  Worker 1   │  │  Worker 2   │     │
│  │            │  │            │  │            │     │
│  │ ┌────────┐ │  │ ┌────────┐ │  │ ┌────────┐ │     │
│  │ │Task 0-0│ │  │ │Task 0-1│ │  │ │Task 1-0│ │     │
│  │ │(MySQL  │ │  │ │(MySQL  │ │  │ │(S3     │ │     │
│  │ │ Source) │ │  │ │ Source) │ │  │ │ Sink)  │ │     │
│  │ └────────┘ │  │ └────────┘ │  │ └────────┘ │     │
│  │ ┌────────┐ │  │ ┌────────┐ │  │ ┌────────┐ │     │
│  │ │Task 1-1│ │  │ │Task 2-0│ │  │ │Task 2-1│ │     │
│  │ │(S3     │ │  │ │(ES     │ │  │ │(ES     │ │     │
│  │ │ Sink)  │ │  │ │ Sink)  │ │  │ │ Sink)  │ │     │
│  │ └────────┘ │  │ └────────┘ │  │ └────────┘ │     │
│  └────────────┘  └────────────┘  └────────────┘     │
│                                                       │
│  Internal Topics:                                     │
│  - connect-configs (connector configurations)         │
│  - connect-offsets (source connector offsets)          │
│  - connect-status  (connector/task status)            │
└──────────────────────────────────────────────────────┘
```

### Connectors, Tasks, and Workers

```json
// Debezium MySQL Source Connector
{
  "name": "mysql-cdc-orders",
  "config": {
    "connector.class": "io.debezium.connector.mysql.MySqlConnector",
    "database.hostname": "mysql-primary",
    "database.port": "3306",
    "database.user": "debezium",
    "database.password": "${vault:mysql/password}",
    "database.server.id": "184054",
    "topic.prefix": "cdc",
    "database.include.list": "ecommerce",
    "table.include.list": "ecommerce.orders,ecommerce.order_items",
    "schema.history.internal.kafka.bootstrap.servers": "kafka:9092",
    "schema.history.internal.kafka.topic": "schema-changes.ecommerce",
    "transforms": "route,unwrap",
    "transforms.route.type": "org.apache.kafka.connect.transforms.RegexRouter",
    "transforms.route.regex": "cdc\\.ecommerce\\.(.*)",
    "transforms.route.replacement": "ecommerce.$1",
    "transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState",
    "transforms.unwrap.drop.tombstones": "false",
    "errors.tolerance": "all",
    "errors.deadletterqueue.topic.name": "dlq-mysql-cdc",
    "errors.deadletterqueue.context.headers.enable": "true",
    "tasks.max": "1",
    "snapshot.mode": "initial"
  }
}
```

### Single Message Transforms (SMTs)

```json
// Common SMTs
{
  "transforms": "insertTimestamp,maskField,cast,flatten",
  
  "transforms.insertTimestamp.type": "org.apache.kafka.connect.transforms.InsertField$Value",
  "transforms.insertTimestamp.timestamp.field": "kafka_timestamp",
  
  "transforms.maskField.type": "org.apache.kafka.connect.transforms.MaskField$Value",
  "transforms.maskField.fields": "ssn,credit_card",
  
  "transforms.cast.type": "org.apache.kafka.connect.transforms.Cast$Value",
  "transforms.cast.spec": "price:float64,quantity:int32",
  
  "transforms.flatten.type": "org.apache.kafka.connect.transforms.Flatten$Value",
  "transforms.flatten.delimiter": "_"
}
```

### Dead Letter Queue (DLQ)

```json
{
  "errors.tolerance": "all",
  "errors.deadletterqueue.topic.name": "dlq-connector-name",
  "errors.deadletterqueue.topic.replication.factor": 3,
  "errors.deadletterqueue.context.headers.enable": true,
  "errors.log.enable": true,
  "errors.log.include.messages": true
}
```

DLQ headers contain:
- `__connect.errors.topic` - Original topic
- `__connect.errors.partition` - Original partition
- `__connect.errors.offset` - Original offset
- `__connect.errors.exception.class` - Error class
- `__connect.errors.exception.message` - Error message

### Exactly-Once in Connect (3.3+)

```properties
# Worker config
exactly.once.source.support=enabled
# Connector config
transaction.boundary=poll  # or 'connector' or 'interval'
```

---

## 7. Performance Tuning

### Zero-Copy Transfer

```
Traditional Copy (4 copies, 2 syscalls with user-space):
Disk → Kernel Buffer → User Buffer → Socket Buffer → NIC

Kafka Zero-Copy (2 copies, 1 syscall via sendfile()):
Disk → Kernel Buffer (Page Cache) → NIC (via DMA)

Result: ~60% reduction in CPU usage for consumer fetch operations
```

**Implementation:** Java `FileChannel.transferTo()` → Linux `sendfile()` syscall

### Page Cache Optimization

Kafka heavily relies on OS page cache instead of JVM heap:

```bash
# Recommended OS tuning
# Increase dirty page ratio (delay writes)
vm.dirty_ratio = 80
vm.dirty_background_ratio = 5

# Swap avoidance
vm.swappiness = 1

# File descriptor limits
fs.file-max = 1000000
ulimit -n 1000000

# Network tuning
net.core.wmem_max = 2097152
net.core.rmem_max = 2097152
net.ipv4.tcp_wmem = 4096 65536 2048000
net.ipv4.tcp_rmem = 4096 65536 2048000
net.core.netdev_max_backlog = 50000
```

### Compression Comparison

| Algorithm | Compression Ratio | Compression Speed | Decompression Speed | CPU Usage |
|-----------|------------------|-------------------|--------------------|-----------| 
| none | 1.0x | N/A | N/A | None |
| snappy | ~1.7x | Very Fast | Very Fast | Low |
| lz4 | ~2.1x | Very Fast | Very Fast | Low |
| zstd | ~2.8x | Fast | Very Fast | Medium |
| gzip | ~2.5x | Slow | Fast | High |

**Recommendation:**
- **Latency-sensitive:** `lz4`
- **Storage-sensitive:** `zstd`
- **Legacy compatibility:** `snappy`
- **Never in production:** `gzip` (too CPU-intensive for high throughput)

### JVM Tuning

```bash
# Recommended JVM settings for Kafka broker
KAFKA_HEAP_OPTS="-Xms6g -Xmx6g"

# G1GC (recommended for Kafka)
KAFKA_JVM_PERFORMANCE_OPTS="
  -XX:+UseG1GC
  -XX:MaxGCPauseMillis=20
  -XX:InitiatingHeapOccupancyPercent=35
  -XX:G1HeapRegionSize=16M
  -XX:MinMetaspaceFreeRatio=50
  -XX:MaxMetaspaceFreeRatio=80
  -XX:+ExplicitGCInvokesConcurrent
  -Djava.awt.headless=true
"

# DON'T give Kafka too much heap - leave memory for page cache
# Rule: 6GB heap for broker, rest for page cache
# On 64GB machine: 6GB heap + 58GB page cache
```

### Partition Count Strategy

**Formula for partition count:**
```
Partitions = max(Tp/Pp, Tc/Pc)

Where:
  Tp = Target throughput (MB/s)
  Pp = Producer throughput per partition (MB/s)
  Tc = Target consumer throughput (MB/s)  
  Pc = Consumer throughput per partition (MB/s)

Example:
  Target: 1 GB/s throughput
  Producer: 50 MB/s per partition
  Consumer: 50 MB/s per partition
  
  Partitions = max(1000/50, 1000/50) = 20 partitions minimum
```

**Guidelines:**
- Start with `partitions = 2 × broker_count` for typical workloads
- Never exceed ~4000 partitions per broker (affects leader election time)
- Total cluster limit: ~200,000 partitions (KRaft handles more)
- More partitions = more open file handles, more memory, longer recovery

---

## 8. Schema Registry

### Architecture

```
┌────────────────────────────────────────────────────────────┐
│                   Schema Registry Cluster                    │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Primary    │  │   Secondary  │  │   Secondary  │      │
│  │  (Leader)    │  │  (Follower)  │  │  (Follower)  │      │
│  └──────┬───────┘  └──────────────┘  └──────────────┘      │
│         │                                                    │
│  ┌──────▼───────────────────────────────────────────────┐   │
│  │           _schemas (internal topic)                    │   │
│  │  Key: (subject, version)                              │   │
│  │  Value: {schema, schemaType, references}              │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

### Compatibility Modes

```
Schema V1: {id: int, name: string, email: string}
Schema V2: {id: int, name: string, email: string, phone: string (optional)}
Schema V3: {id: int, name: string, phone: string (optional)}

BACKWARD (default):
  New schema can READ old data
  V2 can read V1 data ✓ (phone defaults to null)
  Adding optional fields ✓, removing fields ✓
  → Safe for CONSUMERS to upgrade first

FORWARD:
  Old schema can READ new data
  V1 can read V2 data ✓ (ignores phone)
  Adding fields ✓, removing optional fields ✓
  → Safe for PRODUCERS to upgrade first

FULL:
  Both backward AND forward compatible
  Only adding/removing optional fields
  → Safest, recommended for critical topics

NONE:
  No compatibility check
  → DANGER: Use only for development

TRANSITIVE variants (BACKWARD_TRANSITIVE, FORWARD_TRANSITIVE, FULL_TRANSITIVE):
  Check against ALL previous versions, not just the latest
```

### Schema Types

```java
// Avro (most common for Kafka)
{
  "type": "record",
  "name": "Order",
  "namespace": "com.example",
  "fields": [
    {"name": "order_id", "type": "string"},
    {"name": "amount", "type": "double"},
    {"name": "currency", "type": {"type": "enum", "name": "Currency", 
     "symbols": ["USD", "EUR", "GBP"]}},
    {"name": "metadata", "type": ["null", {"type": "map", 
     "values": "string"}], "default": null}
  ]
}

// Protobuf
syntax = "proto3";
message Order {
  string order_id = 1;
  double amount = 2;
  Currency currency = 3;
  map<string, string> metadata = 4;
  
  enum Currency {
    USD = 0;
    EUR = 1;
    GBP = 2;
  }
}

// JSON Schema
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "order_id": {"type": "string"},
    "amount": {"type": "number"},
    "currency": {"type": "string", "enum": ["USD", "EUR", "GBP"]}
  },
  "required": ["order_id", "amount"]
}
```

---

## 9. Security

### Authentication (SASL)

```properties
# Broker config - SASL/SCRAM
listeners=SASL_SSL://0.0.0.0:9093
security.inter.broker.protocol=SASL_SSL
sasl.mechanism.inter.broker.protocol=SCRAM-SHA-512
sasl.enabled.mechanisms=SCRAM-SHA-512

# JAAS config for SCRAM
listener.name.sasl_ssl.scram-sha-512.sasl.jaas.config=\
  org.apache.kafka.common.security.scram.ScramLoginModule required \
  username="admin" \
  password="admin-secret";
```

```bash
# Create SCRAM credentials
kafka-configs.sh --bootstrap-server kafka:9092 \
  --alter --add-config \
  'SCRAM-SHA-512=[password=alice-secret]' \
  --entity-type users --entity-name alice
```

### Authorization (ACLs)

```bash
# Allow producer to write to topic
kafka-acls.sh --bootstrap-server kafka:9092 \
  --add --allow-principal User:producer-app \
  --operation Write --topic orders

# Allow consumer group to read
kafka-acls.sh --bootstrap-server kafka:9092 \
  --add --allow-principal User:consumer-app \
  --operation Read --topic orders \
  --group order-processors

# List ACLs
kafka-acls.sh --bootstrap-server kafka:9092 --list

# Deny specific user
kafka-acls.sh --bootstrap-server kafka:9092 \
  --add --deny-principal User:malicious-user \
  --operation All --topic '*'
```

### Encryption

```properties
# SSL/TLS encryption
ssl.keystore.location=/var/kafka/ssl/kafka.broker.keystore.jks
ssl.keystore.password=${KEYSTORE_PASSWORD}
ssl.key.password=${KEY_PASSWORD}
ssl.truststore.location=/var/kafka/ssl/kafka.broker.truststore.jks
ssl.truststore.password=${TRUSTSTORE_PASSWORD}
ssl.client.auth=required  # mTLS
ssl.enabled.protocols=TLSv1.3,TLSv1.2
ssl.protocol=TLSv1.3
```

---

## 10. KRaft Mode

### Architecture (No ZooKeeper)

```
┌─────────────────────────────────────────────────────────────────┐
│                       KRaft Cluster                              │
│                                                                  │
│  Controller Quorum (Raft-based):                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Controller 0 │  │ Controller 1 │  │ Controller 2 │          │
│  │ (ACTIVE)     │  │ (FOLLOWER)   │  │ (FOLLOWER)   │          │
│  │              │  │              │  │              │          │
│  │ Metadata Log │  │ Metadata Log │  │ Metadata Log │          │
│  │ (replicated) │  │ (replicated) │  │ (replicated) │          │
│  └──────┬───────┘  └──────────────┘  └──────────────┘          │
│         │                                                        │
│         │ Metadata Updates (push-based)                          │
│         ▼                                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Broker 0   │  │   Broker 1   │  │   Broker 2   │          │
│  │              │  │              │  │              │          │
│  │ MetadataCache│  │ MetadataCache│  │ MetadataCache│          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### KRaft vs ZooKeeper Comparison

| Aspect | ZooKeeper Mode | KRaft Mode |
|--------|---------------|------------|
| Metadata storage | ZooKeeper znodes | Internal Raft log |
| Controller election | Via ZK ephemeral node | Via Raft protocol |
| Partition limit | ~200K | Millions |
| Controlled shutdown | Slower | Faster |
| Recovery time | Minutes | Seconds |
| Operational complexity | High (manage ZK + Kafka) | Lower (Kafka only) |
| Metadata propagation | Pull (brokers poll ZK) | Push (controller pushes) |

### Migration from ZooKeeper to KRaft

```bash
# Step 1: Generate cluster ID
kafka-storage.sh random-uuid
# Output: dPqzJUm9RDGMj_2HOPstXQ

# Step 2: Format controller storage
kafka-storage.sh format -t dPqzJUm9RDGMj_2HOPstXQ \
  -c /etc/kafka/kraft/controller.properties

# Step 3: Start controllers in KRaft mode
# Step 4: Migrate brokers one at a time
# Step 5: Remove ZooKeeper dependency
```

---

## 11. Exactly-Once Semantics (EOS)

### Three Pillars of EOS

```
┌────────────────────────────────────────────────────────────┐
│              EXACTLY-ONCE SEMANTICS                         │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Idempotent  │  │ Transactional│  │  Consumer    │     │
│  │  Producer    │  │  Producer    │  │  read_       │     │
│  │              │  │              │  │  committed   │     │
│  │  PID + SeqNo │  │  Atomic      │  │              │     │
│  │  per partition│  │  multi-      │  │  Only reads  │     │
│  │              │  │  partition   │  │  committed   │     │
│  │  Dedup at    │  │  writes     │  │  transactions│     │
│  │  broker      │  │              │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                             │
│  Combined: End-to-end exactly-once in                       │
│  consume-transform-produce patterns                         │
└────────────────────────────────────────────────────────────┘
```

### EOS in Practice (Consume-Transform-Produce)

```java
Properties props = new Properties();
props.put("bootstrap.servers", "kafka:9092");
props.put("transactional.id", "word-count-processor-1");
props.put("isolation.level", "read_committed");
props.put("enable.auto.commit", "false");

KafkaConsumer<String, String> consumer = new KafkaConsumer<>(props);
KafkaProducer<String, String> producer = new KafkaProducer<>(props);

producer.initTransactions();
consumer.subscribe(List.of("input-topic"));

while (true) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
    if (records.isEmpty()) continue;
    
    producer.beginTransaction();
    try {
        for (ConsumerRecord<String, String> record : records) {
            // Transform
            String result = transform(record.value());
            // Produce
            producer.send(new ProducerRecord<>("output-topic", record.key(), result));
        }
        
        // Commit consumer offsets within the transaction
        Map<TopicPartition, OffsetAndMetadata> offsets = getOffsetsToCommit(records);
        producer.sendOffsetsToTransaction(offsets, consumer.groupMetadata());
        
        producer.commitTransaction();
    } catch (Exception e) {
        producer.abortTransaction();
        // Reset consumer to last committed offset
        consumer.seekToCommitted();
    }
}
```

---

## 12. Multi-DC Deployment

### MirrorMaker 2 Architecture

```
┌─────────────────┐         ┌─────────────────┐
│  DC-EAST Cluster │         │  DC-WEST Cluster │
│                  │         │                  │
│  orders          │◀──MM2──▶│  east.orders     │
│  payments        │         │  east.payments   │
│  users           │         │  east.users      │
│                  │         │                  │
│  west.orders     │         │  orders          │
│  west.payments   │         │  payments        │
│  west.users      │         │  users           │
└─────────────────┘         └─────────────────┘
        ▲                           ▲
        │       MirrorMaker 2       │
        │   ┌────────────────┐      │
        └───│ Source→Target  │──────┘
            │ Heartbeats     │
            │ Checkpoints    │
            │ Offset Sync    │
            └────────────────┘
```

### MM2 Configuration

```json
{
  "name": "mm2-east-to-west",
  "config": {
    "connector.class": "org.apache.kafka.connect.mirror.MirrorSourceConnector",
    "source.cluster.alias": "east",
    "target.cluster.alias": "west",
    "source.cluster.bootstrap.servers": "east-kafka:9092",
    "target.cluster.bootstrap.servers": "west-kafka:9092",
    "topics": "orders,payments,users",
    "groups": ".*",
    "replication.factor": 3,
    "sync.topic.configs.enabled": true,
    "sync.topic.acls.enabled": true,
    "emit.heartbeats.interval.seconds": 5,
    "emit.checkpoints.interval.seconds": 10,
    "refresh.topics.interval.seconds": 30,
    "offset-syncs.topic.replication.factor": 3,
    "heartbeats.topic.replication.factor": 3,
    "checkpoints.topic.replication.factor": 3
  }
}
```

### Active-Active Patterns

```
Pattern 1: Aggregate Topics (recommended)
Each DC writes to local topics, MM2 replicates with prefix.
Consumers read from both local + remote prefixed topics.

Pattern 2: Conflict-Free Replicated Data Types (CRDT)
Use last-writer-wins or vector clocks for conflict resolution.

Pattern 3: Geo-Partitioning
Route messages to specific partitions based on geography.
Each DC only processes its own partitions.
```

---

## 13. Capacity Planning

### Throughput Calculations

```
Given:
  - 100,000 events/second
  - Average event size: 1 KB
  - Replication factor: 3
  - Retention: 7 days
  - Compression ratio: 2x (zstd)

Calculations:
  Ingress: 100,000 × 1KB = 100 MB/s
  With replication: 100 MB/s × 3 = 300 MB/s (inter-broker)
  With compression: 100 MB/s / 2 = 50 MB/s (on disk per replica)
  
  Daily storage: 50 MB/s × 86,400s × 3 replicas = 12.96 TB/day
  7-day retention: 12.96 × 7 = 90.7 TB total storage
  
Broker sizing:
  Throughput per broker: ~150 MB/s sustained (on good hardware)
  Brokers needed: 300 MB/s / 150 MB/s = 2 brokers (minimum)
  For resilience: 2 × 1.5 = 3 brokers (can lose 1)
  
  Storage per broker: 90.7 TB / 3 = 30.2 TB per broker
  
  Network: 10 Gbps per broker minimum
           (300 MB/s = 2.4 Gbps ingress + egress)
```

### Broker Hardware Recommendations

| Component | Development | Production | High-Throughput |
|-----------|-------------|------------|-----------------|
| CPU | 4 cores | 16 cores | 32+ cores |
| RAM | 8 GB | 64 GB | 128+ GB |
| Disk | SSD 500GB | NVMe 4×2TB RAID10 | NVMe 8×4TB JBOD |
| Network | 1 Gbps | 10 Gbps | 25 Gbps |
| JVM Heap | 1 GB | 6 GB | 6 GB |
| Page Cache | 7 GB | 58 GB | 122 GB |

---

## 14. Common Anti-Patterns

### 1. Too Many Partitions

**Problem:** 50,000 partitions on a 3-broker cluster
- Leader election takes minutes during broker failure
- Memory pressure from segment indexes
- File descriptor exhaustion

**Solution:**
- Target: ≤4000 partitions per broker
- Use fewer partitions with higher consumer parallelism
- Consider KRaft mode (handles more partitions)

### 2. Large Messages

**Problem:** Sending 10MB messages (video frames, large documents)
- Increased memory pressure on brokers and clients
- Timeout failures during replication
- Breaks batch size assumptions

**Solution:**
- Use Claim Check pattern: Store payload in S3, send reference in Kafka
- If unavoidable: increase `message.max.bytes`, `replica.fetch.max.bytes`, `max.request.size`
- Use compression and chunking

### 3. Consumer Lag Causes

```
Symptom: Consumer lag growing continuously

Root Causes:
1. Processing too slow → Optimize processing or scale consumers
2. Too many partitions per consumer → Add more consumers
3. Frequent rebalances → Use static membership + cooperative sticky
4. GC pauses → Tune JVM, reduce heap, use G1GC
5. Slow external calls → Use async processing, batch operations
6. max.poll.records too high → Reduce and tune processing time
```

### 4. Rebalance Storms

**Problem:** Consumers constantly rebalancing, never making progress

```
Causes:
- max.poll.interval.ms too short for processing time
- session.timeout.ms too aggressive
- Consumer GC pauses exceeding session timeout
- Network instability

Solutions:
1. Increase max.poll.interval.ms to match worst-case processing
2. Use cooperative sticky assignor
3. Enable static group membership
4. Reduce max.poll.records
5. Move heavy processing to separate thread pool
```

### 5. Not Using Idempotent Producer

**Problem:** Duplicate messages after producer retries

```
# ALWAYS enable in production
enable.idempotence=true   # Default since Kafka 3.0
acks=all
max.in.flight.requests.per.connection=5  # Safe with idempotence
```

### 6. Offset Reset Disasters

**Problem:** Consumer group offsets expired (after `offsets.retention.minutes`, default 7 days), causing full reprocessing.

```
# Prevention
offsets.retention.minutes=10080      # 7 days (broker)
auto.offset.reset=latest             # For new consumers, don't reprocess
                                     # Use 'earliest' only if you need full history

# Emergency recovery
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --group my-group --reset-offsets --to-datetime 2024-01-15T00:00:00.000 \
  --topic my-topic --execute
```

### 7. Not Monitoring Key Metrics

```
Essential Kafka Metrics Dashboard:

Broker Health:
  - UnderReplicatedPartitions (should be 0)
  - ActiveControllerCount (exactly 1 in cluster)
  - OfflinePartitionsCount (should be 0)
  - RequestHandlerAvgIdlePercent (should be > 0.3)

Producer:
  - record-send-rate
  - record-error-rate
  - batch-size-avg
  - request-latency-avg

Consumer:
  - records-consumed-rate
  - records-lag-max
  - commit-latency-avg
  - rebalance-rate-and-time

Cluster:
  - BytesInPerSec / BytesOutPerSec per broker
  - MessagesInPerSec
  - PartitionCount
  - IsrShrinksPerSec / IsrExpandsPerSec
```

---

## Quick Reference: Production Checklist

```
[ ] Replication factor ≥ 3
[ ] min.insync.replicas = 2
[ ] acks = all
[ ] enable.idempotence = true
[ ] unclean.leader.election.enable = false
[ ] auto.create.topics.enable = false
[ ] compression.type = lz4 or zstd
[ ] Monitoring: URP, ISR, lag, throughput
[ ] Security: SASL + TLS + ACLs
[ ] Schema Registry with FULL_TRANSITIVE compatibility
[ ] Consumer: cooperative sticky assignor + static membership
[ ] JVM: G1GC, 6GB heap, rest for page cache
[ ] OS: vm.swappiness=1, file descriptors, network tuning
[ ] Partition count: 2× broker count minimum, ≤4000/broker
[ ] Retention: sized based on capacity planning
[ ] DLQ configured for Connect and consumer error handling
[ ] Backup: MirrorMaker 2 for DR
```
