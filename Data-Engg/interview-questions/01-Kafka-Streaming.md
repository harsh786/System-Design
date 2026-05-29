# Interview Questions Set 1: Apache Kafka & Event Streaming (Q1-30)

---

## Q1: Explain Kafka's storage architecture. How does a partition physically store data?

**Answer:**
Each partition is a directory on the broker's filesystem containing:
- **Segment files** (.log): Append-only files, default 1GB each. Named by base offset (e.g., `00000000000000000000.log`)
- **Index files** (.index): Sparse offset → physical position mapping (every 4KB of data)
- **Timeindex files** (.timeindex): Timestamp → offset mapping for time-based lookups
- **Leader epoch checkpoint**: Tracks leader changes for consistency

```
/kafka-logs/orders-0/
├── 00000000000000000000.log      (segment: offsets 0-15232)
├── 00000000000000000000.index
├── 00000000000000000000.timeindex
├── 00000000000000015233.log      (segment: offsets 15233-current)
├── 00000000000000015233.index
├── 00000000000000015233.timeindex
└── leader-epoch-checkpoint
```

**Key insight:** Messages are NEVER deleted individually. Entire segments are deleted when retention policy triggers (time/size). This is why Kafka is so fast—sequential I/O only.

---

## Q2: What happens when a Kafka consumer group rebalances? What are the problems and solutions?

**Answer:**
**Trigger:** Consumer joins/leaves group, topic partition count changes, or heartbeat timeout.

**Stop-the-World rebalance (Eager protocol):**
1. All consumers revoke ALL partitions
2. JoinGroup request to coordinator
3. Leader consumer assigns partitions (Range/RoundRobin/Sticky)
4. SyncGroup distributes assignments
5. All consumers resume from last committed offset

**Problem:** Complete processing halt during rebalance (seconds to minutes).

**Solutions:**
- **Cooperative Sticky Assignor (Incremental Rebalance):** Only revoke partitions that need to move. Other partitions continue processing. Multiple rebalance rounds but no full stop.
- **Static Group Membership:** Set `group.instance.id`. Consumer gets same partitions back after restart (within `session.timeout.ms`). No rebalance on restart.
- **Tune timeouts:** `session.timeout.ms=45000`, `heartbeat.interval.ms=15000`, `max.poll.interval.ms=300000`

---

## Q3: How does Kafka achieve exactly-once semantics (EOS)? Explain the mechanism.

**Answer:**
Three mechanisms combined:

**1. Idempotent Producer (within partition):**
- Producer gets `ProducerID` (PID) from broker
- Each message has sequence number per partition
- Broker deduplicates: if seq ≤ last committed → reject silently
- Handles retries without duplicates

**2. Transactional Producer (across partitions):**
```java
producer.initTransactions();
producer.beginTransaction();
producer.send(record1);  // partition 0
producer.send(record2);  // partition 1
producer.sendOffsetsToTransaction(offsets, consumerGroupId);
producer.commitTransaction();  // atomic: all or nothing
```
- Uses internal `__transaction_state` topic
- Two-phase commit: PREPARE → COMMIT/ABORT
- Transaction coordinator manages state

**3. Consumer `isolation.level=read_committed`:**
- Consumer only sees committed transactional messages
- Uncommitted/aborted messages are skipped

**End-to-end flow:** Read from input topic → Process → Write to output topic + Commit input offset → All in ONE transaction.

---

## Q4: Your Kafka cluster has 100 partitions with replication factor 3. A broker dies. Walk through what happens.

**Answer:**
1. **Detection (10-30s):** Controller detects missing heartbeat/ZK session (or KRaft raft timeout)
2. **ISR update:** Dead broker removed from ISR of all partitions it hosted
3. **Leader election:** For partitions where dead broker was leader:
   - Controller picks new leader from ISR (first replica in ISR list, `unclean.leader.election.enable=false`)
   - ~33 partitions need new leader (100 × 1/3 brokers)
   - LeaderAndIsr requests sent to new leaders
4. **Metadata propagation:** UpdateMetadata to all brokers
5. **Under-replicated partitions:** All partitions that had a replica on dead broker are now under-replicated (URP)
6. **Producer impact:** Producers to affected partitions get `NOT_LEADER` error, refresh metadata, retry to new leader (transparent with retries)
7. **Consumer impact:** Consumers fetch from new leader automatically
8. **Recovery:** When broker returns, replicas catch up from leader (fetch from last HW), rejoin ISR

**Time to full recovery:** Leader election: <1s. Replica catch-up: minutes to hours depending on lag.

---

## Q5: How do you handle ordering guarantees when you need to scale consumers?

