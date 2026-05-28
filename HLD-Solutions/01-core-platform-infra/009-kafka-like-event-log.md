# Design a Kafka-like Event Log / Distributed Streaming Platform

## 1. Functional Requirements

- **Topic Management**: Create, delete, and configure topics with configurable partitions and replication factor
- **Ordered Append**: Producers append records to topic partitions with guaranteed ordering within a partition
- **Consumer Groups**: Multiple consumers in a group each consume a subset of partitions (parallel processing)
- **Offset Management**: Track consumer position (offset) per partition; support commit, seek, and replay
- **Retention Policies**: Time-based (e.g., 7 days) and size-based (e.g., 100 GB per partition) retention
- **Log Compaction**: Keep only the latest value per key (for changelog/snapshot topics)
- **Exactly-Once Semantics (EOS)**: Transactional produce + consume with idempotent producers
- **Replication**: Each partition replicated across N brokers with leader-based writes and follower reads
- **Schema Registry**: Enforce and evolve schemas (Avro, Protobuf, JSON Schema) with compatibility checks
- **Consumer Rebalancing**: Automatic partition reassignment when consumers join/leave
- **Batch Produce/Consume**: Efficiently batch multiple records in a single network request
- **Compression**: Producer-side compression (gzip, snappy, lz4, zstd) for bandwidth reduction
- **Quotas**: Per-client produce/consume rate limits to prevent noisy neighbors
- **ACLs**: Topic-level and consumer-group-level access control
- **Multi-Tenancy**: Logical isolation between teams/services sharing a cluster
- **Connect API**: Source and sink connectors for database CDC, S3, Elasticsearch, etc.
- **Stream Processing**: Built-in stream processing (windowing, joins, aggregations)
- **Tiered Storage**: Move older segments to object storage (S3) while serving from local disk
- **Mirror/Replication**: Cross-datacenter replication for disaster recovery

## 2. Non-Functional Requirements

| NFR | Target |
|-----|--------|
| **Availability** | 99.99% with multi-AZ replication |
| **Throughput** | 2 GB/sec per broker (produce); 5 GB/sec per broker (consume via zero-copy) |
| **Latency** | p99 < 10ms for produce (acks=1); p99 < 5ms for consume |
| **Durability** | Zero data loss for acked records (min.insync.replicas=2, acks=all) |
| **Ordering** | Strict ordering within partition; no ordering across partitions |
| **Scalability** | 1000+ brokers, 1M+ partitions, 1M+ producers, 100K+ consumer groups |
| **Retention** | 1 hour to forever (with tiered storage to S3) |
| **Message Size** | Up to 10 MB per record (configurable) |
| **Exactly-Once** | Idempotent producers + transactional semantics |
| **Replication Lag** | < 100ms under normal conditions |
| **Recovery** | Leader failover < 5 seconds; no data loss for ISR replicas |

## 3. Capacity Estimation

### Assumptions
| Dimension | Value |
|-----------|-------|
| Cluster size | 100 brokers |
| Total topics | 50,000 |
| Total partitions | 500,000 |
| Average message size | 1 KB |
| Peak produce rate | 50M messages/sec cluster-wide |
| Peak consume rate | 200M messages/sec (4 consumer groups avg) |
| Replication factor | 3 |
| Retention | 7 days average |
| Compression ratio | 4:1 (with zstd) |

### QPS/RPS
```
Produce: 50M msg/sec = 50 GB/sec raw (before compression)
  With compression (4:1): 12.5 GB/sec actual disk writes
  With replication (3x): 37.5 GB/sec total disk I/O for writes
  Per broker: 37.5 / 100 = 375 MB/sec write I/O per broker

Consume: 200M msg/sec = 200 GB/sec raw reads
  Zero-copy (sendfile): OS page cache → NIC, no CPU copy
  Per broker: 200 / 100 = 2 GB/sec read I/O per broker
  Often from page cache (no disk I/O if consumer is near real-time)

Metadata requests: ~1M req/sec (topic/partition discovery, offset commits)
  Per broker: 10K req/sec metadata overhead
```

### Storage Estimation
```
Daily ingest (after compression): 12.5 GB/sec × 86,400 = 1.08 PB/day
  Per broker: 10.8 TB/day
7-day retention: 1.08 PB × 7 = 7.56 PB total hot storage
  Per broker: 75.6 TB (achievable with multiple NVMe SSDs)
  
With tiered storage (S3 for data > 24h):
  Hot storage (local): 1.08 PB × 1 day = 1.08 PB
  Cold storage (S3): 1.08 PB × 6 days = 6.48 PB in S3
  Per broker local: ~10.8 TB (much more manageable)

Index overhead: ~2% of data = 150 TB total
Replication: already counted in write I/O (3 copies)
```

