# Kafka Integration Issues (#41-53)

> Kafka is the most common source/sink for Flink. These issues cover the production challenges of the Kafka-Flink integration at scale.

---

## Issue #41: Kafka Consumer Lag Growing Unbounded

**Severity**: 🔴 Critical  
**Frequency**: Very High  
**Impact**: Data freshness degraded, potential memory issues if backlog processed

### Symptoms
- `records-lag-max` growing linearly
- Flink processing rate < Kafka production rate
- Dashboard data becomes stale
- Consumer group shows increasing lag per partition

### Root Cause
1. **Under-provisioned**: Flink parallelism too low for throughput
2. **Backpressure**: Downstream operator/sink is slow
3. **Skewed partitions**: Some Kafka partitions have much more data
4. **After restart**: Job catching up from checkpoint offset (temporary lag)
5. **Source idle**: Some partitions not being consumed

### Diagnosis
```bash
# Check consumer group lag
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --group flink-job-consumer-group

# Check per-partition lag
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --group flink-job-consumer-group | sort -k5 -n -r | head -10
```

```promql
# Prometheus
flink_taskmanager_job_task_operator_KafkaSourceReader_KafkaConsumer_records_lag_max
flink_taskmanager_job_task_operator_KafkaSourceReader_KafkaConsumer_records_consumed_rate
```

### Fix
```yaml
# 1. Increase source parallelism (MUST equal Kafka partitions)
# If topic has 200 partitions, source parallelism must be ≤ 200
parallelism.default: 200

# 2. Increase Kafka fetch size (consume more per poll)
kafka.consumer.fetch.max.bytes: 52428800       # 50MB
kafka.consumer.max.partition.fetch.bytes: 10485760  # 10MB per partition
kafka.consumer.max.poll.records: 5000

# 3. Add more Kafka partitions (if parallelism is already at max)
kafka-topics.sh --alter --topic my-topic --partitions 400 \
  --bootstrap-server kafka:9092
# WARNING: Repartitioning changes key→partition mapping!
```

### Prevention
- Set Kafka partitions = expected max Flink parallelism from day one
- Alert when lag > threshold (e.g., 5 minutes of production rate)
- Monitor lag trend (growing = under-provisioned)

---

## Issue #42: Kafka Consumer Rebalance Storm

**Severity**: 🔴 Critical  
**Frequency**: Medium-High  
**Impact**: Processing stops during rebalance, duplicate processing possible

### Symptoms
```
INFO ConsumerCoordinator - Revoke previously assigned partitions [...]
INFO ConsumerCoordinator - Setting newly assigned partitions [...]
```
- Repeated rebalance messages in logs
- Processing gaps (0 records consumed) during rebalance
- Happens every `max.poll.interval.ms` (default 5 min)

### Root Cause
Consumer fails to poll within `max.poll.interval.ms`:
1. **GC pause** > `max.poll.interval.ms`
2. **Slow processing**: Processing batch takes too long before next poll
3. **Checkpoint blocking**: Long checkpoint blocks processing thread
4. **Session timeout**: Network issues cause session expiry

### Fix
```yaml
# Increase poll interval (allow more processing time between polls)
kafka.consumer.max.poll.interval.ms: 900000    # 15 min (default 5 min)
kafka.consumer.session.timeout.ms: 60000        # 60s (default 10s)
kafka.consumer.heartbeat.interval.ms: 10000     # 10s

# Reduce records per poll (faster processing per batch)
kafka.consumer.max.poll.records: 500            # Down from 5000

# Use cooperative rebalancing (less disruptive)
kafka.consumer.partition.assignment.strategy: \
  org.apache.kafka.clients.consumer.CooperativeStickyAssignor
```

### Prevention
- Use `CooperativeStickyAssignor` (Kafka 2.4+)
- Set `max.poll.interval.ms` > max checkpoint duration
- Monitor rebalance frequency (> 1/hour = problem)

---

## Issue #43: Kafka Offset Commit Failure

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: On restart, may reprocess some messages (at-least-once)

### Symptoms
```
WARN FlinkKafkaConsumer - Committing offsets to Kafka failed.
org.apache.kafka.clients.consumer.CommitFailedException: 
  Commit cannot be completed since the group has already rebalanced
```

### Root Cause
Offset commit happens asynchronously. If a rebalance occurs between processing and commit:
- Partition reassigned to different consumer
- Original consumer's commit rejected
- On recovery, messages may be reprocessed from last committed offset