**Answer:**
**Problem:** Kafka guarantees ordering only within a partition. More consumers = need more partitions = ordering only per partition.

**Strategies:**
1. **Partition by ordering key:** All events for same entity go to same partition
   ```
   producer.send(new ProducerRecord("orders", customerId, orderEvent));
   // customerId is the key → same partition → ordered per customer
   ```

2. **When one partition isn't enough for throughput:**
   - Use application-level sequencing (sequence numbers in payload)
   - Buffer and reorder on consumer side within a window
   - Use Kafka Streams with key-based repartitioning

3. **Global ordering (single partition):** Only option for strict global order. Throughput limited to single partition (~10-50 MB/s).

4. **Event sourcing pattern:** Include version/sequence in event. Consumer detects gaps, requests replay.

---

## Q6: Explain consumer lag. How do you monitor it and what are the causes of increasing lag?

**Answer:**
**Consumer lag** = Latest partition offset - Consumer's committed offset = messages not yet processed.

**Monitoring:**
```
# Kafka CLI
kafka-consumer-groups.sh --describe --group my-group

# Metrics (JMX)
kafka.consumer:type=consumer-fetch-manager-metrics,client-id=*
  records-lag-max    # Max lag across partitions
  records-lag-avg    # Average lag

# External: Burrow (LinkedIn), Kafka Exporter + Prometheus
```

**Causes of increasing lag:**
1. **Slow processing:** Consumer processing time > production rate
2. **Consumer rebalances:** Processing stops during rebalance
3. **GC pauses:** Long JVM pauses stall consumer
4. **External dependency:** Database/API calls slowing consumer
5. **Data skew:** One partition has disproportionate data
6. **Under-provisioned:** Not enough consumer instances
7. **max.poll.records too high:** Large batches + slow processing → poll timeout → rebalance → more lag

**Solutions:**
- Scale consumers (up to partition count)
- Increase `max.poll.interval.ms` if processing is legitimately slow
- Parallelize within consumer (partition-level thread pool)
- Reduce `max.poll.records` for more frequent commits
- Fix data skew (better partitioning strategy)

---

## Q7: Design a multi-datacenter Kafka deployment. What are the trade-offs?

**Answer:**

**Option 1: Active-Passive (MirrorMaker 2 / Cluster Linking)**
```
DC1 (Active)              DC2 (Passive)
┌──────────┐   MM2/CL    ┌──────────┐
│  Kafka   │────────────▶│  Kafka   │
│ Cluster  │  async      │ Cluster  │
│          │  replication │ (standby)│
└──────────┘              └──────────┘
```
- Pro: Simple, no cross-DC latency for producers
- Con: RPO > 0 (data loss on failover), offset translation needed

**Option 2: Active-Active (each DC produces locally)**
```
DC1                       DC2
┌──────────┐   MM2 bidi  ┌──────────┐
│  Kafka   │◀───────────▶│  Kafka   │
│ Cluster  │              │ Cluster  │
└──────────┘              └──────────┘
```
- Pro: Local latency for all producers, high availability
- Con: Conflict resolution, duplicate detection, topic naming (prefixes)

**Option 3: Stretch Cluster (single cluster across DCs)**
- `min.insync.replicas=2`, replicas in both DCs
- Pro: Strong consistency, simple topology
- Con: Cross-DC latency on every produce (RTT added), requires low-latency link (<10ms)

**Trade-offs:** Consistency vs Latency vs Availability (CAP applied to Kafka).

---

## Q8: What is ISR (In-Sync Replicas) and how does it relate to data durability?

**Answer:**
**ISR** = Set of replicas that are "caught up" to the leader within `replica.lag.time.max.ms` (default 30s).

**How ISR works:**
- Follower fetches from leader continuously
- If follower falls behind by > `replica.lag.time.max.ms` → removed from ISR
- When caught up again → added back to ISR

**Durability configuration:**
```properties
# Broker level
min.insync.replicas=2        # At least 2 replicas must ack
default.replication.factor=3  # 3 total copies

# Producer level  
acks=all                     # Wait for ALL ISR replicas to ack
```

**Failure scenarios:**
- ISR=[0,1,2], `min.insync.replicas=2`, `acks=all`:
  - 1 broker dies → ISR=[0,1], produce succeeds (2 ≥ 2)
  - 2 brokers die → ISR=[0], produce FAILS (1 < 2) → `NotEnoughReplicasException`

**High Water Mark (HW):** Offset up to which ALL ISR replicas have replicated. Consumers only see up to HW. This prevents reading uncommitted data.

---

## Q9: How would you handle poison pill messages (messages that crash consumers)?

**Answer:**