### Network Bandwidth
```
Produce ingest: 12.5 GB/sec = 100 Gbps
Replication traffic: 12.5 GB/sec × 2 = 25 GB/sec = 200 Gbps
Consume egress: up to 200 GB/sec = 1.6 Tbps (mostly from page cache)
Per broker: 100 Gbps produce + 200 Gbps replication + 1600 Gbps consume / 100 = 19 Gbps per broker
  → Need 25 GbE or 2×10 GbE per broker minimum
```

### Infrastructure
```
Brokers: 100 nodes
  - CPU: 16 cores (mostly I/O bound, not CPU bound)
  - RAM: 128 GB (64 GB for page cache, 64 GB for JVM/heap)
  - Disk: 8× 4 TB NVMe SSD = 32 TB per broker (JBOD, not RAID)
  - Network: 25 GbE
  
ZooKeeper / KRaft: 5 nodes (Raft consensus for metadata)
  - CPU: 8 cores
  - RAM: 32 GB
  - Disk: 512 GB SSD (metadata only)
  
Schema Registry: 3 nodes (HA)
Connect cluster: 20 nodes (varies by connector load)
Monitoring: 5 nodes (Prometheus, Grafana, Cruise Control)
```

## 4. Data Modeling

### Core Data Structures

#### Partition Log (Append-Only Segments)
```
Directory structure:
  /data/topic-name-partition-N/
    ├── 00000000000000000000.log       # First segment (offset 0)
    ├── 00000000000000000000.index     # Sparse offset → position index
    ├── 00000000000000000000.timeindex # Sparse timestamp → offset index
    ├── 00000000000065536000.log       # Next segment (starts at offset 65536000)
    ├── 00000000000065536000.index
    ├── 00000000000065536000.timeindex
    ├── leader-epoch-checkpoint        # Leader epoch history
    └── partition.metadata             # Partition metadata

Segment naming: zero-padded base offset of first record in segment
Segment roll: on size (1 GB default) or time (7 days) or index full
```

#### Record Batch Format (on disk and wire)
```
RecordBatch (container for multiple records):
┌─────────────────────────────────────────────────┐
│ baseOffset: int64                                │  -- First offset in batch
│ batchLength: int32                               │  -- Total bytes
│ partitionLeaderEpoch: int32                      │  -- Leader epoch for fencing
│ magic: int8 (=2)                                 │  -- Format version
│ crc: uint32                                      │  -- CRC of remaining fields
│ attributes: int16                                │  -- Compression, timestamp type, transactional, control
│ lastOffsetDelta: int32                           │  -- Offset of last record relative to baseOffset
│ baseTimestamp: int64                             │  -- Timestamp of first record
│ maxTimestamp: int64                              │  -- Max timestamp in batch
│ producerId: int64                                │  -- For idempotent/transactional produce
│ producerEpoch: int16                             │  -- Producer epoch for fencing
│ baseSequence: int32                              │  -- Sequence number for idempotency
│ records: [Record]                                │  -- Array of records (varint encoded)
└─────────────────────────────────────────────────┘

Record (individual message):
┌─────────────────────────────────────────────────┐
│ length: varint                                   │
│ attributes: int8                                 │
│ timestampDelta: varlong (relative to batch base) │
│ offsetDelta: varint (relative to batch base)     │
│ keyLength: varint                                │
│ key: bytes                                       │
│ valueLength: varint                              │
│ value: bytes                                     │
│ headersCount: varint                             │
│ headers: [Header]  (key-value pairs)            │
└─────────────────────────────────────────────────┘
```

#### Offset Index (Sparse)
```
Index entry (8 bytes each):
┌────────────────────┐
│ relativeOffset: u32│  -- Offset relative to segment base
│ position: u32      │  -- Byte position in .log file
└────────────────────┘

Properties:
  - Sparse: one entry per ~4 KB of messages (not every message)
  - Binary search: O(log n) to find position for any offset
  - Memory-mapped: OS caches in RAM for fast lookups
  - Size: ~1 MB per GB of log data

Lookup flow:
  1. Find segment file containing target offset (binary search on filenames)
  2. Binary search .index file for largest entry ≤ target offset
  3. Scan .log file from that position forward to exact offset
```

#### Consumer Group Offsets
```
Topic: __consumer_offsets (internal, compacted)
  Key: (group_id, topic, partition)
  Value: {
    offset: int64,
    metadata: string,
    commit_timestamp: int64,
    leader_epoch: int32
  }
  
  Partitioned by: hash(group_id) % 50 (50 partitions)
  Compacted: only latest offset per key retained
  Retention: forever (compacted)
```