### Fix
```java
// Use Flink's checkpoint-based offset tracking (NOT Kafka commit)
KafkaSource.<String>builder()
    .setStartingOffsets(OffsetsInitializer.committedOffsets(
        OffsetResetStrategy.EARLIEST))
    // Offsets stored in Flink checkpoint, not Kafka consumer group
    .setProperty("enable.auto.commit", "false")
    .build();
```

```yaml
# Rely on Flink checkpoints for exactly-once (not Kafka offset commits)
execution.checkpointing.mode: EXACTLY_ONCE
# Kafka offsets committed on checkpoint success (for monitoring only)
```

### Prevention
- Never rely on Kafka offset commits for correctness
- Use Flink checkpoints as source of truth for offsets
- Kafka commits are "best effort" for monitoring tools
- Ensure idempotent processing in case of offset replay

---

## Issue #44: Exactly-Once Kafka Sink - Transaction Timeout

**Severity**: 🔴 Critical  
**Frequency**: Medium  
**Impact**: Kafka transactions aborted, data loss in downstream consumers

### Symptoms
```
ERROR FlinkKafkaProducer - Transaction timeout for [...] 
  Transactions timed out after 60000ms (transaction.timeout.ms)
```
- Kafka sink transactions timing out
- Downstream consumers (read_committed) see gaps in data
- Happens when checkpoint duration > `transaction.timeout.ms`

### Root Cause
Flink's exactly-once Kafka sink uses two-phase commit:
1. Pre-commit: Open Kafka transaction, write records
2. Commit: On checkpoint complete, commit transaction

If checkpoint takes longer than `transaction.timeout.ms`, Kafka broker aborts the transaction.

### Fix
```yaml
# Kafka sink transaction timeout MUST be > max checkpoint duration
# If checkpoints take up to 10 minutes:
kafka.producer.transaction.timeout.ms: 900000    # 15 min (> checkpoint time)

# Kafka broker must also allow long transactions
# server.properties:
transaction.max.timeout.ms: 900000               # Must be ≥ producer timeout
```

```java
// Configure in code
KafkaSink.<String>builder()
    .setBootstrapServers("kafka:9092")
    .setDeliverGuarantee(DeliveryGuarantee.EXACTLY_ONCE)
    .setTransactionalIdPrefix("my-job-" + UUID.randomUUID())
    .setProperty("transaction.timeout.ms", "900000")
    .build();
```

### Prevention
- Formula: `transaction.timeout.ms` > `checkpoint.timeout` + buffer
- Monitor checkpoint duration — if growing, increase transaction timeout
- Alert if checkpoint duration > 50% of transaction timeout

---

## Issue #45: Kafka Topic Auto-Discovery Not Working

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: New topics not consumed, data loss for new topics

### Symptoms
- New Kafka topics matching pattern not consumed
- Source metrics show same partition count despite new topics
- Only topics existing at job start are consumed

### Root Cause
- Topic pattern discovery disabled
- Discovery interval too long
- Regex pattern not matching new topic names
- RBAC preventing topic listing

### Fix
```java
// Enable dynamic topic discovery
KafkaSource.<String>builder()
    .setTopicPattern(Pattern.compile("events-.*"))  // Pattern match
    .setProperty("partition.discovery.interval.ms", "30000")  // Check every 30s
    .build();
```

### Prevention
- Always set `partition.discovery.interval.ms` for dynamic topics
- Test regex patterns against all expected topic names
- Monitor discovered partition count

---

## Issue #46: Kafka Deserialization Failure Crashing Job

**Severity**: 🔴 Critical  
**Frequency**: High  
**Impact**: Job crash on corrupt/invalid message, continuous restart loop

### Symptoms
```
java.io.IOException: Failed to deserialize consumer record
Caused by: com.fasterxml.jackson.core.JsonParseException: Unexpected character
```
- Job restarts in loop on same offset (poison pill)
- Cannot advance past corrupt message
- Restart always fails at same point

### Root Cause
A single malformed message in Kafka topic causes deserialization failure:
- Invalid JSON/Avro/Protobuf encoding
- Schema incompatibility (producer used different schema)
- Null value in non-nullable field
- Binary data in text-expected field

### Fix
```java
// Implement fault-tolerant deserialization
public class SafeDeserializer implements KafkaRecordDeserializationSchema<Event> {
    private static final OutputTag<byte[]> DEAD_LETTER = 
        new OutputTag<>("dead-letter") {};
    
    @Override
    public void deserialize(ConsumerRecord<byte[], byte[]> record, 
                           Collector<Event> out) {
        try {
            Event event = objectMapper.readValue(record.value(), Event.class);
            out.collect(event);
        } catch (Exception e) {
            // Log and skip corrupt message (DON'T throw!)
            LOG.warn("Failed to deserialize record at partition={} offset={}: {}",
                record.partition(), record.offset(), e.getMessage());
            metrics.counter("deserialization-failures").inc();
            // Optionally: write to dead letter topic
        }
    }
}
```