**Dead Letter Queue (DLQ) pattern:**
```java
while (true) {
    records = consumer.poll(Duration.ofMillis(100));
    for (record : records) {
        try {
            process(record);
        } catch (Exception e) {
            if (retryCount(record) < MAX_RETRIES) {
                producer.send(new ProducerRecord("orders-retry", record.key(), 
                    addRetryHeader(record)));
            } else {
                producer.send(new ProducerRecord("orders-dlq", record.key(), 
                    record.value()));  // Send to DLQ
                log.error("Poison pill sent to DLQ: {}", record.offset());
            }
        }
    }
    consumer.commitSync();
}
```

**Strategies:**
1. **DLQ:** Move to dead letter topic after N retries. Human review.
2. **Skip and log:** Skip bad message, alert, continue processing.
3. **Schema validation:** Validate before processing. Reject malformed at gate.
4. **Retry topic with backoff:** `orders-retry-1` (1min), `orders-retry-2` (5min), `orders-retry-3` (30min), then DLQ.
5. **Circuit breaker:** If error rate > threshold, pause consumer, alert.

---

## Q10: Explain Kafka Streams vs Flink for stream processing. When would you choose each?

**Answer:**

| Aspect | Kafka Streams | Flink |
|--------|--------------|-------|
| Deployment | Library (runs in your app) | Cluster (JobManager + TaskManagers) |
| Source/Sink | Kafka only | Any (Kafka, files, DBs, custom) |
| Scaling | Add app instances | Adjust parallelism |
| State | RocksDB (local) | RocksDB (managed) |
| Checkpointing | Changelog topics | Distributed snapshots |
| Exactly-once | Within Kafka ecosystem | Across any sink (2PC) |
| Event time | Yes (limited) | Yes (advanced watermarks) |
| Complexity | Low (just a library) | High (cluster ops) |
| Latency | Very low (ms) | Low (ms-s) |
| Windows | Session, tumbling, hopping, sliding | All + custom windows |
| SQL | ksqlDB (separate) | Built-in Table API/SQL |

**Choose Kafka Streams when:**
- Source and sink are both Kafka
- Simple transformations, aggregations, joins
- Want library deployment (no cluster to manage)
- Team already runs microservices on K8s

**Choose Flink when:**
- Complex event processing (CEP patterns)
- Multiple sources/sinks beyond Kafka
- Advanced windowing, event-time processing
- Very large state (TB-scale)
- Need SQL interface for analysts

---

## Q11: How does log compaction work? When would you use it?

**Answer:**
**Log compaction** retains the LAST value for each key. Instead of deleting old segments by time/size, it removes older records with the same key, keeping only the latest.

```
Before compaction:
  offset 0: key=A, value=v1
  offset 1: key=B, value=v1
  offset 2: key=A, value=v2   ← newer A
  offset 3: key=A, value=v3   ← newest A
  offset 4: key=B, value=v2   ← newest B

After compaction:
  offset 3: key=A, value=v3   ← kept (latest)
  offset 4: key=B, value=v2   ← kept (latest)
```

**Tombstone:** key=A, value=null → Marks key for deletion. Kept for `delete.retention.ms` then removed.

**Configuration:**
```properties
cleanup.policy=compact              # or "compact,delete" for both
min.cleanable.dirty.ratio=0.5       # Trigger when 50% dirty
segment.ms=604800000                # Active segment never compacted
min.compaction.lag.ms=0             # Delay before eligible
```

**Use cases:**
- Changelog topics (Kafka Streams state stores)
- CDC (latest state of each row)
- Configuration distribution
- Cache invalidation
- User profile updates (latest profile per user_id)

---

## Q12: Your producer is getting `NotEnoughReplicasException`. Diagnose and fix.

**Answer:**

**Meaning:** `acks=all` and ISR count < `min.insync.replicas`.

**Diagnosis steps:**
```bash
# Check ISR for affected partitions
kafka-topics.sh --describe --topic orders --bootstrap-server broker:9092
# Look for: Isr: 0  (only leader, no followers in sync)

# Check broker health
kafka-broker-api-versions.sh --bootstrap-server broker1:9092,broker2:9092

# Check under-replicated partitions
kafka-topics.sh --describe --under-replicated-partitions

# Check broker logs for follower fetch issues
grep "replica.lag" /var/log/kafka/server.log
```

**Root causes:**
1. Broker(s) down → fewer replicas available
2. Follower too slow (network, disk I/O) → removed from ISR
3. Disk full on follower → can't write, falls out of ISR
4. GC pauses on follower → misses fetch deadline
5. Network partition between brokers