#### Metadata (KRaft / ZooKeeper)
```
Cluster metadata:
  /brokers/ids/{broker_id} → {host, port, rack, endpoints}
  /topics/{topic_name} → {partitions, config}
  /topics/{topic_name}/partitions/{partition_id} → {leader, replicas, isr}
  /controller → {broker_id, epoch}
  /cluster/id → cluster UUID

KRaft metadata log (replacing ZooKeeper):
  - Single Raft log for all cluster metadata
  - Snapshot + incremental log entries
  - Controller quorum: 3 or 5 nodes
  - Each broker caches metadata locally, applies updates from log
```

### Database/Store Choices
| Data | Store | Why |
|------|-------|-----|
| Message data | Append-only log files (local NVMe) | Sequential writes, zero-copy reads |
| Message indexes | Memory-mapped sparse index files | Fast offset lookups |
| Consumer offsets | Internal compacted topic | Self-hosted, durable, scalable |
| Cluster metadata | KRaft (Raft consensus log) | Strong consistency, no external dependency |
| Schema registry | PostgreSQL + cache | Schema evolution, compatibility checks |
| Cold data | S3/GCS (tiered storage) | Cost-effective long-term retention |
| Monitoring metrics | Prometheus TSDB | Time-series, PromQL |
| Connector state | Internal topic + KV store | Distributed, fault-tolerant |

## 5. High-Level Design

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           PRODUCERS                                               │
│  (Application Services, CDC Connectors, IoT, Log Shippers, Stream Processors)   │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │ Produce requests (batch, compressed)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      BROKER CLUSTER (100 nodes)                                   │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐│
│  │                    CONTROLLER QUORUM (KRaft)                                 ││
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ││
│  │  │Controller│  │Controller│  │Controller│  │ Voter    │  │ Voter    │  ││
│  │  │ (Active) │  │ (Standby)│  │ (Standby)│  │ (Broker) │  │ (Broker) │  ││
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  ││
│  │  Responsibilities: leader election, partition assignment, config, ACLs      ││
│  └────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐│
│  │                         DATA BROKERS                                        ││
│  │                                                                              ││
│  │  Broker 1                    Broker 2                    Broker N            ││
│  │  ┌────────────────────┐     ┌────────────────────┐     ┌─────────────────┐││
│  │  │                    │     │                    │     │                 │││
│  │  │ Network Threads    │     │ Network Threads    │     │ Network Threads │││
│  │  │ (Accept, Read,     │     │ (Accept, Read,     │     │                 │││
│  │  │  Write)            │     │  Write)            │     │                 │││
│  │  │         │          │     │         │          │     │                 │││
│  │  │ Request Handler    │     │ Request Handler    │     │                 │││
│  │  │ Threads (8)        │     │ Threads (8)        │     │                 │││
│  │  │         │          │     │         │          │     │                 │││
│  │  │ ┌──────────────┐  │     │ ┌──────────────┐  │     │                 │││
│  │  │ │Partition Mgr  │  │     │ │Partition Mgr  │  │     │                 │││
│  │  │ │              │  │     │ │              │  │     │                 │││
│  │  │ │ P0(L) P5(F)  │  │     │ │ P1(L) P0(F)  │  │     │                 │││
│  │  │ │ P3(L) P7(F)  │  │     │ │ P4(L) P3(F)  │  │     │                 │││
│  │  │ │ P9(L) P12(F) │  │     │ │ P6(L) P9(F)  │  │     │                 │││
│  │  │ └──────────────┘  │     │ └──────────────┘  │     │                 │││
│  │  │         │          │     │         │          │     │                 │││
│  │  │ ┌──────────────┐  │     │ ┌──────────────┐  │     │                 │││
│  │  │ │ Log Manager   │  │     │ │ Log Manager   │  │     │                 │││
│  │  │ │ (Segments,    │  │     │ │ (Segments,    │  │     │                 │││
│  │  │ │  Index, Flush)│  │     │ │  Index, Flush)│  │     │                 │││
│  │  │ └──────────────┘  │     │ └──────────────┘  │     │                 │││
│  │  │         │          │     │         │          │     │                 │││
│  │  │ ┌──────────────┐  │     │ ┌──────────────┐  │     │                 │││
│  │  │ │ Replication   │  │     │ │ Replication   │  │     │                 │││
│  │  │ │ Manager       │  │     │ │ Manager       │  │     │                 │││
│  │  │ │ (Fetch from   │  │     │ │ (Fetch from   │  │     │                 │││
│  │  │ │  leaders)     │  │     │ │  leaders)     │  │     │                 │││
│  │  │ └──────────────┘  │     │ └──────────────┘  │     │                 │││
│  │  │                    │     │                    │     │                 │││
│  │  │ [NVMe SSDs ×8]    │     │ [NVMe SSDs ×8]    │     │ [NVMe SSDs ×8] │││
│  │  │ 32 TB total       │     │ 32 TB total       │     │ 32 TB total    │││
│  │  └────────────────────┘     └────────────────────┘     └─────────────────┘││
│  └────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
│  REPLICATION: Leader-based, ISR (In-Sync Replicas), high-watermark              │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │ Fetch requests
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           CONSUMERS                                               │
│                                                                                  │
│  Consumer Group A          Consumer Group B          Consumer Group C            │
│  (Order Processing)        (Search Indexing)        (Analytics Pipeline)        │
│  ┌───┐ ┌───┐ ┌───┐       ┌───┐ ┌───┐             ┌───┐                       │
│  │C1 │ │C2 │ │C3 │       │C1 │ │C2 │             │C1 │ (Flink)               │
│  │P0 │ │P1 │ │P2 │       │P0,1│ │P2 │             │P0-2│                       │
│  └───┘ └───┘ └───┘       └───┘ └───┘             └───┘                       │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                      SUPPORTING SYSTEMS                                           │
│                                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Schema       │  │ Kafka        │  │ Tiered       │  │ Cruise       │      │
│  │ Registry     │  │ Connect      │  │ Storage      │  │ Control      │      │
│  │              │  │              │  │              │  │ (Auto-balance)│      │
│  │ Avro/Proto   │  │ MySQL CDC    │  │ S3 archival  │  │              │      │
│  │ Compatibility│  │ S3 Sink      │  │ Remote fetch │  │ Partition    │      │
│  │ Evolution    │  │ ES Sink      │  │ Lazy load    │  │ reassignment │      │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                        │
│  │ Kafka        │  │ Monitoring   │  │ Mirror       │                        │
│  │ Streams      │  │ (JMX→Prom   │  │ Maker        │                        │
│  │              │  │  →Grafana)   │  │ (Cross-DC)   │                        │
│  │ Stateful     │  │              │  │              │                        │
│  │ processing   │  │ Alerts       │  │ Topic mirror │                        │
│  │ Windows,joins│  │ SLO tracking │  │ Offset sync  │                        │
│  └──────────────┘  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD)

