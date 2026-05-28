# Design a Distributed Queue (Like SQS/RabbitMQ)

## 1. Functional Requirements

- **Message Publishing**: Producers publish messages to named queues with at-least-once delivery guarantee
- **Message Consumption**: Consumers pull or receive pushed messages with configurable acknowledgment
- **Visibility Timeout**: After delivery, message is invisible to other consumers until ack or timeout (prevents duplicate processing)
- **Dead Letter Queue (DLQ)**: Move messages that fail processing N times to a DLQ for investigation
- **Message Delay**: Schedule messages for future delivery (delay seconds/minutes/hours)
- **Priority Queues**: Support message priority levels (higher priority consumed first)
- **FIFO Ordering**: Optionally guarantee strict ordering within a message group
- **Batch Operations**: Send/receive/delete multiple messages in a single API call
- **Message Deduplication**: Detect and reject duplicate messages within a dedup window
- **Long Polling**: Consumers wait for messages (up to 20s) instead of empty responses
- **Fan-out**: Single message delivered to multiple queues via pub/sub topics
- **Message Filtering**: Consumers receive only messages matching attribute-based filters
- **Retention**: Configurable message retention (1 minute to 14 days)
- **Redrive Policy**: Configure max receive count before moving to DLQ
- **Message Attributes**: Metadata key-value pairs on messages without touching body
- **Queue Management**: Create, delete, list, purge, get attributes, tag queues
- **Access Control**: Per-queue permissions (who can send, receive, manage)
- **Encryption**: At-rest encryption (KMS) and in-transit encryption (TLS)

## 2. Non-Functional Requirements

| NFR | Target |
|-----|--------|
| **Availability** | 99.99% (multi-AZ replication) |
| **Latency** | p99 < 20ms for send, p99 < 50ms for receive (excluding long poll) |
| **Throughput** | 100K messages/sec per queue, 10M messages/sec cluster-wide |
| **Durability** | 99.9999999% (11 nines) — no acknowledged message loss |
| **Ordering** | Best-effort (standard queue) or strict FIFO per message group |
| **Scalability** | Auto-scale queues independently; no queue size limit |
| **Message Size** | Up to 256 KB per message (reference pattern for larger payloads) |
| **Retention** | Configurable: 1 min to 14 days (default 4 days) |
| **Deduplication Window** | 5-minute content-based or ID-based deduplication |
| **Visibility Timeout** | 0 seconds to 12 hours (default 30 seconds) |
| **Consumers** | Unlimited consumers per queue |

## 3. Capacity Estimation

### Assumptions
| Dimension | Value |
|-----------|-------|
| Total queues | 1 million |
| Messages/day (all queues) | 100 billion |
| Average message size | 4 KB (body + attributes) |
| Peak message rate | 10 million messages/sec |
| Average retention | 4 days |
| Consumers per queue (avg) | 5 |
| DLQ utilization | 0.1% of messages end up in DLQ |
| FIFO queues | 10% of total queues |

### QPS/RPS Calculation
```
Total daily messages: 100 billion
Average send rate: 100B / 86,400 = 1.16M messages/sec
Peak send rate: 1.16M × 8 = ~10M messages/sec
Average receive rate: ~1.16M msg/sec × avg 1.2 deliveries/msg = 1.4M/sec
Peak receive rate: 12M/sec
Delete rate: ~equal to receive rate (ack after processing)
Total peak operations: 10M + 12M + 12M = 34M ops/sec
```

### Storage Estimation
```
Messages in-flight at any moment: 10M msg/sec × 30s visibility timeout = 300M messages
Messages retained (4-day avg): 100B/day × 4 days = 400 billion messages
Storage: 400B × 4 KB = 1.6 PB raw data
With replication (3x): 4.8 PB total storage
With metadata overhead (20%): ~5.76 PB

Per-partition storage: assuming 100K partitions = 57.6 TB per partition
Index storage: 400B messages × 64 bytes index entry = 25.6 TB
```

### Network Bandwidth
```
Send bandwidth: 10M msg/sec × 4 KB = 40 GB/s = 320 Gbps (peak)
Receive bandwidth: 12M msg/sec × 4 KB = 48 GB/s = 384 Gbps (peak)  
Replication bandwidth: 40 GB/s × 2 (to 2 replicas) = 80 GB/s = 640 Gbps
Total: ~1.3 Tbps aggregate bandwidth

Per-broker (500 brokers): 2.6 Gbps average
```

### Infrastructure
```
Storage brokers: 500 nodes × 12 TB NVMe each = 6 PB (matches requirement)
Front-end (API) nodes: 100 (handles 340K ops/sec each)
Metadata nodes: 5 (Raft consensus for queue metadata)
Router/Scheduler nodes: 50 (message routing and scheduling)
Monitoring: 10 nodes (metrics, alerting)
```

## 4. Data Modeling

### Database Choice
| Data | Store | Why |
|------|-------|-----|
| Queue metadata (config, attributes) | PostgreSQL / etcd | Strong consistency, low volume |
| Message data (body + attributes) | Custom append-only log (on NVMe) | High throughput sequential writes |
| Message index (delivery state) | RocksDB (per-partition) | Fast point lookups + range scans |
| Visibility state (in-flight messages) | In-memory + WAL | Low latency for timeout tracking |
| DLQ messages | Same as message store | Treated as regular queue |
| Delayed messages | Priority queue (min-heap) + disk | Sorted by delivery time |
| Deduplication index | Bloom filter + LRU cache | Space-efficient, 5-min window |
| Metrics/analytics | Prometheus + ClickHouse | Time-series + analytical queries |
| Access control | PostgreSQL | ACL policies per queue |