**Fixes:**
- Immediate: Reduce `min.insync.replicas` (trade durability for availability)
- Restart failed brokers
- Fix disk/network issues
- Increase `replica.lag.time.max.ms` if followers are slow but functional
- Long-term: Add brokers, fix infrastructure

---

## Q13: How do you size a Kafka cluster? Walk through capacity planning.

**Answer:**

**Inputs needed:**
- Peak write throughput (MB/s)
- Message size (avg, p99)
- Retention period
- Replication factor
- Consumer count and read patterns
- Latency requirements

**Calculation:**
```
Given:
  Peak ingest: 500 MB/s
  Replication factor: 3
  Retention: 7 days
  Consumers: 4 independent groups reading all data

Storage:
  Daily ingest: 500 MB/s × 86400s = 43.2 TB/day (raw)
  With replication: 43.2 × 3 = 129.6 TB/day
  7-day retention: 129.6 × 7 = 907 TB total storage
  With 20% overhead: ~1.1 PB

Network (per broker, 10 brokers):
  Write: 500/10 = 50 MB/s per broker (from producers)
  Replication: 50 × 2 = 100 MB/s (replicating to 2 followers)
  Read: 50 × 4 = 200 MB/s (4 consumer groups, pagecache hit)
  Total per broker: 50 + 100 + 200 = 350 MB/s → need 10Gbps NIC

Disk:
  Write: 50 MB/s per broker (sequential, SSD not required)
  JBOD recommended (multiple disks, no RAID)
  
Partitions:
  Target: 10-50 MB/s per partition
  500 MB/s ÷ 25 MB/s = 20 partitions minimum for throughput
  But consumer parallelism: if 50 consumers → 50 partitions minimum
  
Memory:
  Page cache for active segment reads
  Rule: 25-50% of data accessed in last 30s should fit in page cache
  Typically 32-64 GB RAM per broker
```

---

## Q14: Explain Kafka Connect. How do you ensure exactly-once delivery with Connect?

**Answer:**

**Architecture:**
- **Source Connectors:** External system → Kafka (e.g., Debezium for CDC, JDBC source)
- **Sink Connectors:** Kafka → External system (e.g., S3, Elasticsearch, JDBC sink)
- **Workers:** Distributed mode (multiple JVMs, task distribution via Connect protocol)
- **Converters:** Serialize/deserialize (Avro, JSON, Protobuf)
- **SMTs:** Single Message Transforms (route, filter, mask fields inline)

**Exactly-once for Source Connectors:**
```json
{
  "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
  "exactly.once.support": "required",
  "transaction.boundary": "poll"
}
```
- Source connector uses transactional producer internally
- Offset stored in same transaction as produced messages
- If task restarts, replays from last committed offset → no duplicates

**Exactly-once for Sink Connectors:**
- Depends on sink supporting idempotent writes:
  - S3: Write objects with deterministic names (offset-based) → re-upload = overwrite
  - Database: Use upsert (INSERT ON CONFLICT UPDATE)
  - Elasticsearch: Use document ID = Kafka offset

---

## Q15: How does KRaft (Kafka without ZooKeeper) work? What changes?

**Answer:**

**KRaft architecture:**
- Metadata managed by internal Raft quorum (no external ZooKeeper)
- Controller nodes form Raft group (typically 3 or 5)
- One active controller (Raft leader), others are followers
- Metadata stored in internal `__cluster_metadata` topic

**What changes:**
| Aspect | ZooKeeper mode | KRaft mode |
|--------|---------------|------------|
| Metadata store | ZK znodes | Internal Raft log |
| Controller election | ZK ephemeral node | Raft leader election |
| Broker registration | ZK ephemeral node | Heartbeats to controller |
| Partition leader election | Controller reads ZK | Controller from Raft log |
| Scalability | ~200K partitions | Millions of partitions |
| Operational | ZK + Kafka = 2 systems | Single system |
| Recovery time | Slow (read all ZK state) | Fast (Raft log replay) |

**Benefits:**
- Faster controller failover (seconds vs minutes)
- Simpler operations (no ZK cluster to manage)
- Better scalability (millions of partitions)
- Faster shutdown/startup

---

## Q16: What is the difference between `at-least-once`, `at-most-once`, and `exactly-once` in Kafka?

**Answer:**

**At-most-once (fire and forget):**
```properties
acks=0                    # Don't wait for broker ack
retries=0                 # Never retry
enable.auto.commit=true   # Commit before processing
```
- Message may be lost, never duplicated
- Use: Metrics, logs where loss is acceptable

**At-least-once (default):**
```properties
acks=all
retries=MAX_INT
enable.auto.commit=false  # Commit after processing
```
- Message never lost, may be duplicated
- Use: Most workloads (with idempotent consumers)