### Producer API
```
// Produce to topic (async with callback)
producer.send(new ProducerRecord<>(
    "orders",                          // topic
    "customer_456",                    // key (determines partition)
    orderCreatedEvent,                 // value (serialized)
    List.of(new Header("event_type", "order.created".getBytes()))
), callback);

// Transactional produce (exactly-once)
producer.initTransactions();
producer.beginTransaction();
try {
    producer.send(record1);
    producer.send(record2);
    producer.sendOffsetsToTransaction(offsets, groupId); // consume-transform-produce
    producer.commitTransaction();
} catch (Exception e) {
    producer.abortTransaction();
}
```

### Consumer API
```
// Subscribe to topic with consumer group
consumer.subscribe(List.of("orders"), rebalanceListener);

while (running) {
    ConsumerRecords<String, Order> records = consumer.poll(Duration.ofMillis(100));
    for (ConsumerRecord<String, Order> record : records) {
        process(record.key(), record.value(), record.headers());
    }
    consumer.commitSync(); // or commitAsync()
}

// Seek to specific offset (replay)
consumer.seek(new TopicPartition("orders", 0), 12345L);

// Seek to timestamp
Map<TopicPartition, Long> timestamps = Map.of(tp, 1705312000000L);
Map<TopicPartition, OffsetAndTimestamp> offsets = consumer.offsetsForTimes(timestamps);
consumer.seek(tp, offsets.get(tp).offset());
```

### Admin API
```http
POST /v1/topics
{
    "name": "orders",
    "partitions": 12,
    "replication_factor": 3,
    "configs": {
        "retention.ms": "604800000",
        "cleanup.policy": "delete",
        "compression.type": "zstd",
        "min.insync.replicas": "2",
        "segment.bytes": "1073741824",
        "max.message.bytes": "10485760"
    }
}

GET /v1/topics/orders
Response:
{
    "name": "orders",
    "partitions": [{
        "id": 0,
        "leader": 1,
        "replicas": [1, 3, 5],
        "isr": [1, 3, 5],
        "offline_replicas": []
    }, ...],
    "configs": {...}
}

POST /v1/topics/orders/partitions
{"total_count": 24}  // Increase partitions (cannot decrease)

GET /v1/consumer-groups/order-processor/offsets
Response:
{
    "group_id": "order-processor",
    "state": "Stable",
    "members": [...],
    "offsets": {
        "orders-0": {"offset": 123456, "lag": 50},
        "orders-1": {"offset": 789012, "lag": 0}
    }
}
```

## 7. Architecture Components Deep Dive