### Prevention
- ALWAYS handle deserialization errors gracefully
- Use Schema Registry for schema validation at producer
- Implement dead-letter queue for failed records
- Add deserialization failure rate alert (> 1% = investigate)

---

## Issue #47: Kafka Producer Backlog Causing Memory Pressure

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Memory growth in sink, potential OOM

### Symptoms
- Kafka sink memory growing
- `buffer-total-bytes` near `buffer.memory` limit
- `record-queue-time-max` increasing
- Producer batches not being sent fast enough

### Root Cause
Kafka producer buffers records in memory before sending. If broker is slow:
- Buffer fills up (default 32MB)
- Producer blocks on `send()` (or throws if non-blocking)
- Flink operator blocks → backpressure propagates

### Fix
```yaml
# Tune producer batching
kafka.producer.batch.size: 65536              # 64KB batches
kafka.producer.linger.ms: 10                  # Wait 10ms to batch
kafka.producer.buffer.memory: 134217728       # 128MB buffer (default 32MB)
kafka.producer.max.block.ms: 60000            # Block max 60s before failing
kafka.producer.compression.type: lz4          # Compress → less network → faster sends
kafka.producer.acks: 1                        # acks=1 if at-least-once acceptable
```

### Prevention
- Monitor `buffer-available-bytes` — alert when < 10% available
- Use compression (lz4) to reduce network bandwidth
- Size `buffer.memory` to handle burst (2-3x average throughput × linger)

---

## Issue #48: Kafka Partition Leader Change Causing Temporary Errors

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Brief processing interruption, retries succeed

### Symptoms
```
WARN KafkaConsumer - Error while fetching metadata: LEADER_NOT_AVAILABLE
ERROR KafkaProducer - NotLeaderOrFollowerException for partition events-42
```
- Brief errors during Kafka broker rolling restart
- Automatic recovery after metadata refresh

### Fix
```yaml
# Increase retry and backoff
kafka.consumer.retry.backoff.ms: 500
kafka.consumer.metadata.max.age.ms: 30000     # Refresh metadata every 30s
kafka.producer.retries: 10
kafka.producer.retry.backoff.ms: 500
kafka.producer.delivery.timeout.ms: 300000    # 5 min total delivery timeout
```

### Prevention
- Configure retries with backoff (Kafka client handles automatically)
- Monitor Kafka cluster health (under-replicated partitions)
- Perform rolling restarts during low-traffic windows

---

## Issue #49: Schema Registry Lookup Failure

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Deserialization fails, messages rejected

### Symptoms
```
ERROR AvroDeserializationSchema - Failed to fetch schema from registry
io.confluent.kafka.schemaregistry.client.rest.exceptions.RestClientException: 
  Schema not found; error code: 40403
```

### Root Cause
- Schema Registry unreachable (network/DNS issue)
- Schema was deleted from registry
- Schema ID in message doesn't exist in registry
- Registry rate limiting

### Fix
```java
// Add caching and fallback
Map<String, String> schemaRegistryConfig = new HashMap<>();
schemaRegistryConfig.put("schema.registry.url", "http://schema-registry:8081");
schemaRegistryConfig.put("max.schemas.per.subject", "1000");
schemaRegistryConfig.put("schema.registry.cache.capacity", "5000");

// Use multiple registry instances
schemaRegistryConfig.put("schema.registry.url", 
    "http://sr1:8081,http://sr2:8081,http://sr3:8081");
```