**Exactly-once:**
```properties
acks=all
enable.idempotence=true
transactional.id=my-app-1
isolation.level=read_committed  # Consumer side
```
- Message never lost, never duplicated
- Use: Financial, billing, state machines
- Cost: ~3-10% throughput overhead

---

## Q17: How do you handle schema evolution in Kafka with Avro/Protobuf?

**Answer:**

**Schema Registry workflow:**
1. Producer registers schema (or validates against registered)
2. Schema Registry checks compatibility against previous versions
3. If compatible → assigned schema ID; if not → HTTP 409 error
4. Producer serializes with schema, prepends 5-byte header: [0x00][schema_id_4bytes]
5. Consumer reads schema ID from header, fetches schema from registry, deserializes

**Compatibility modes:**
```
BACKWARD (default): New schema can read data written with old schema
  ✓ Add field WITH default
  ✓ Remove field
  ✗ Add required field without default

FORWARD: Old schema can read data written with new schema
  ✓ Remove field WITH default
  ✓ Add field
  ✗ Remove required field without default

FULL: Both backward and forward
  ✓ Add field with default
  ✓ Remove field with default

NONE: No check (dangerous)
```

**Best practice:** Use FULL compatibility. All new fields have defaults. Never remove fields without defaults.

---

## Q18: Explain the difference between Kafka's `__consumer_offsets` topic and external offset storage.

**Answer:**

**`__consumer_offsets` (default):**
- Internal compacted topic (50 partitions by default)
- Stores: `(group, topic, partition) → offset`
- Managed by Group Coordinator (broker hosting the partition)
- Committed via `commitSync()`/`commitAsync()`

**External offset storage (manual):**
- Store offsets in application's database/state store
- Use `consumer.seek()` on startup to resume from stored offset
- Enables exactly-once with external systems:

```java
// Consume + process + store offset in SAME DB transaction
consumer.subscribe(topics, new ConsumerRebalanceListener() {
    onPartitionsAssigned(partitions) {
        for (p : partitions) {
            long offset = db.getOffset(p);  // Read from DB
            consumer.seek(p, offset);
        }
    }
});

while (true) {
    records = consumer.poll(100);
    db.beginTransaction();
    for (record : records) {
        db.insert(record);
        db.saveOffset(record.partition(), record.offset() + 1);
    }
    db.commit();  // Atomic: data + offset in same transaction
    // DO NOT call consumer.commitSync() — offset is in DB
}
```

---

## Q19: How do you implement event sourcing with Kafka?

**Answer:**

**Event sourcing:** Store state as a sequence of immutable events rather than current state.

```
Topic: accounts (compaction disabled, infinite retention)

Key: account-123
Events:
  offset 0: {type: "AccountCreated", balance: 0}
  offset 1: {type: "Deposited", amount: 1000}
  offset 2: {type: "Withdrawn", amount: 200}
  offset 3: {type: "Deposited", amount: 500}

Current state (derived by replaying): balance = 0 + 1000 - 200 + 500 = 1300
```

**Architecture:**
```
Command → Validate → Event → Kafka → Consumers (Projections)
                                         │
                                         ├─ Read model (query DB)
                                         ├─ Notifications
                                         └─ Analytics
```

**Kafka fits because:**
- Immutable append-only log = event store
- Retention: keep forever (or very long)
- Replay: consumer can seek to offset 0 and rebuild state
- Multiple consumers: different projections from same events