### 7.1 Produce Path (Write)
```
1. Producer serializes key + value (using configured serializer)
2. Partitioner selects partition:
   - If key != null: murmur2(key) % numPartitions (sticky to partition)
   - If key == null: round-robin with sticky batching
3. Record added to partition-specific batch buffer
4. Batch sent when: batch.size reached (16 KB) OR linger.ms elapsed (5ms)
5. Network thread sends ProduceRequest to partition leader broker
6. Leader broker:
   a. Validates: auth, quota, message size, schema (if enforced)
   b. Assigns offset to each record (monotonically increasing)
   c. Appends to partition log (page cache + async fsync)
   d. If acks=all: wait for all ISR replicas to replicate
   e. If acks=1: respond immediately after local write
   f. If acks=0: don't wait for response (fire-and-forget)
7. Response: offset, timestamp, partition for each record

Idempotent producer (exactly-once produce):
  - Producer gets unique producer_id from controller
  - Each produce carries sequence_number (per partition, monotonic)
  - Broker deduplicates: if sequence <= last_committed → return existing offset
  - Handles retries safely: same message never written twice
```

### 7.2 Consume Path (Read)
```
1. Consumer sends FetchRequest to partition leader:
   - fetch_offset: starting offset
   - min_bytes: minimum response size (wait until this much data)
   - max_wait_ms: maximum wait time for min_bytes
   - max_bytes: maximum response size
2. Leader broker:
   a. Locate segment file containing fetch_offset
   b. Read from offset position to min(max_bytes, high_watermark)
   c. Zero-copy transfer: sendfile() from page cache → NIC
   d. Return: records, high_watermark, log_start_offset
3. Consumer deserializes records
4. Consumer processes records
5. Consumer commits offset (async or sync):
   - Writes to __consumer_offsets internal topic

Zero-copy read (sendfile):
  - Avoids: disk → page cache → application buffer → socket buffer → NIC
  - Uses: disk → page cache → NIC (DMA transfer, zero CPU copies)
  - Benefit: ~5 GB/sec per broker throughput for consumer reads
  - Requirement: data must be in page cache (real-time consumers: always in cache)
```

### 7.3 Replication & ISR
```
ISR (In-Sync Replicas):
  - Set of replicas that are "caught up" to the leader
  - Caught up = replica's fetch offset within replica.lag.time.max.ms (10s default)
  - Leader tracks: LEO (Log End Offset) of each follower

High Watermark (HW):
  - Offset up to which all ISR replicas have replicated
  - Consumers can only read up to HW (no dirty reads)
  - HW advances when all ISR replicas acknowledge

Replication flow:
  1. Follower sends FetchRequest to leader (same as consumer fetch)
  2. Leader responds with new records since follower's last offset
  3. Follower appends to local log
  4. Follower sends next FetchRequest (implicit ACK of previous batch)
  5. Leader updates follower's LEO → recalculates HW

ISR shrink (follower falls behind):
  - If follower hasn't fetched within replica.lag.time.max.ms:
    - Remove from ISR
    - Leader can still produce (if remaining ISR ≥ min.insync.replicas)
  - Follower catches up → added back to ISR

Unclean leader election (data loss tradeoff):
  unclean.leader.election.enable = false (default):
    - If all ISR replicas die, partition is unavailable until ISR member recovers
    - Guarantees no data loss
  unclean.leader.election.enable = true:
    - Out-of-sync replica can become leader (may lose recent data)
    - Prefer availability over consistency
```

### 7.4 Log Compaction
```
Purpose: Keep only the latest value per key (infinite retention for changelogs)

How it works:
  1. Log cleaner thread scans "dirty" portion (after last clean point)
  2. Builds in-memory map: key → latest offset
  3. Rewrites segments keeping only latest record per key
  4. Tombstones (value=null): retained for delete.retention.ms, then removed

Use cases:
  - Database CDC changelog: latest state of each row
  - KTable in stream processing: materialized view
  - Configuration topics: latest config per key

Example:
  Before compaction:
    offset 0: key=A, value=1
    offset 1: key=B, value=2
    offset 2: key=A, value=3  ← newer value for A
    offset 3: key=C, value=4
    offset 4: key=B, value=null (tombstone)

  After compaction:
    offset 2: key=A, value=3  ← kept (latest for A)
    offset 3: key=C, value=4  ← kept (latest for C)
    offset 4: key=B, value=null ← kept (tombstone, until delete.retention.ms)

Config:
  cleanup.policy=compact (or "compact,delete" for both)
  min.compaction.lag.ms: minimum time before a record can be compacted
  min.cleanable.dirty.ratio: trigger compaction when dirty/total > ratio
```