### Schema Design

#### `queues` (PostgreSQL - Metadata Store)
```sql
CREATE TABLE queues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(10) NOT NULL DEFAULT 'standard', -- standard, fifo
    visibility_timeout_seconds INT DEFAULT 30,
    message_retention_seconds INT DEFAULT 345600, -- 4 days
    max_message_size_bytes INT DEFAULT 262144,    -- 256 KB
    delay_seconds INT DEFAULT 0,                  -- default delay for all messages
    receive_message_wait_time_seconds INT DEFAULT 0, -- long poll timeout
    redrive_policy JSONB,
    -- {"deadLetterTargetArn": "queue_uuid", "maxReceiveCount": 5}
    deduplication_scope VARCHAR(20) DEFAULT 'queue', -- queue, messageGroup
    content_based_deduplication BOOLEAN DEFAULT false,
    fifo_throughput_limit VARCHAR(20) DEFAULT 'perQueue', -- perQueue, perMessageGroupId
    encryption_config JSONB,
    -- {"kmsKeyId": "key_uuid", "dataKeyReusePeriodSeconds": 300}
    tags JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    approximate_message_count BIGINT DEFAULT 0,
    approximate_not_visible_count BIGINT DEFAULT 0,
    approximate_delayed_count BIGINT DEFAULT 0,
    UNIQUE(account_id, name)
);

CREATE INDEX idx_queues_account ON queues(account_id);
CREATE INDEX idx_queues_name ON queues(account_id, name);
CREATE INDEX idx_queues_dlq ON queues(id) WHERE (redrive_policy->>'deadLetterTargetArn') IS NOT NULL;
```

#### Message Storage (Custom Append-Only Log)
```
File structure per partition:
  /data/queue_{id}/partition_{n}/
    ├── segment_000000000000.log   (append-only message data)
    ├── segment_000000000000.idx   (offset → file position index)
    ├── segment_000000000001.log
    ├── segment_000000000001.idx
    ├── visibility.wal             (in-flight message tracking)
    └── checkpoint.bin             (last committed state)

Segment format:
  ┌────────────────────────────────────────┐
  │ Message Entry                           │
  ├────────────────────────────────────────┤
  │ Length (4 bytes, big-endian)            │
  │ CRC32 (4 bytes)                        │
  │ Timestamp (8 bytes, unix ms)           │
  │ Message ID (16 bytes, UUID)            │
  │ Sequence Number (8 bytes)              │
  │ Delivery Timestamp (8 bytes)           │  -- for delayed messages
  │ Attributes Count (2 bytes)             │
  │ Attributes (variable)                  │
  │   Key Length (2) + Key + Value Len (2) + Value
  │ Body Length (4 bytes)                  │
  │ Body (variable, up to 256 KB)         │
  │ Dedup ID Length (2 bytes)             │
  │ Dedup ID (variable, optional)         │
  │ Group ID Length (2 bytes)             │  -- for FIFO queues
  │ Group ID (variable, optional)         │
  └────────────────────────────────────────┘

Segment size: 1 GB per segment, then roll to new segment
Index: sparse index every 4 KB of messages (position → file offset)
```

#### Visibility Index (RocksDB per partition)
```
Key: message_id (16 bytes)
Value: {
    sequence_number: u64,
    state: u8,              // AVAILABLE=0, IN_FLIGHT=1, DELAYED=2, DELETED=3
    receive_count: u16,
    first_receive_ts: u64,
    visibility_deadline: u64,  // When message becomes visible again
    receipt_handle: [u8; 32],  // Opaque handle for ack/nack
}

// Additional indexes:
// For available messages: sorted by sequence_number (FIFO) or priority
// For in-flight messages: sorted by visibility_deadline (timeout check)
// For delayed messages: sorted by delivery_timestamp
```

#### Deduplication Cache (Bloom Filter + HashMap)
```
Structure:
  - Bloom filter: 10M bits, 7 hash functions → 1% false positive
    - Memory: ~1.2 MB per queue
    - Used for fast negative check (definitely not seen)
  - HashMap (LRU): dedup_id → expiry_timestamp
    - Capacity: 100K entries per queue
    - Entry size: 32 bytes key + 8 bytes timestamp = 40 bytes
    - Memory: 4 MB per queue
  - Window: 5 minutes (entries expire after 5 min)
  
On message arrival:
  1. Check bloom filter: if NO → definitely new, accept
  2. If bloom says MAYBE → check HashMap for exact match
  3. If found in HashMap and not expired → reject (duplicate)
  4. If not found → accept, add to both bloom and HashMap
```