**Challenges:**
- Event schema evolution (all historical events must remain readable)
- Snapshotting (don't replay millions of events on every startup)
- Ordering (single partition per aggregate for ordering guarantee)

---

## Q20: Your Kafka cluster has 500 topics × 100 partitions = 50,000 partitions. What problems arise?

**Answer:**

**Problems:**
1. **Controller bottleneck:** Controller manages all partition metadata. Failover requires loading all 50K partition states.
2. **ZooKeeper pressure:** 50K znodes for partition state (KRaft handles this better).
3. **Leader election storm:** If a broker with 5000 leader partitions dies → 5000 leader elections simultaneously.
4. **Increased end-to-end latency:** More partitions = more metadata requests, more file handles.
5. **Consumer rebalance time:** Rebalancing 50K partitions across consumers takes longer.
6. **File descriptors:** Each partition has segment files. 50K partitions × 2 segments avg = 100K+ file handles.

**Mitigations:**
- KRaft: Handles millions of partitions (vs ZK limit ~200K)
- Fewer partitions per topic (do you REALLY need 100?)
- Partition count = MAX(throughput_requirement / partition_throughput, consumer_parallelism)
- Use tiered storage to reduce active segments
- Increase `controlled.shutdown.max.retries` for graceful migration
- Consider topic namespacing (fewer topics with more keys)

---

## Q21: How do you implement a dead letter queue pattern in a Kafka streaming application?

**Answer:**

```java
// Kafka Streams DLQ with branching
StreamsBuilder builder = new StreamsBuilder();
KStream<String, Order> orders = builder.stream("orders");

// Branch: valid vs invalid
KStream<String, Order>[] branches = orders.branch(
    (key, value) -> isValid(value),    // Branch 0: valid
    (key, value) -> true               // Branch 1: invalid (catch-all)
);

// Process valid orders
branches[0]
    .mapValues(this::enrichOrder)
    .to("orders-enriched");

// Route invalid to DLQ with error metadata
branches[1]
    .mapValues(order -> DlqRecord.builder()
        .originalPayload(order)
        .errorReason(getValidationError(order))
        .timestamp(Instant.now())
        .sourceTopic("orders")
        .build())
    .to("orders-dlq");
```

**DLQ management:**
- Monitor DLQ topic lag (should be near 0 if fixed quickly)
- Build DLQ UI for human review/replay
- Auto-retry: Consumer on DLQ attempts reprocessing after delay
- Alerting: New messages in DLQ → PagerDuty/Slack

---

## Q22: Explain consumer group protocol. What is the difference between group leader and group coordinator?

**Answer:**

**Group Coordinator (Broker-side):**
- A broker designated to manage a consumer group
- Determined by: `hash(group.id) % __consumer_offsets partitions`
- Responsibilities: Manage group membership, trigger rebalances, store offsets

**Group Leader (Consumer-side):**
- First consumer to join the group becomes leader
- Receives full list of members + their subscriptions
- Runs partition assignment strategy (Range, RoundRobin, Sticky, Cooperative)
- Sends assignment back to coordinator, which distributes to all members

**Protocol flow:**
```
Consumer → FindCoordinator → Coordinator (broker)
Consumer → JoinGroup → Coordinator
           Coordinator → selects Leader
Leader   → SyncGroup(assignments) → Coordinator
           Coordinator → SyncGroup(my assignment) → each Consumer
Consumer → Heartbeat (periodic) → Coordinator
Consumer → OffsetCommit → Coordinator
```

---

## Q23: How do you implement rate limiting in Kafka consumers?

**Answer:**

**Approach 1: Broker-side quotas**
```properties
# Per client-id quota
kafka-configs.sh --alter --add-config 'consumer_byte_rate=10485760' \
  --entity-type clients --entity-name my-consumer
# Limits consumer to 10 MB/s fetch rate
```

**Approach 2: Application-level with pause/resume**
```java
while (true) {
    records = consumer.poll(Duration.ofMillis(100));
    for (record : records) {
        rateLimiter.acquire();  // Guava RateLimiter, blocks if over limit
        process(record);
    }
}

// Or: pause partitions when backpressure detected
if (processingQueue.size() > HIGH_WATERMARK) {
    consumer.pause(consumer.assignment());
}
if (processingQueue.size() < LOW_WATERMARK) {
    consumer.resume(consumer.assignment());
}
```

**Approach 3: max.poll.records + poll interval**
```properties
max.poll.records=100          # Process 100 at a time
fetch.max.bytes=1048576       # Max 1 MB per fetch
```

---

## Q24: How does Kafka handle backpressure?

**Answer:**

**Kafka's inherent backpressure mechanism:**
Kafka is a PULL-based system. Consumers pull at their own pace. If consumer is slow:
- Messages buffer in Kafka (that's what retention is for)
- Consumer lag increases (monitored, alerted)
- No broker pressure (broker doesn't push)

**Producer-side backpressure:**
```properties
buffer.memory=33554432        # 32 MB producer buffer
max.block.ms=60000            # Block send() if buffer full (60s)
linger.ms=5                   # Batch for 5ms before sending
batch.size=16384              # Batch up to 16KB
```
If broker is slow → producer buffer fills → `send()` blocks → natural backpressure to application.

**Kafka Streams backpressure:**
- No explicit backpressure mechanism
- If processing is slow → `max.poll.interval.ms` exceeded → rebalance
- Solution: Increase poll interval, reduce `max.poll.records`, scale instances

**Comparison with push-based systems:**
- Flink: Backpressure propagates through operator chain (credit-based flow control)
- Kafka: Lag-based (pull at your pace, monitor lag)

---

## Q25: Design a Kafka-based CDC pipeline from PostgreSQL to a data lake.

**Answer:**

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│PostgreSQL│───▶│Debezium  │───▶│  Kafka   │───▶│ Flink/   │───▶ S3/Lake
│          │    │(Connect) │    │          │    │ Spark    │
│  WAL     │    │          │    │ CDC topic│    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘

Configuration (Debezium PostgreSQL connector):
{
  "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
  "database.hostname": "pg-primary",
  "database.port": "5432",
  "database.dbname": "orders_db",
  "database.server.name": "pg-orders",
  "table.include.list": "public.orders,public.customers",
  "plugin.name": "pgoutput",
  "slot.name": "debezium_slot",
  "publication.name": "dbz_publication",
  "snapshot.mode": "initial",
  "transforms": "route",
  "transforms.route.type": "io.debezium.transforms.ByLogicalTableRouter",
  "transforms.route.topic.regex": "(.*)\\.(.*)",
  "transforms.route.topic.replacement": "cdc.$2",
  "key.converter": "io.confluent.connect.avro.AvroConverter",
  "value.converter": "io.confluent.connect.avro.AvroConverter"
}
```

**CDC event structure:**
```json
{
  "before": {"id": 1, "amount": 100, "status": "CREATED"},
  "after":  {"id": 1, "amount": 100, "status": "SHIPPED"},
  "source": {"version": "2.4", "ts_ms": 1706000000000, "lsn": 12345},
  "op": "u",  // c=create, u=update, d=delete, r=read(snapshot)
  "ts_ms": 1706000000100
}
```

**Sink to data lake:**
- Flink CDC connector → Iceberg table (upsert mode)
- Or: Kafka Connect S3 Sink → Parquet files → Spark merge

---

## Q26: What are the common Kafka performance tuning parameters?

**Answer:**

**Producer tuning:**
```properties
# Throughput
batch.size=65536              # 64KB batches (up from 16KB default)
linger.ms=10                  # Wait 10ms to fill batch
compression.type=lz4          # or zstd for better ratio
buffer.memory=67108864        # 64MB buffer

# Reliability
acks=all
retries=2147483647
delivery.timeout.ms=120000
max.in.flight.requests.per.connection=5  # With idempotence=true

# Latency
linger.ms=0                   # Send immediately (sacrifice throughput)
```

**Consumer tuning:**
```properties
# Throughput
fetch.min.bytes=1048576       # Wait for 1MB before returning
fetch.max.wait.ms=500         # Or 500ms, whichever first
max.poll.records=1000         # Process 1000 records per poll
max.partition.fetch.bytes=1048576

# Reliability
enable.auto.commit=false      # Manual commit
auto.offset.reset=earliest    # Start from beginning if no offset
```

**Broker tuning:**
```properties
num.network.threads=8         # Network I/O threads
num.io.threads=16             # Disk I/O threads
socket.send.buffer.bytes=102400
socket.receive.buffer.bytes=102400
num.replica.fetchers=4        # Parallel replication
log.flush.interval.messages=10000  # Flush every 10K (OS page cache handles durability)
```

---

## Q27: How do you handle message ordering with retries enabled?

**Answer:**

**Problem:** With `retries > 0` and `max.in.flight.requests.per.connection > 1`:
```
Batch 1 (offset 0-4) → sent → FAILS
Batch 2 (offset 5-9) → sent → SUCCEEDS
Batch 1 retried      → sent → SUCCEEDS
Result: offsets on broker = [5,6,7,8,9,0,1,2,3,4] → OUT OF ORDER!
```

**Solutions:**

1. **Idempotent producer (recommended):**
```properties
enable.idempotence=true
# Automatically sets max.in.flight.requests.per.connection=5
# Broker reorders by sequence number → ordering guaranteed
```

2. **Limit in-flight (legacy):**
```properties
max.in.flight.requests.per.connection=1
# Only 1 batch in flight → no reordering possible
# Cost: ~50% throughput reduction
```

3. **Transactional producer:**
```properties
transactional.id=my-producer-1
# Implies idempotence, adds cross-partition atomicity
```

---

## Q28: Explain Kafka tiered storage. Why is it important?

**Answer:**

**Problem:** Kafka stores all data on broker local disks. Long retention = massive disk costs. Adding storage means adding brokers (expensive).

**Tiered storage (KIP-405, Kafka 3.6+):**
```
┌─────────────────────────────────────────────────┐
│ LOCAL TIER (broker disk):                       │
│   Hot data (last few hours/days)                │
│   Fast access, low latency                      │
│   Active segment always local                   │
└────────────────────┬────────────────────────────┘
                     │ offload old segments
                     ▼
┌─────────────────────────────────────────────────┐
│ REMOTE TIER (S3, GCS, ADLS, HDFS):             │
│   Cold data (days to years)                     │
│   Cheap storage                                 │
│   Higher latency for fetch                      │
│   Segments copied with index/timeindex          │
└─────────────────────────────────────────────────┘
```

**Benefits:**
- Decouple storage from compute (add retention without adding brokers)
- 10x cost reduction for long retention (S3 ≈ $0.023/GB vs EBS ≈ $0.10/GB)
- Faster broker recovery (less local data to replicate)
- Infinite retention feasible

**Configuration:**
```properties
remote.log.storage.system.enable=true
remote.log.storage.manager.class.name=org.apache.kafka.server.log.remote.storage.S3RemoteLogStorageManager
remote.log.metadata.manager.class.name=...
log.local.retention.ms=86400000   # Keep 1 day locally
log.retention.ms=2592000000       # Total retention: 30 days (remote)
```

---

## Q29: How do you migrate a Kafka topic to a different cluster with zero downtime?

**Answer:**

**Strategy: MirrorMaker 2 (MM2) migration:**

```
Phase 1: Setup replication
┌──────────┐    MM2     ┌──────────┐
│ Old      │───────────▶│ New      │
│ Cluster  │  replicate │ Cluster  │
│          │  topics    │          │
└──────────┘            └──────────┘
  ↑ Producers             
  ↓ Consumers             

Phase 2: Move consumers (one group at a time)
┌──────────┐    MM2     ┌──────────┐
│ Old      │───────────▶│ New      │
│ Cluster  │            │ Cluster  │
└──────────┘            └──────────┘
  ↑ Producers           ↓ Consumers (moved)
  
Phase 3: Move producers
┌──────────┐    MM2     ┌──────────┐
│ Old      │───────────▶│ New      │
│ Cluster  │            │ Cluster  │
└──────────┘            └──────────┘
                        ↑ Producers (moved)
                        ↓ Consumers

Phase 4: Decommission old, stop MM2
```

**Key considerations:**
- MM2 translates offsets (source offset → target offset mapping)
- Use `MirrorCheckpointConnector` for offset sync
- Consumer groups can switch using translated offsets (no reprocessing)
- Test with non-critical topics first
- Monitor replication lag before cutover

---

## Q30: Design a Kafka-based event-driven microservices architecture for an e-commerce platform.

**Answer:**

```
┌─────────────────────────────────────────────────────────────────┐
│                  EVENT-DRIVEN E-COMMERCE                          │
│                                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Order    │  │ Payment  │  │ Inventory│  │ Shipping │        │
│  │ Service  │  │ Service  │  │ Service  │  │ Service  │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │              │              │              │              │
│  ┌────▼──────────────▼──────────────▼──────────────▼────┐        │
│  │                    KAFKA                              │        │
│  │                                                       │        │
│  │  Topics:                                              │        │
│  │  orders.created        (Order → Payment, Inventory)   │        │
│  │  payments.completed    (Payment → Order, Shipping)    │        │
│  │  inventory.reserved    (Inventory → Order)            │        │
│  │  inventory.insufficient(Inventory → Order)            │        │
│  │  shipments.dispatched  (Shipping → Order, Notify)     │        │
│  │  notifications.send    (→ Notification Service)       │        │
│  └───────────────────────────────────────────────────────┘        │
│                                                                    │
│  SAGA: Order Placement                                            │
│  1. OrderService: OrderCreated →                                  │
│  2. InventoryService: consumes → ReserveStock                     │
│       Success → InventoryReserved                                 │
│       Failure → InventoryInsufficient → Compensate                │
│  3. PaymentService: consumes → ChargePayment                      │
│       Success → PaymentCompleted                                  │
│       Failure → PaymentFailed → Release inventory                 │
│  4. ShippingService: consumes → CreateShipment                    │
│  5. OrderService: consumes all → Update order status              │
│                                                                    │
│  Key patterns:                                                    │
│  - Choreography (events) vs Orchestration (saga orchestrator)    │
│  - Idempotent consumers (handle duplicates gracefully)           │
│  - Outbox pattern (DB transaction + outbox table → Kafka)        │
│  - Event schema versioning (Avro + Schema Registry)              │
│  - Dead letter queues per service                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Outbox pattern for reliable event publishing:**
```sql
-- In same DB transaction as business logic:
BEGIN;
  INSERT INTO orders (id, customer_id, amount) VALUES (...);
  INSERT INTO outbox (id, topic, key, payload, created_at) 
    VALUES (uuid(), 'orders.created', customer_id, '{...}', NOW());
COMMIT;

-- Separate process (Debezium CDC on outbox table) publishes to Kafka
-- Then deletes from outbox after confirmed publish
```