### 7.5 Tiered Storage
```
Architecture:
  Local tier (NVMe): Recent segments (< 24 hours)
  Remote tier (S3): Older segments (> 24 hours, configurable)

Segment lifecycle:
  1. Active segment: writes go here (local only)
  2. Sealed segment: rolled, still local
  3. Uploaded: copied to S3 asynchronously after seal
  4. Offloaded: local copy deleted after S3 upload confirmed + retention
  5. Remote-only: only in S3, fetched on demand (rare consumer seek)

Benefits:
  - 10x cost reduction for long retention (S3: $0.023/GB vs NVMe: $0.30/GB)
  - Decouples storage from compute (brokers need less disk)
  - Elastic retention: keep years of data cheaply
  - Faster broker recovery: only need recent data locally

Remote fetch handling:
  - Consumer fetches old data → broker detects segment is remote
  - Broker fetches from S3 → caches locally → serves to consumer
  - Background prefetch for sequential reads
  - Latency: first read ~100-500ms (S3 GET), subsequent from local cache
```

## 8. Deep Dive: Consumer Group Rebalancing

### 8.1 Group Coordinator
```
Each consumer group has a coordinator (one of the brokers):
  Coordinator = broker owning partition: hash(group_id) % 50 of __consumer_offsets

Coordinator responsibilities:
  - Track group membership (heartbeats)
  - Trigger rebalance when members change
  - Commit offsets
  - Manage group state machine

Group states:
  Empty → PreparingRebalance → CompletingRebalance → Stable
    ↑                                                    │
    └────────── member leaves/joins/dies ────────────────┘
```

### 8.2 Partition Assignment Strategies
```
1. Range Assignor (default):
   Partitions: [P0, P1, P2, P3, P4, P5], Consumers: [C1, C2]
   C1: [P0, P1, P2], C2: [P3, P4, P5]
   
   Issue: uneven if partitions % consumers != 0

2. Round-Robin Assignor:
   C1: [P0, P2, P4], C2: [P1, P3, P5]
   Even distribution across all subscribed topics

3. Sticky Assignor (preferred):
   Minimizes partition movement on rebalance
   - Maintains previous assignment as much as possible
   - Only reassigns partitions from dead/removed consumers
   
4. Cooperative Sticky (incremental rebalance):
   - No "stop-the-world" rebalance
   - Only revokes specific partitions that need to move
   - Other partitions continue processing during rebalance
   - Two-phase: revoke → assign (consumers keep non-revoked partitions)
```

### 8.3 Static Group Membership
```
Problem: Container restarts cause frequent rebalances (even brief restarts)

Solution: group.instance.id (static membership)
  - Each consumer has persistent instance ID
  - On brief disconnect: no rebalance until session.timeout.ms expires
  - On reconnect with same instance ID: rejoin without rebalance
  - Benefit: eliminates unnecessary rebalances during rolling deploys

Config:
  session.timeout.ms = 300000 (5 minutes for static members)
  heartbeat.interval.ms = 10000
  group.instance.id = "order-processor-pod-1" (stable across restarts)
```

## 9. Component Optimization

### 9.1 Zero-Copy Optimization
```
Traditional read:
  Disk → Kernel buffer → User buffer → Socket buffer → NIC
  = 4 copies, 2 context switches

Zero-copy (sendfile):
  Disk → Kernel buffer (page cache) → NIC (via DMA)
  = 0 CPU copies, 1 context switch

Implementation:
  Java: FileChannel.transferTo() → Linux sendfile() syscall
  Condition: data must be in page cache (recent data always is)
  Impact: 5x throughput improvement for consumer reads
  
When zero-copy fails (fallback to user-space read):
  - SSL/TLS enabled (must encrypt in user space) → use sendfile with TLS offloading
  - Consumer reads very old data (not in page cache) → prefetch needed
  - Compression conversion needed (e.g., broker recompresses for consumer)
```

### 9.2 Page Cache Management
```
Strategy: Use OS page cache as read cache (no application-level cache)

Why:
  - OS manages LRU eviction automatically
  - No JVM GC overhead for cached data
  - Survives process restart (data still in page cache)
  - Automatic read-ahead for sequential access

Sizing guidance:
  Page cache = Total RAM - JVM Heap - OS overhead
  128 GB RAM - 6 GB heap - 2 GB OS = 120 GB page cache
  
  If consumer lag < page cache capacity:
    All consumer reads from memory (zero I/O)
    Example: 120 GB cache / 375 MB/sec writes = ~5.3 minutes of data cached
    If consumers are < 5 minutes behind: 100% cache hit rate

Optimization:
  - Produce writes: buffered (page cache), flushed by OS or explicit fsync
  - log.flush.interval.messages: flush every N messages (default: rely on OS)
  - log.flush.interval.ms: flush every N ms (default: rely on OS)
  - Recommendation: let OS manage flushing; replication provides durability
```