## 5. High-Level Design

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PRODUCERS & CONSUMERS                                      │
│  (Microservices, Lambda Functions, IoT Devices, Background Jobs)            │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        API LAYER (Front-End Fleet)                            │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ API Node 1   │  │ API Node 2   │  │ API Node N   │  │ API Node 100 │  │
│  │              │  │              │  │              │  │              │  │
│  │ • Auth/AuthZ │  │ • Auth/AuthZ │  │ • Auth/AuthZ │  │ • Auth/AuthZ │  │
│  │ • Validation │  │ • Validation │  │ • Validation │  │ • Validation │  │
│  │ • Routing    │  │ • Routing    │  │ • Routing    │  │ • Routing    │  │
│  │ • Rate Limit │  │ • Rate Limit │  │ • Rate Limit │  │ • Rate Limit │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                              │
│  Stateless, auto-scaled behind NLB                                          │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MESSAGE BROKER CLUSTER                                     │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              PARTITION MANAGER / ROUTER                               │   │
│  │  • Maps queue → partitions → broker nodes                           │   │
│  │  • Handles partition leader election                                  │   │
│  │  • Coordinates rebalancing on node add/remove                        │   │
│  └─────────────────────────────────┬───────────────────────────────────┘   │
│                                    │                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │              STORAGE BROKERS                                           │ │
│  │                                                                        │ │
│  │  Broker 1 (Partitions P1, P5, P9)     Broker 2 (P2, P6, P10)        │ │
│  │  ┌──────────────────────────────┐     ┌──────────────────────────┐   │ │
│  │  │ ┌────────┐ ┌────────┐       │     │ ┌────────┐ ┌────────┐   │   │ │
│  │  │ │ Write  │ │ Read   │       │     │ │ Write  │ │ Read   │   │   │ │
│  │  │ │ Engine │ │ Engine │       │     │ │ Engine │ │ Engine │   │   │ │
│  │  │ └───┬────┘ └───┬────┘       │     │ └───┬────┘ └───┬────┘   │   │ │
│  │  │     │           │            │     │     │           │        │   │ │
│  │  │ ┌───▼───────────▼────┐      │     │ ┌───▼───────────▼────┐  │   │ │
│  │  │ │   Append-Only Log   │      │     │ │   Append-Only Log   │  │   │ │
│  │  │ │   (NVMe SSD)        │      │     │ │   (NVMe SSD)        │  │   │ │
│  │  │ └────────────────────┘      │     │ └────────────────────┘  │   │ │
│  │  │ ┌────────────────────┐      │     │ ┌────────────────────┐  │   │ │
│  │  │ │  Visibility Tracker │      │     │ │  Visibility Tracker │  │   │ │
│  │  │ │  (In-memory + WAL)  │      │     │ │  (In-memory + WAL)  │  │   │ │
│  │  │ └────────────────────┘      │     │ └────────────────────┘  │   │ │
│  │  │ ┌────────────────────┐      │     │ ┌────────────────────┐  │   │ │
│  │  │ │  Delay Scheduler    │      │     │ │  Delay Scheduler    │  │   │ │
│  │  │ │  (Min-Heap)         │      │     │ │  (Min-Heap)         │  │   │ │
│  │  │ └────────────────────┘      │     │ └────────────────────┘  │   │ │
│  │  └──────────────────────────────┘     └──────────────────────────┘   │ │
│  │                                                                        │ │
│  │  Broker 3 (Replicas: P1', P2', P5')  Broker N (...)                  │ │
│  │  ┌──────────────────────────────┐     ┌──────────────────────────┐   │ │
│  │  │ REPLICA (async or sync)      │     │ ...                       │   │ │
│  │  │ Receives WAL from leader     │     │                           │   │ │
│  │  │ Promotes on leader failure   │     │                           │   │ │
│  │  └──────────────────────────────┘     └──────────────────────────┘   │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  REPLICATION: Raft consensus (sync) or chain replication (async)            │
│  PARTITIONING: Each queue split into 1-1000 partitions based on throughput │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                    SUPPORTING SERVICES                                        │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Metadata     │  │ Delay        │  │ DLQ          │  │ Metrics &    │  │
│  │ Service      │  │ Service      │  │ Manager      │  │ Billing      │  │
│  │              │  │              │  │              │  │              │  │
│  │ Queue CRUD   │  │ Timer wheel  │  │ Max receive  │  │ Message count│  │
│  │ ACLs, Tags   │  │ Delayed msg  │  │ count check  │  │ Byte count   │  │
│  │ Attributes   │  │ scheduling   │  │ Auto-redrive │  │ API calls    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │ Garbage      │  │ Replication  │  │ Auto-Scale   │                     │
│  │ Collector    │  │ Manager      │  │ Controller   │                     │
│  │              │  │              │  │              │                     │
│  │ Expired msg  │  │ Leader elect │  │ Partition    │                     │
│  │ cleanup      │  │ Replica sync │  │ split/merge  │                     │
│  │ Segment roll │  │ Failover     │  │ based on load│                     │
│  └──────────────┘  └──────────────┘  └──────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Microservice Patterns

| Pattern | Application |
|---------|-------------|
| **Partitioning** | Queue data sharded across partitions for parallelism |
| **Raft Consensus** | Partition replication for durability |
| **Competing Consumers** | Multiple consumers pulling from same queue |
| **Visibility Timeout** | Lease-based message locking |
| **Dead Letter Queue** | Poison message isolation |
| **Timer Wheel** | Efficient delayed message scheduling |
| **Request-Reply** | Synchronous messaging via correlation IDs |
| **Claim Check** | Large payloads stored in S3, reference in message |

## 6. Low-Level Design (LLD)

### Public APIs

**Send Message**
```http
POST /v1/queues/{queue_id}/messages
Authorization: Bearer <token>
Content-Type: application/json

Request:
{
    "message_body": "{\"order_id\": \"ord_123\", \"action\": \"process\"}",
    "delay_seconds": 0,
    "message_attributes": {
        "event_type": {"data_type": "String", "string_value": "order.created"},
        "priority": {"data_type": "Number", "string_value": "5"},
        "source": {"data_type": "String", "string_value": "order-service"}
    },
    "message_deduplication_id": "order_123_created_v1",
    "message_group_id": "customer_456"
}

Response: 200 OK
{
    "message_id": "msg_7f8g9h0j1k2l",
    "sequence_number": "10000000000000000001",
    "md5_of_body": "098f6bcd4621d373cade4e832627b4f6",
    "md5_of_attributes": "a1b2c3d4e5f6...",
    "deduplication_applied": false
}
```

**Send Message Batch**
```http
POST /v1/queues/{queue_id}/messages:batchSend
Authorization: Bearer <token>

Request:
{
    "entries": [
        {
            "id": "batch_entry_1",
            "message_body": "...",
            "delay_seconds": 0,
            "message_attributes": {}
        },
        {
            "id": "batch_entry_2",
            "message_body": "...",
            "delay_seconds": 60
        }
    ]
}

Response: 200 OK
{
    "successful": [
        {"id": "batch_entry_1", "message_id": "msg_abc", "sequence_number": "1001"}
    ],
    "failed": [
        {"id": "batch_entry_2", "code": "InvalidMessageBody", "message": "Body too large"}
    ]
}
```

**Receive Messages**
```http
POST /v1/queues/{queue_id}/messages:receive
Authorization: Bearer <token>

Request:
{
    "max_number_of_messages": 10,
    "visibility_timeout_seconds": 60,
    "wait_time_seconds": 20,
    "message_attribute_names": ["event_type", "priority"],
    "message_filter": {
        "event_type": ["order.created", "order.updated"],
        "priority": [{"numeric": [">=", 3]}]
    }
}

Response: 200 OK
{
    "messages": [
        {
            "message_id": "msg_7f8g9h0j1k2l",
            "receipt_handle": "AQEBwJnKyrHigUMZj6...",
            "body": "{\"order_id\": \"ord_123\", \"action\": \"process\"}",
            "attributes": {
                "sent_timestamp": "1705312000000",
                "approximate_receive_count": "1",
                "approximate_first_receive_timestamp": "1705312005000",
                "sequence_number": "10000000000000000001",
                "message_group_id": "customer_456"
            },
            "message_attributes": {
                "event_type": {"data_type": "String", "string_value": "order.created"},
                "priority": {"data_type": "Number", "string_value": "5"}
            },
            "md5_of_body": "098f6bcd...",
            "md5_of_attributes": "a1b2c3d4..."
        }
    ]
}
```

**Acknowledge (Delete) Message**
```http
DELETE /v1/queues/{queue_id}/messages/{receipt_handle}
Authorization: Bearer <token>

Response: 204 No Content
```

**Change Visibility Timeout**
```http
PATCH /v1/queues/{queue_id}/messages/{receipt_handle}/visibility
Authorization: Bearer <token>

Request:
{
    "visibility_timeout_seconds": 120
}

Response: 200 OK
{
    "receipt_handle": "AQEBwJnKyrHigUMZj6...",
    "new_visibility_deadline": "2024-01-15T10:02:00Z"
}
```

**Create Queue**
```http
POST /v1/queues
Authorization: Bearer <token>
Idempotency-Key: <uuid>

Request:
{
    "name": "order-processing",
    "type": "fifo",
    "attributes": {
        "visibility_timeout_seconds": 60,
        "message_retention_seconds": 604800,
        "delay_seconds": 0,
        "max_message_size_bytes": 262144,
        "receive_wait_time_seconds": 20,
        "redrive_policy": {
            "dead_letter_queue_id": "queue_dlq_orders",
            "max_receive_count": 5
        },
        "content_based_deduplication": true
    },
    "encryption": {
        "kms_key_id": "key_abc123"
    },
    "tags": {
        "team": "payments",
        "environment": "production"
    }
}

Response: 201 Created
{
    "queue_id": "queue_7f8g9h0j",
    "queue_url": "https://queue.platform.com/v1/queues/queue_7f8g9h0j",
    "name": "order-processing.fifo",
    "created_at": "2024-01-15T10:00:00Z"
}
```

### Internal APIs (gRPC)
```protobuf
syntax = "proto3";
package queue.broker.v1;

service BrokerService {
    // Partition leader handles writes
    rpc AppendMessage(AppendRequest) returns (AppendResponse);
    rpc AppendBatch(BatchAppendRequest) returns (BatchAppendResponse);
    
    // Partition leader handles reads
    rpc FetchMessages(FetchRequest) returns (FetchResponse);
    rpc AcknowledgeMessage(AckRequest) returns (AckResponse);
    rpc NackMessage(NackRequest) returns (NackResponse);
    rpc ChangeVisibility(ChangeVisibilityRequest) returns (ChangeVisibilityResponse);
    
    // Replication
    rpc ReplicateEntries(stream ReplicationEntry) returns (stream ReplicationAck);
    rpc RequestSnapshot(SnapshotRequest) returns (stream SnapshotChunk);
    
    // Leader election
    rpc RequestVote(VoteRequest) returns (VoteResponse);
    rpc AppendEntries(AppendEntriesRequest) returns (AppendEntriesResponse);
}

service PartitionManager {
    rpc GetPartitionLeader(PartitionRequest) returns (LeaderInfo);
    rpc ListPartitions(ListPartitionsRequest) returns (ListPartitionsResponse);
    rpc SplitPartition(SplitRequest) returns (SplitResponse);
    rpc MergePartitions(MergeRequest) returns (MergeResponse);
    rpc ReassignPartition(ReassignRequest) returns (ReassignResponse);
}
```

### Design Patterns

| Pattern | Implementation |
|---------|---------------|
| **Producer-Consumer** | Core queue semantics with decoupling |
| **Competing Consumers** | Multiple consumers receive from partitions |
| **Lease/Lock** | Visibility timeout as time-bounded lease |
| **Retry with Backoff** | Exponential backoff on redelivery |
| **Circuit Breaker** | Consumer-side circuit breaker on processing failures |
| **Claim Check** | S3 reference for messages > 256 KB |
| **Saga** | Multi-step processing with DLQ for compensation |
| **Timer Wheel** | Hierarchical timer wheel for delayed messages |
| **WAL (Write-Ahead Log)** | Durability before acknowledgment |

## 7. Architecture Components Deep Dive

### 7.1 Write Path (Message Send)
```
1. API node receives SendMessage request
2. Validate: size, attributes, permissions, encryption
3. If dedup enabled: check dedup cache (bloom + hashmap)
4. Compute partition: 
   - Standard queue: round-robin or hash(message_group_id)
   - FIFO queue: hash(message_group_id) → specific partition
5. Route to partition leader broker
6. Broker appends to WAL:
   a. Serialize message to binary format
   b. Write to page-aligned buffer
   c. Batch fsync (every 1ms or buffer full, whichever first)
7. Replicate to followers (Raft or chain replication):
   - Wait for majority ack (2 of 3 nodes)
8. Update in-memory index:
   - If delay_seconds > 0: add to delay scheduler (min-heap)
   - If delay_seconds == 0: add to available message queue
9. Return message_id and sequence_number to client

Write amplification: 
  - 1 local write + 2 replica writes = 3x write amplification
  - Batching amortizes fsync cost: 1000 messages per fsync
```

### 7.2 Read Path (Message Receive)
```
1. API node receives ReceiveMessages request
2. Route to partition leader(s) for the queue
3. Broker checks available messages:
   a. Scan available index from current position
   b. Apply message filter (attribute-based filtering)
   c. Skip messages with active visibility timeout
   d. Collect up to max_number_of_messages
4. For each selected message:
   a. Mark as IN_FLIGHT in visibility tracker
   b. Set visibility_deadline = now + visibility_timeout
   c. Generate receipt_handle (opaque, includes: partition, offset, timestamp, HMAC)
   d. Increment receive_count
5. If no messages available and wait_time > 0:
   a. Register consumer in wait queue
   b. Hold connection open (long polling)
   c. On new message arrival: wake waiting consumer
   d. On timeout: return empty response
6. Return messages with receipt handles

Long polling implementation:
  - Consumers wait on condition variable per partition
  - On message append: signal one waiting consumer
  - Timeout: epoll timer fires, consumer gets empty response
  - Efficient: no busy-waiting, no repeated empty requests
```

### 7.3 Visibility Timeout & Acknowledgment
```
Visibility timeout lifecycle:
  1. Message received → marked IN_FLIGHT, deadline set
  2. Consumer processes message successfully → DELETE (ack)
  3. Consumer fails to ack within timeout → message becomes AVAILABLE again

Visibility tracker (per partition):
  Data structure: Min-heap ordered by visibility_deadline
  
  Timer thread:
    every 100ms:
      while heap.peek().deadline <= now:
        msg = heap.pop()
        if msg.state == IN_FLIGHT:  // not already acked
          msg.state = AVAILABLE
          msg.receive_count++
          add to available queue
          
          if msg.receive_count >= max_receive_count:
            move to DLQ (redrive)

Receipt handle structure:
  HMAC-SHA256(secret, partition_id + sequence_number + receive_timestamp + nonce)
  - Includes all info to identify the exact delivery
  - HMAC prevents forging (can't ack other consumer's messages)
  - Expires: invalid after visibility_timeout + buffer
```

### 7.4 FIFO Queue Ordering
```
Guarantee: Messages in same message_group_id delivered in order

Implementation:
  - Partition by message_group_id (consistent hashing)
  - Within partition: strict sequence_number ordering
  - Only one message per group in-flight at a time

Group-level locking:
  - When message from group G is delivered:
    - Lock group G (no more messages from G until ack or timeout)
    - Next message from G only delivered after current is acked
  - This ensures exactly-once-in-order processing per group

Throughput impact:
  - Standard queue: unlimited parallelism within partition
  - FIFO queue: parallelism limited to number of active groups
  - Recommendation: use many message_group_ids for higher throughput
  - High-throughput FIFO: 30,000 msg/sec per queue (per-group locking)
```

### 7.5 Delay Scheduler
```
Data structure: Hierarchical Timer Wheel

Wheels:
  - Level 0: 1-second slots × 60 = messages delayed 0-60s
  - Level 1: 1-minute slots × 60 = messages delayed 1-60min
  - Level 2: 1-hour slots × 24 = messages delayed 1-24h
  - Level 3: 1-day slots × 14 = messages delayed 1-14d

On message with delay:
  1. Compute which wheel/slot based on delivery_time
  2. Insert into appropriate slot
  3. Persist to disk (WAL) for crash recovery

Timer tick (every 1 second):
  1. Advance Level 0 by one slot
  2. All messages in current Level 0 slot → move to available queue
  3. Every 60 seconds: cascade Level 1 → Level 0
  4. Every 3600 seconds: cascade Level 2 → Level 1
  
Advantages over sorted data structures:
  - Insert: O(1) vs O(log n) for heap
  - Tick processing: O(messages_in_slot) amortized
  - Memory efficient: just arrays of linked lists
  - Handles millions of delayed messages efficiently
```

### 7.6 Dead Letter Queue (DLQ)
```
Redrive policy:
{
    "deadLetterTargetArn": "queue_dlq_id",
    "maxReceiveCount": 5
}

DLQ flow:
  1. Message receive_count reaches maxReceiveCount
  2. Instead of making available again:
     a. Copy message to DLQ (with original attributes preserved)
     b. Add DLQ-specific attributes:
        - original_queue_id
        - original_message_id
        - redrive_count
        - first_sent_timestamp
        - error_details (if available)
     c. Delete from source queue
  3. DLQ is a regular queue (can be consumed, purged, monitored)

Redrive (replay from DLQ):
  POST /v1/queues/{dlq_id}/messages:redrive
  {
      "target_queue_id": "original_queue_id",
      "max_messages": 1000
  }
  - Moves messages from DLQ back to original queue for reprocessing
  - Useful after fixing consumer bugs
```

## 8. Deep Dive: Replication & Durability

### 8.1 Raft-Based Partition Replication
```
Each partition has a Raft group (typically 3 nodes: 1 leader, 2 followers)

Write flow:
  1. Leader receives append request
  2. Leader appends to local WAL
  3. Leader sends AppendEntries RPC to followers
  4. Followers append to their WAL, respond
  5. Leader commits when majority (2/3) acknowledge
  6. Leader responds to client: message durably stored

Commit guarantee:
  - Message is committed when on 2+ nodes' WAL
  - Even if leader crashes, committed messages survive
  - New leader has all committed entries

Leader election:
  - If followers don't hear from leader within election_timeout (150-300ms):
    - Increment term
    - Vote for self
    - Request votes from others
    - Win with majority → become new leader
  - Election time: typically < 500ms

Consistency:
  - Linearizable writes (all go through leader)
  - Reads can be stale if reading from followers
  - For receive: always read from leader (to ensure visibility consistency)
```

### 8.2 Storage Engine (Append-Only Log)
```
Design goals:
  - Sequential write (NVMe optimal): 3 GB/s sustained
  - Fast point reads: message by offset/ID
  - Efficient range scans: batch fetch available messages
  - Low write amplification: append-only, no in-place updates

Segment management:
  Active segment: currently being written to
  Sealed segments: read-only, candidates for compaction/deletion
  Segment size: 1 GB (roll on size or time, whichever first)
  
  Lifecycle:
    Active → Sealed → (after retention) → Deleted
    
    Compaction (for queues with many deletes):
      - Background: scan sealed segments
      - Skip deleted/expired messages
      - Write live messages to new compact segment
      - Replace old segments atomically

Write optimization:
  - Buffer writes in memory (64 KB page)
  - Group commit: fsync every 1ms (batch many messages in one syscall)
  - Direct I/O: bypass page cache for writes (we manage our own cache)
  - Aligned writes: 4 KB alignment for NVMe efficiency
  
Read optimization:
  - mmap for reads: OS page cache handles caching
  - Prefetch: sequential read ahead for batch receive
  - Index: sparse index every 4 KB for O(1) seek to message
```

## 9. Component Optimization

### 9.1 Batching & Throughput
```
Producer batching:
  - Client SDK buffers messages (up to 10 or 64 KB or 50ms)
  - Sends as single batch request
  - Reduces network round-trips by 10x
  - Server processes batch atomically (all or nothing per partition)

Broker-side batching:
  - Group commit: accumulate writes for 1ms, then single fsync
  - At 10M msg/sec: each fsync commits ~10,000 messages
  - Fsync cost: ~50μs on NVMe → 20,000 fsync/sec possible
  - Effective per-message cost: 50μs / 10,000 = 5 nanoseconds amortized

Consumer batching:
  - ReceiveMessages with max=10: single network call, 10 messages
  - Batch acknowledge: delete up to 10 messages in one call
  - Prefetch: client SDK fetches next batch while processing current
```

### 9.2 Long Polling Implementation
```
Problem: Without long polling, consumers poll every 100ms = 10 req/sec × 50K consumers = 500K wasted requests/sec

Solution: Server-side wait with epoll

Implementation:
  per partition:
    wait_queue: LinkedList<WaitingConsumer>
    
  on ReceiveMessages(wait_time=20s):
    messages = tryFetch()
    if messages.empty() and wait_time > 0:
      waiter = new WaitingConsumer(connection, filter, deadline=now+wait_time)
      partition.wait_queue.push(waiter)
      // Connection held open, no response yet
    
  on message_appended(partition):
    while partition.wait_queue.not_empty():
      waiter = partition.wait_queue.pop()
      if waiter.deadline > now:
        messages = fetchForWaiter(waiter.filter)
        if messages.not_empty():
          waiter.respond(messages)
          break
      else:
        waiter.respond(empty)  // Timed out
        
Benefits:
  - Zero wasted requests when queue is empty
  - Immediate delivery when message arrives (no polling delay)
  - Server holds connection cheaply (epoll: 1000s of connections per thread)
```

### 9.3 Partition Auto-Scaling
```
Scale-out trigger:
  - Partition throughput > 1000 msg/sec sustained for 5 min
  - Consumer lag > 100,000 messages for 5 min
  - Write latency p99 > 50ms sustained

Split partition:
  1. Create 2 new partitions on different brokers
  2. Stop writes to old partition (brief pause: < 100ms)
  3. Assign message groups to new partitions (consistent hash)
  4. Resume writes to new partitions
  5. Old partition drains (consumers finish processing, then deleted)

Scale-in trigger:
  - Partition throughput < 10 msg/sec for 1 hour
  - Very few active message groups

Merge partitions:
  1. Stop writes to both partitions
  2. Merge remaining messages into single new partition
  3. Resume writes to merged partition
  4. Delete old partitions

Auto-scaling policy:
  - Min partitions: 1 per queue
  - Max partitions: 1000 per queue
  - Scale step: 2x (1 → 2 → 4 → 8 → ...)
  - Cooldown: 10 minutes between scaling events
```

### 9.4 Message Filtering at Broker
```
Filter policy (set by consumer):
{
    "event_type": ["order.created", "order.updated"],
    "priority": [{"numeric": [">=", 3]}],
    "region": [{"prefix": "us-"}]
}

Filter evaluation (per message):
  - String exact match: O(1) hash lookup
  - Numeric comparison: O(1)
  - Prefix match: O(prefix_length)
  - AND logic between attributes, OR logic within attribute values

Optimization:
  - Compile filter to bytecode on consumer registration
  - Evaluate at broker (don't transfer filtered-out messages)
  - For high-selectivity filters (< 10% pass): significant bandwidth savings
  - Bloom filter pre-check on attribute values for fast rejection
```

### 9.5 Exactly-Once Processing (Deduplication + Idempotent Consumer)
```
Producer-side deduplication:
  - message_deduplication_id (explicit) or content hash (content-based)
  - Window: 5 minutes
  - If duplicate detected: return success (same message_id as original)
  - Implementation: per-partition dedup cache (bloom filter + LRU)

Consumer-side exactly-once:
  Approach 1: Idempotent processing
    - Consumer tracks processed message IDs in database
    - On receive: check if already processed → skip if yes
    - Combine: process + mark as processed in same transaction

  Approach 2: Transactional outbox
    - Process message within database transaction
    - Write "processed" marker in same transaction
    - If crash before ack: message redelivered, duplicate detected by marker

  Approach 3: Idempotency keys
    - Consumer generates idempotency key per message
    - Downstream services reject duplicate idempotency keys
    - At-least-once delivery + idempotent consumers = effectively exactly-once
```

## 10. Observability

### 10.1 Metrics
```yaml
# Queue-level metrics
queue_messages_sent_total{queue, status}                    # Counter
queue_messages_received_total{queue}                        # Counter
queue_messages_deleted_total{queue}                         # Counter
queue_messages_visible{queue}                               # Gauge (available to receive)
queue_messages_not_visible{queue}                           # Gauge (in-flight)
queue_messages_delayed{queue}                               # Gauge
queue_oldest_message_age_seconds{queue}                     # Gauge (consumer lag indicator)
queue_message_size_bytes{queue}                             # Histogram

# Operation metrics
queue_send_latency_seconds{queue}                           # Histogram
queue_receive_latency_seconds{queue}                        # Histogram
queue_delete_latency_seconds{queue}                         # Histogram
queue_empty_receives_total{queue}                           # Counter (no messages available)
queue_throttled_requests_total{queue, operation}            # Counter

# DLQ metrics
queue_dlq_messages_total{source_queue, dlq}                # Counter
queue_dlq_depth{dlq}                                       # Gauge
queue_redrive_total{source_queue}                           # Counter

# Broker metrics
broker_partitions_leading{broker}                           # Gauge
broker_partitions_following{broker}                         # Gauge
broker_disk_usage_bytes{broker}                             # Gauge
broker_write_throughput_bytes{broker}                       # Gauge
broker_replication_lag_bytes{broker, partition}             # Gauge
broker_fsync_latency_seconds{broker}                        # Histogram
broker_segment_count{broker, partition}                     # Gauge

# Consumer metrics
queue_consumer_count{queue}                                 # Gauge
queue_consumer_processing_time_seconds{queue, consumer}    # Histogram
queue_visibility_timeout_extensions_total{queue}            # Counter
queue_message_redeliveries_total{queue}                    # Counter (visibility timeouts)

# System metrics
cluster_total_messages                                     # Gauge
cluster_total_throughput_messages_per_sec                   # Gauge
cluster_storage_used_bytes                                  # Gauge
```

### 10.2 Alerting
```yaml
# Critical
- alert: QueueProcessingStalled
  expr: queue_oldest_message_age_seconds > 3600
  for: 5m
  severity: critical
  description: "Queue {{ $labels.queue }} has messages older than 1 hour"

- alert: DLQGrowing
  expr: rate(queue_dlq_messages_total[5m]) > 10
  for: 5m
  severity: critical
  description: "DLQ receiving > 10 messages/min for {{ $labels.source_queue }}"

- alert: BrokerDiskFull
  expr: broker_disk_usage_bytes / broker_disk_capacity_bytes > 0.9
  for: 10m
  severity: critical

- alert: ReplicationLagHigh
  expr: broker_replication_lag_bytes > 104857600
  for: 2m
  severity: critical
  description: "Replication lag > 100MB, risk of data loss on leader failure"

# Warning
- alert: HighRedeliveryRate
  expr: rate(queue_message_redeliveries_total[10m]) / rate(queue_messages_received_total[10m]) > 0.1
  for: 10m
  severity: warning
  description: "> 10% messages being redelivered (consumer failures)"

- alert: EmptyReceivesHigh
  expr: rate(queue_empty_receives_total[5m]) > 100
  for: 10m
  severity: warning
  description: "High empty receive rate (consider long polling)"
```

### 10.3 Dashboards
```
Dashboard 1: Queue Overview
- Messages in queue (visible + not visible + delayed)
- Send/Receive/Delete throughput
- Oldest message age
- DLQ depth
- Consumer count

Dashboard 2: Consumer Health
- Processing latency per consumer
- Redelivery rate
- Visibility timeout extensions
- Error rate
- Consumer lag

Dashboard 3: Broker Cluster
- Partition distribution
- Disk usage per broker
- Replication lag
- Fsync latency
- Network throughput

Dashboard 4: Operations
- Partition splits/merges
- Failover events
- Throttling events
- Storage growth forecast
```

## 11. Considerations and Assumptions

### Assumptions
1. **At-least-once delivery**: Standard guarantee; exactly-once requires idempotent consumers
2. **No message ordering across partitions**: Only FIFO within message group
3. **Pull-based consumption**: Consumers pull (with long polling); not server-push
4. **Message size limit**: 256 KB in queue; larger payloads use claim-check (S3 reference)
5. **Multi-AZ deployment**: All data replicated across 3 AZs for durability
6. **Network**: Clients in same region as queue cluster (cross-region adds latency)
7. **Retention-based cleanup**: Messages auto-deleted after retention period

### Design Decisions

| Decision | Chosen | Alternative | Rationale |
|----------|--------|-------------|-----------|
| Storage | Append-only log on NVMe | B-Tree (RocksDB for everything) | Sequential writes optimal for high throughput |
| Replication | Raft (synchronous majority) | Async replication | Durability guarantee (no acked message loss) |
| Visibility tracking | In-memory + WAL | Database table | Sub-ms operations, crash-safe with WAL |
| Delay scheduling | Hierarchical timer wheel | Sorted set / priority queue | O(1) insert, efficient for millions of timers |
| Deduplication | Bloom filter + LRU | Redis external store | Self-contained, no external dependency |
| Partitioning | Fixed partitions per queue (auto-split) | Consistent hashing | Simpler management, easier to reason about ordering |
| Protocol | HTTP/2 (public) + gRPC (internal) | Custom binary protocol | Standard, good tooling, efficient with HTTP/2 |

### Trade-offs

| Trade-off | Benefit | Cost |
|-----------|---------|------|
| At-least-once vs exactly-once | Simpler implementation, higher throughput | Consumer must handle duplicates |
| Pull vs Push | Consumer controls rate, no overload | Slightly higher latency (mitigated by long poll) |
| Visibility timeout vs transactions | Simple, no distributed transactions | Message may be processed twice on timeout |
| Raft replication | Strong durability | Higher write latency (wait for majority) |
| Fixed partitions vs dynamic | Predictable performance | Need manual/auto scaling for hot queues |
| In-memory visibility tracking | Fast operations | Memory proportional to in-flight messages |
| Message retention vs delete-on-ack | Replay possible, debugging easier | More storage used |

### Failure Modes

| Failure | Impact | Recovery |
|---------|--------|----------|
| Broker leader crash | ~500ms unavailability for affected partitions | Raft election promotes follower; no data loss |
| Consumer crash mid-processing | Message stuck until visibility timeout | Timeout expires → message redelivered to another consumer |
| Network partition (client ↔ broker) | Client can't send/receive | Retry with backoff; messages safe on broker |
| Disk failure | Partition data on that disk unavailable | Replica takes over; replace disk, resync |
| Slow consumer | Messages accumulate, age increases | Auto-scale consumers; alert on old messages |
| Poison message (always fails) | Consumer keeps retrying | After maxReceiveCount: move to DLQ, stop retrying |
| Clock skew between nodes | Delay/visibility timing inaccuracy | NTP synchronization; use logical clocks for ordering |
| Split-brain | Risk of duplicate message delivery | Raft quorum prevents; partitions minority become read-only |