### Prevention
- Deploy Schema Registry in HA (multi-instance)
- Never delete schemas that are in use
- Cache schemas aggressively (they're immutable once registered)
- Monitor Schema Registry health and latency

---

## Issue #50: Kafka Source Not Respecting Committed Offsets After Restart

**Severity**: 🔴 Critical  
**Frequency**: Medium  
**Impact**: Massive reprocessing from earliest offset

### Symptoms
- After restart, job starts consuming from beginning of topic
- Massive consumer lag appears (topic retention worth of data)
- Processing load spikes, downstream systems overwhelmed

### Root Cause
1. Consumer group offsets expired (Kafka `offsets.retention.minutes` exceeded)
2. Checkpoint lost/corrupted → falls back to reset policy
3. `OffsetResetStrategy.EARLIEST` configured as fallback
4. Different consumer group ID between deployments

### Fix
```java
// Use checkpoint offsets as primary, Kafka committed as fallback
KafkaSource.<String>builder()
    .setStartingOffsets(OffsetsInitializer.committedOffsets(
        OffsetResetStrategy.LATEST))  // LATEST not EARLIEST as fallback!
    .setProperty("group.id", "my-job-v1")  // Keep consistent across deploys
    .build();
```

```yaml
# Kafka broker: increase offset retention
offsets.retention.minutes: 20160  # 14 days (default 7 days)
```

### Prevention
- Use `LATEST` as reset strategy (not `EARLIEST`)
- Keep consumer group ID stable across deployments
- Ensure checkpoints are durable (S3, not local)
- Set Kafka offset retention > max job downtime

---

## Issue #51: Exactly-Once Semantics - Zombie Transactions on Restart

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Downstream consumers blocked by open transactions

### Symptoms
- Downstream consumers (read_committed) stop making progress
- Kafka shows open transactions that never commit/abort
- Last Stable Offset (LSO) stuck behind open transaction

### Root Cause
When Flink job restarts, previous transaction IDs are abandoned:
- Old producer with open transaction is now dead
- Transaction stays open until `transaction.timeout.ms` expires
- Downstream consumers (read_committed) cannot read past open transaction

### Fix
```yaml
# Reduce transaction timeout to minimize blocking window
kafka.producer.transaction.timeout.ms: 300000  # 5 min (faster cleanup)

# Use unique transactional ID prefix per job instance
# Flink does this automatically with checkpoint IDs
```

```bash
# Manual: abort stuck transactions
kafka-transactions.sh --bootstrap-server kafka:9092 \
  list --status open | grep "my-job"

kafka-transactions.sh --bootstrap-server kafka:9092 \
  abort --producerId <pid> --epoch <epoch>
```

### Prevention
- Set reasonable `transaction.timeout.ms` (5-15 min)
- Monitor Last Stable Offset lag on downstream topics
- Use `transactional.id.prefix` unique per job version

---

## Issue #52: Kafka Source Watermark Lagging Behind Due to Inactive Partitions

**Severity**: 🟡 Warning  
**Frequency**: High  
**Impact**: Watermark stalls, windows never fire

### Symptoms
- Overall watermark stuck at old timestamp
- Some partitions have no data (temporarily or permanently)
- Windows never close because watermark won't advance

### Root Cause
Watermark = min(all partition watermarks). If one partition has no data:
- Its watermark stays at initial value (Long.MIN_VALUE)
- Overall watermark stuck → no window ever fires
- Even partitions with data are stuck

### Fix
```java
// Mark idle partitions to not hold back watermark
WatermarkStrategy.<Event>forBoundedOutOfOrderness(Duration.ofSeconds(30))
    .withIdleness(Duration.ofMinutes(1))  // After 1 min idle, exclude from watermark
    .withTimestampAssigner((event, ts) -> event.getTimestamp());
```

### Prevention
- **ALWAYS** configure `.withIdleness()` for multi-partition sources
- Set idleness timeout < expected max gap between events
- Monitor per-source-subtask watermark values

---

## Issue #53: Kafka Source Offset Out of Range

**Severity**: 🔴 Critical  
**Frequency**: Low-Medium  
**Impact**: Job fails to start, cannot consume from requested offset

### Symptoms
```
ERROR KafkaConsumer - OffsetOutOfRangeException: 
  Fetch offset 12345 is out of range for partition events-0, 
  earliest: 50000, latest: 100000
```

### Root Cause
Checkpoint/savepoint contains an offset that's been deleted by Kafka retention:
- Job was down longer than Kafka retention period
- Topic retention was reduced
- Topic was recreated (different offsets)

### Fix
```java
// Handle gracefully: skip to earliest available
KafkaSource.<String>builder()
    .setStartingOffsets(OffsetsInitializer.committedOffsets(
        OffsetResetStrategy.EARLIEST))  // Fall back to earliest available
    .setProperty("auto.offset.reset", "earliest")
    .build();
```

```bash
# Manual: Reset consumer group to latest
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --group my-flink-job --reset-offsets --to-latest \
  --topic my-topic --execute
```

### Prevention
- Set Kafka retention > max expected job downtime
- Alert when job is down > 50% of topic retention time
- Use `EARLIEST` reset strategy (reprocess is better than data loss)
- Take savepoints before planned downtime