### 9.3 Batch Compression
```
Producer-side compression:
  - Compress entire batch of records together (better ratio than per-record)
  - Algorithms: zstd (best ratio), lz4 (fastest), snappy (good balance), gzip (legacy)
  - Compression happens in producer (offloads broker CPU)

Compression ratio benchmarks (for JSON events):
  - zstd: 4:1 compression (best, ~20% CPU overhead)
  - lz4: 2.5:1 compression (fast, ~5% CPU overhead)
  - snappy: 2:1 compression (very fast, ~3% CPU overhead)

End-to-end compression:
  1. Producer compresses batch
  2. Broker stores compressed (no decompression!)
  3. Follower replicates compressed bytes (no decompression!)
  4. Consumer receives compressed batch
  5. Consumer decompresses
  
  Result: compression saves storage AND network at every hop
  
Broker validation cost:
  - If message format conversion needed: broker must decompress/recompress
  - Avoid by matching producer message format version with broker version
```

### 9.4 Exactly-Once Semantics (EOS)
```
Components:
  1. Idempotent producer: prevents duplicate writes on retry
  2. Transactions: atomic multi-partition writes + offset commits

Idempotent producer:
  - producer_id (PID): unique ID assigned by broker
  - sequence_number: per-partition, monotonically increasing
  - Broker dedup: maintains (PID, partition) → last 5 sequence numbers
  - On duplicate: return success with original offset (no duplicate write)

Transactions:
  Transaction coordinator: broker owning hash(transactional_id) % 50

  Flow:
  1. Producer: InitPidRequest → get PID and epoch
  2. Producer: AddPartitionsToTxnRequest → register partitions in transaction
  3. Producer: ProduceRequest × N → write to multiple partitions
  4. Producer: AddOffsetsToTxnRequest → register consumer group offset commit
  5. Producer: TxnOffsetCommitRequest → write offsets (visible only after commit)
  6. Producer: EndTxnRequest(COMMIT) → coordinator writes COMMIT marker
  7. Coordinator: WriteTxnMarkersRequest → write commit markers to all partitions
  8. Consumers (isolation.level=read_committed): skip uncommitted/aborted records

  Guarantees:
  - All records in transaction are visible atomically (or none)
  - Consumer offsets committed atomically with produced records
  - Enables exactly-once consume-transform-produce pipelines
```

### 9.5 Partition Leadership & Load Balancing
```
Preferred replica election:
  - First replica in replica list is "preferred" leader
  - auto.leader.rebalance.enable: periodically restore preferred leaders
  - Ensures even leader distribution across brokers

Cruise Control (LinkedIn):
  - Automated partition rebalancing
  - Goals: even disk usage, even network I/O, even CPU, rack awareness
  - Constraint: min ISR, max replication throttle
  - Proposals: generated automatically, applied with approval

Rack awareness:
  - Replicas spread across racks/AZs: broker.rack=us-east-1a
  - Ensures AZ failure doesn't lose all replicas
  - Partition assignment respects rack constraint
```

### 9.6 Quotas & Multi-Tenancy
```
Quota types:
  1. Produce quota: bytes/sec limit per client-id/user
  2. Consume quota: bytes/sec limit per client-id/user
  3. Request rate quota: percentage of broker I/O threads per client
  4. Controller mutation quota: rate of topic/partition creates

Throttling mechanism:
  - Broker tracks bytes produced/consumed per client (sliding window)
  - When quota exceeded: delay response by throttle_time_ms
  - Client receives ThrottleTimeMs in response → backs off
  - No data loss: just slows down client

Multi-tenancy isolation:
  - Topic naming convention: {tenant}.{topic_name}
  - ACLs: tenant can only access their prefixed topics
  - Quotas: per-tenant produce/consume limits
  - Monitoring: per-tenant dashboards and alerting
```

## 10. Observability

### 10.1 Key Metrics
```yaml
# Broker metrics
kafka_server_broker_topic_metrics_messages_in_total{topic}            # Counter
kafka_server_broker_topic_metrics_bytes_in_total{topic}               # Counter
kafka_server_broker_topic_metrics_bytes_out_total{topic}              # Counter
kafka_server_replica_manager_under_replicated_partitions              # Gauge (should be 0!)
kafka_server_replica_manager_isr_shrinks_total                        # Counter
kafka_server_replica_manager_isr_expands_total                        # Counter
kafka_controller_active_controller_count                              # Gauge (exactly 1)
kafka_server_request_handler_avg_idle_percent                         # Gauge (< 30% = overloaded)

# Request metrics
kafka_network_request_metrics_total_time_ms{request_type}             # Histogram
kafka_network_request_metrics_requests_per_sec{request_type}          # Gauge
kafka_server_request_handler_produce_request_queue_time_ms            # Histogram
kafka_server_request_handler_produce_response_send_time_ms            # Histogram

# Consumer group metrics
kafka_consumer_group_lag{group, topic, partition}                     # Gauge (critical!)
kafka_consumer_group_state{group}                                     # Gauge (Stable/Rebalancing)
kafka_consumer_group_members{group}                                   # Gauge

# Partition metrics
kafka_log_log_size{topic, partition}                                  # Gauge (bytes)
kafka_log_log_start_offset{topic, partition}                          # Gauge
kafka_log_log_end_offset{topic, partition}                            # Gauge
kafka_server_replica_fetcher_max_lag                                  # Gauge

# JVM metrics
kafka_jvm_gc_collection_time_ms{gc}                                   # Counter
kafka_jvm_memory_heap_used_bytes                                      # Gauge
kafka_jvm_threads_current                                             # Gauge

# Disk metrics
kafka_log_log_flush_time_ms                                           # Histogram
kafka_server_log_dir_disk_usage_bytes{logdir}                         # Gauge
kafka_server_log_dir_offline_dirs                                     # Gauge (should be 0!)
```

### 10.2 Alerting
```yaml
# Critical
- alert: UnderReplicatedPartitions
  expr: kafka_server_replica_manager_under_replicated_partitions > 0
  for: 2m
  severity: critical
  description: "Partitions are under-replicated — risk of data loss on failure"

- alert: NoActiveController
  expr: sum(kafka_controller_active_controller_count) != 1
  for: 30s
  severity: critical

- alert: OfflineDisk
  expr: kafka_server_log_dir_offline_dirs > 0
  for: 1m
  severity: critical

- alert: ConsumerLagCritical
  expr: kafka_consumer_group_lag > 1000000
  for: 5m
  severity: critical
  description: "Consumer group {{ $labels.group }} lag > 1M on {{ $labels.topic }}"

# Warning
- alert: ISRShrinking
  expr: rate(kafka_server_replica_manager_isr_shrinks_total[5m]) > 0
  for: 5m
  severity: warning

- alert: HighProduceLatency
  expr: kafka_network_request_metrics_total_time_ms{request_type="Produce"} > 100
  for: 5m
  severity: warning

- alert: LowRequestHandlerIdlePercent
  expr: kafka_server_request_handler_avg_idle_percent < 0.3
  for: 10m
  severity: warning
  description: "Request handlers > 70% utilized — nearing capacity"

- alert: DiskUsageHigh
  expr: kafka_server_log_dir_disk_usage_bytes / kafka_server_log_dir_disk_capacity_bytes > 0.8
  for: 30m
  severity: warning
```

## 11. Considerations and Assumptions

### Design Decisions

| Decision | Chosen | Alternative | Rationale |
|----------|--------|-------------|-----------|
| Consensus | KRaft (Raft) | ZooKeeper | No external dependency, simpler operations |
| Ordering | Per-partition only | Global ordering | Global ordering doesn't scale; partition ordering is sufficient |
| Storage | Local NVMe + tiered S3 | Only local | Cost-effective long retention |
| Replication | ISR-based (async with acks) | Raft per partition | Higher throughput; ISR allows tunable durability |
| Consumer model | Pull-based | Push-based | Consumer controls rate; backpressure natural |
| Wire protocol | Custom binary | gRPC | Lower overhead, zero-copy possible |
| Compression | Producer-side, broker pass-through | Broker-side | Offloads CPU from broker |
| Schema | Schema Registry (separate) | Schema in broker | Separation of concerns |

### Trade-offs

| Trade-off | Benefit | Cost |
|-----------|---------|------|
| Partition = unit of parallelism | Simple scaling model | Can't reorder across partitions |
| ISR vs Raft per partition | Higher throughput | Possible data loss if ISR=0 on unclean election |
| Pull vs Push consumers | Natural backpressure, replay | Slightly higher latency (mitigated by long poll/fetch) |
| Page cache as read cache | Simple, survives restarts | Less control than application cache |
| Append-only log | Fast sequential I/O | No in-place updates (deletion = compaction) |
| At-least-once default | Simple, performant | Consumers must handle duplicates (or use EOS) |

### Failure Modes

| Failure | Impact | Recovery |
|---------|--------|----------|
| Leader broker crash | Partition unavailable until election (~5s) | ISR follower elected leader; no data loss |
| All ISR replicas fail | Partition unavailable (if unclean=false) | Wait for ISR member to recover |
| Controller failure | No new topic/partition creates | KRaft: standby controller takes over (<5s) |
| Network partition | Split ISR, potential stale reads | Fencing via leader epoch; min.insync prevents stale writes |
| Disk failure | Partitions on that disk unavailable | Reassign partitions from replicas; replace disk |
| Consumer lag spiral | Processing falls further behind | Scale consumers; skip to latest (if acceptable) |
| Schema incompatibility | Consumers fail to deserialize | Schema Registry compatibility checks prevent this |
| Broker OOM | Broker crash | Tune heap, max.message.bytes, buffer sizes; restart auto-recovers |
