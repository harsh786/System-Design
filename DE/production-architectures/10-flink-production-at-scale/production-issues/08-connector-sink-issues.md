# Connector & Sink Issues (#87-95)

> Connectors are where Flink meets the external world. These issues cover production failures in Elasticsearch, JDBC, Redis, Iceberg, and custom sinks.

---

## Issue #87: Elasticsearch Sink Bulk Failures

**Severity**: 🔴 Critical  
**Frequency**: Medium-High  
**Impact**: Data loss or backpressure, ES cluster instability

### Symptoms
```
ERROR ElasticsearchSinkFunction - Failed to execute bulk request:
  [reject] bulk [actions=5000] of [10MB] exceeding queue capacity
BulkActionRequestFailure: Request rejected by ES, action=INDEX, status=429
```
- ES returning 429 (Too Many Requests)
- ES thread pool queue full
- Bulk indexing latency increasing
- ES cluster turning yellow/red

### Root Cause
1. ES write thread pool saturated
2. Bulk request too large (too many actions or too much data)
3. Index refresh contention (too many segments)
4. Cluster under-provisioned for write load
5. Mapping explosion (too many fields)

### Fix
```java
// Tune bulk parameters
ElasticsearchSink.Builder<Event> builder = new ElasticsearchSink.Builder<>(
    httpHosts, new EventElasticsearchSinkFunction());

builder.setBulkFlushMaxActions(1000);          // Smaller batches (default 1000)
builder.setBulkFlushMaxSizeMb(5);              // 5MB per bulk (default 5MB)
builder.setBulkFlushInterval(5000);            // Flush every 5s
builder.setBulkFlushBackoff(true);
builder.setBulkFlushBackoffType(FlushBackoffType.EXPONENTIAL);
builder.setBulkFlushBackoffRetries(5);
builder.setBulkFlushBackoffDelay(1000);        // 1s initial backoff

// Handle failures gracefully
builder.setFailureHandler((ActionRequestFailureHandler) (action, failure, restStatusCode, indexer) -> {
    if (restStatusCode == 429) {
        // Retry on throttle (backoff handles this)
        indexer.add(action);
    } else if (restStatusCode == 400) {
        // Bad request - log and skip (don't retry)
        LOG.error("Malformed document, skipping: {}", failure.getMessage());
    } else {
        throw failure;  // Unknown error - fail the job
    }
});
```

```yaml
# ES cluster tuning for high write throughput
index.refresh_interval: 30s        # Reduce refresh frequency (default 1s)
index.translog.durability: async   # Async translog for speed
index.translog.sync_interval: 30s
thread_pool.write.queue_size: 1000  # Larger queue before rejecting
```

### Prevention
- Size ES cluster for write load (rule: 40K docs/sec per data node)
- Increase `refresh_interval` for write-heavy indices
- Use ILM to rollover indices (don't write to huge indices)
- Monitor ES thread pool rejection rate

---

## Issue #88: JDBC Sink Connection Pool Exhaustion

**Severity**: 🔴 Critical  
**Frequency**: Medium  
**Impact**: Writes fail, backpressure, potential data loss

### Symptoms
```
java.sql.SQLException: Cannot get a connection, pool error: 
  Timeout waiting for idle connection
HikariPool - Connection is not available, request timed out after 30000ms
```
- All connections in use
- Database showing max_connections reached
- Flink sink blocked waiting for connection

### Root Cause
1. Connection pool too small for parallelism
2. Long-running transactions holding connections
3. Database overloaded (slow queries blocking connections)
4. Connection leak (not returned to pool)
5. Network issues causing connection validation timeout

### Fix
```java
// Proper JDBC sink with connection pooling
public class BatchingJdbcSink extends RichSinkFunction<Record> {
    private transient HikariDataSource dataSource;
    private transient List<Record> buffer;
    
    @Override
    public void open(Configuration parameters) {
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl("jdbc:postgresql://host:5432/db");
        config.setMaximumPoolSize(10);          // Per parallel instance!
        config.setMinimumIdle(2);
        config.setConnectionTimeout(30000);      // 30s
        config.setIdleTimeout(300000);           // 5 min
        config.setMaxLifetime(1800000);          // 30 min
        config.setValidationTimeout(5000);
        config.addDataSourceProperty("reWriteBatchedInserts", "true");
        
        dataSource = new HikariDataSource(config);
        buffer = new ArrayList<>(BATCH_SIZE);
    }
    
    @Override
    public void invoke(Record record, Context ctx) throws Exception {
        buffer.add(record);
        if (buffer.size() >= BATCH_SIZE) {
            flushBatch();
        }
    }
    
    private void flushBatch() throws SQLException {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(INSERT_SQL)) {
            for (Record r : buffer) {
                ps.setString(1, r.getId());
                ps.setLong(2, r.getTimestamp());
                ps.addBatch();
            }
            ps.executeBatch();
            buffer.clear();
        }
    }
    
    @Override
    public void close() {
        if (dataSource != null) dataSource.close();
    }
}
```

### Prevention
- Pool size per instance: `max_db_connections / flink_parallelism`
- Always use batch inserts (10-100x faster than individual)
- Use `reWriteBatchedInserts=true` for PostgreSQL
- Monitor connection pool utilization metric
- Implement circuit breaker for database overload

---

## Issue #89: Redis Sink Timeout Under Load

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Backpressure, stale data in Redis

### Symptoms
```
io.lettuce.core.RedisCommandTimeoutException: Command timed out after 5000ms
redis.clients.jedis.exceptions.JedisConnectionException: Connection reset
```
- Redis latency spikes during high write load
- Connection pool depleted
- Cluster mode slot moved errors

### Fix
```java
// Use pipelining for bulk writes
public class PipelinedRedisSink extends RichSinkFunction<FeatureUpdate> {
    private transient RedisClient client;
    private transient StatefulRedisConnection<String, String> connection;
    private transient List<RedisFuture<?>> futures;
    private static final int PIPELINE_SIZE = 100;
    
    @Override
    public void open(Configuration params) {
        client = RedisClient.create(RedisURI.builder()
            .withHost("redis-cluster")
            .withPort(6379)
            .withTimeout(Duration.ofSeconds(10))
            .build());
        client.setOptions(ClientOptions.builder()
            .autoReconnect(true)
            .disconnectedBehavior(ClientOptions.DisconnectedBehavior.REJECT_COMMANDS)
            .build());
        connection = client.connect();
        futures = new ArrayList<>(PIPELINE_SIZE);
    }
    
    @Override
    public void invoke(FeatureUpdate update, Context ctx) {
        RedisAsyncCommands<String, String> async = connection.async();
        async.setAutoFlushCommands(false);
        
        futures.add(async.hset(update.getKey(), update.getField(), update.getValue()));
        futures.add(async.expire(update.getKey(), update.getTtlSeconds()));
        
        if (futures.size() >= PIPELINE_SIZE) {
            async.flushCommands();
            LettuceFutures.awaitAll(Duration.ofSeconds(5), 
                futures.toArray(new RedisFuture[0]));
            futures.clear();
        }
    }
    
    @Override
    public void close() {
        if (connection != null) connection.close();
        if (client != null) client.shutdown();
    }
}
```

### Prevention
- Use pipelining (batch multiple commands in one round-trip)
- Set appropriate timeouts (> Redis cluster failover time)
- Use Redis Cluster with sufficient slots
- Monitor Redis memory usage and eviction rate

---

## Issue #90: Iceberg Sink Small Files Problem

**Severity**: 🟡 Warning  
**Frequency**: High  
**Impact**: Query performance degrades, storage costs increase

### Symptoms
- Thousands of tiny files (< 1MB) per commit
- Query latency increasing over time
- S3 LIST operations slow (too many files)
- Iceberg metadata growing large

### Root Cause
Flink streaming to Iceberg commits frequently (checkpoint interval):
- Each checkpoint = one commit
- Each parallel writer creates one file per commit
- With parallelism=200 and 1-min checkpoints: 200 files/minute = 288,000 files/day

### Fix
```java
// Configure Iceberg sink for larger files
FlinkSink.forRowData(input)
    .tableLoader(tableLoader)
    .set("write.target-file-size-bytes", "536870912")  // 512MB target files
    .set("write.distribution-mode", "hash")             // Reduce file count
    .set("commit.manifest.target-size-bytes", "8388608") // 8MB manifests
    .append();
```

```sql
-- Compaction maintenance (run periodically)
CALL catalog.system.rewrite_data_files(
    table => 'db.my_table',
    strategy => 'binpack',
    options => map('target-file-size-bytes', '536870912',
                   'min-file-size-bytes', '67108864')  -- 64MB minimum
);

-- Also compact manifests
CALL catalog.system.rewrite_manifests('db.my_table');
```

```yaml
# Increase checkpoint interval for Iceberg sink jobs
execution.checkpointing.interval: 300000  # 5 min (fewer, larger commits)
```

### Prevention
- Set checkpoint interval to 5-10 minutes for Iceberg sink jobs
- Run compaction as scheduled maintenance (hourly)
- Use `hash` distribution mode to reduce writers per partition
- Monitor file count per partition

---

## Issue #91: Two-Phase Commit Sink - Pre-Commit Failure

**Severity**: 🔴 Critical  
**Frequency**: Low-Medium  
**Impact**: Data stuck in pending state, potential inconsistency

### Symptoms
```
ERROR TwoPhaseCommitSinkFunction - Failed to pre-commit transaction
```
- Sink has data in "pending" state after checkpoint
- On recovery, pending transactions need to be committed or rolled back
- External system shows uncommitted/phantom data

### Root Cause
Pre-commit (phase 1 of 2PC) failed after checkpoint barrier passed:
- Database connection dropped during prepare
- Kafka transaction init failed
- External system rejected pre-commit (capacity, permission)

### Fix
```java
// Implement proper 2PC with recovery
public class My2PCSink extends TwoPhaseCommitSinkFunction<Event, TxnState, Void> {
    
    @Override
    protected TxnState beginTransaction() {
        return new TxnState(UUID.randomUUID().toString());
    }
    
    @Override
    protected void preCommit(TxnState transaction) throws Exception {
        // Prepare but don't commit
        // Must be idempotent (may be called again on retry)
        transaction.prepare();
    }
    
    @Override
    protected void commit(TxnState transaction) {
        // Called after checkpoint success
        // Must be idempotent (may be called multiple times)
        int retries = 0;
        while (retries < MAX_RETRIES) {
            try {
                transaction.commit();
                return;
            } catch (Exception e) {
                retries++;
                Thread.sleep(1000 * retries);
            }
        }
        throw new RuntimeException("Failed to commit after " + MAX_RETRIES + " retries");
    }
    
    @Override
    protected void abort(TxnState transaction) {
        // Rollback on failure
        transaction.rollback();
    }
    
    @Override
    protected void recoverAndCommit(TxnState transaction) {
        // Called on recovery for pending transactions
        // MUST complete the commit (idempotently)
        commit(transaction);
    }
}
```

### Prevention
- Ensure pre-commit and commit are idempotent
- Implement proper `recoverAndCommit()` for crash recovery
- Set transaction timeouts longer than checkpoint interval
- Test failure scenarios in integration tests

---

## Issue #92: S3 FileSink Producing Incomplete/Corrupt Files

**Severity**: 🔴 Critical  
**Frequency**: Medium  
**Impact**: Downstream consumers read incomplete data

### Symptoms
- Parquet files that can't be read (corrupt footer)
- Files in `.inprogress` state never committed
- Missing data in downstream queries
- Files left in staging directory after crash

### Root Cause
S3 FileSink uses a staging approach:
1. Write to `.inprogress` file
2. On checkpoint: rename to final path (S3 doesn't support rename → copy + delete)
3. If crash between write and commit: `.inprogress` file orphaned

### Fix
```java
// Proper FileSink configuration
FileSink<Event> sink = FileSink
    .forRowFormat(new Path("s3://bucket/output/"), new EventEncoder())
    .withBucketAssigner(new DateTimeBucketAssigner<>("yyyy-MM-dd/HH"))
    .withRollingPolicy(
        DefaultRollingPolicy.builder()
            .withRolloverInterval(Duration.ofMinutes(15))  // New file every 15 min
            .withInactivityInterval(Duration.ofMinutes(5))  // Close after 5 min idle
            .withMaxPartSize(MemorySize.ofMebiBytes(512))   // Max 512MB per file
            .build())
    .withOutputFileConfig(OutputFileConfig.builder()
        .withPartPrefix("events")
        .withPartSuffix(".parquet")
        .build())
    .build();
```

```yaml
# S3 configuration for reliable writes
fs.s3a.fast.upload: true
fs.s3a.fast.upload.buffer: disk          # Buffer to disk before upload
fs.s3a.multipart.size: 67108864          # 64MB parts
fs.s3a.multipart.threshold: 134217728    # Start multipart at 128MB
fs.s3a.connection.maximum: 100
```

### Prevention
- Use `forBulkFormat` for Parquet (atomic file creation)
- Set rolling policy with reasonable file sizes (100MB-1GB)
- Run orphan file cleanup job periodically
- Enable S3 lifecycle rules to delete `.inprogress` files after 1 day

---

## Issue #93: Custom Sink Blocking processElement

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Backpressure, reduced throughput

### Symptoms
- Sink throughput much lower than expected
- Single-threaded writing to external system
- `busyTimeMsPerSecond` near 1000 on sink
- Every record waiting for synchronous I/O

### Root Cause
Custom sink doing synchronous I/O in `invoke()`:
```java
// Bad: Blocking in invoke()
@Override
public void invoke(Record record, Context ctx) {
    httpClient.post(url, record).execute();  // Blocks until response!
}
```

### Fix
```java
// Option 1: Use AsyncSinkBase (Flink 1.15+)
public class MyAsyncSink extends AsyncSinkBase<Event, RequestEntry> {
    @Override
    protected void submitRequestEntries(
            List<RequestEntry> entries, 
            Consumer<List<RequestEntry>> callback) {
        // Non-blocking batch submit
        CompletableFuture.supplyAsync(() -> {
            batchWrite(entries);
            return null;
        }).thenRun(() -> callback.accept(Collections.emptyList()));
    }
}

// Option 2: Internal buffering with async flush
public class BufferedAsyncSink extends RichSinkFunction<Event> {
    private transient BlockingQueue<Event> buffer;
    private transient ExecutorService executor;
    
    @Override
    public void open(Configuration params) {
        buffer = new ArrayBlockingQueue<>(10_000);
        executor = Executors.newFixedThreadPool(4);
        // Start background flush threads
        for (int i = 0; i < 4; i++) {
            executor.submit(this::flushLoop);
        }
    }
    
    @Override
    public void invoke(Event event, Context ctx) {
        buffer.put(event);  // Non-blocking if buffer not full
    }
}
```

### Prevention
- Never do synchronous I/O in `invoke()`
- Use `AsyncSinkBase` for new sinks (Flink 1.15+)
- Use Async I/O operator for lookups
- Batch writes (reduce round-trips)

---

## Issue #94: Connector Version Incompatibility

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: ClassNotFoundException, NoSuchMethodError at runtime

### Symptoms
```
java.lang.NoSuchMethodError: org.apache.kafka.clients.consumer.KafkaConsumer.poll(J)
java.lang.ClassNotFoundException: org.apache.flink.connector.kafka.source.KafkaSource
```
- Job starts but fails on first record
- Compile succeeds but runtime fails
- Different versions of same library conflicting

### Root Cause
- Flink connector version doesn't match Flink version
- Kafka client version in connector conflicts with user's Kafka client
- Shading not done properly (multiple copies of same class)
- Flink SQL connector vs DataStream connector mixed

### Fix
```xml
<!-- Maven: Use proper version alignment -->
<properties>
    <flink.version>1.18.1</flink.version>
    <kafka.version>3.6.1</kafka.version>
</properties>

<dependencies>
    <!-- Flink Kafka connector matching Flink version -->
    <dependency>
        <groupId>org.apache.flink</groupId>
        <artifactId>flink-connector-kafka</artifactId>
        <version>${flink.version}</version>
    </dependency>
    
    <!-- Exclude conflicting transitive dependencies -->
    <dependency>
        <groupId>my.library</groupId>
        <artifactId>my-lib</artifactId>
        <exclusions>
            <exclusion>
                <groupId>org.apache.kafka</groupId>
                <artifactId>kafka-clients</artifactId>
            </exclusion>
        </exclusions>
    </dependency>
</dependencies>
```

### Prevention
- Use Flink's BOM (Bill of Materials) for version alignment
- Use `maven-shade-plugin` to relocate conflicting packages
- Test with `env.getConfig().disableGenericTypes()` to catch early
- Check Flink compatibility matrix for connector versions

---

## Issue #95: Sink Exactly-Once Breaking After Upgrade

**Severity**: 🔴 Critical  
**Frequency**: Low-Medium  
**Impact**: Duplicates or data loss during upgrade window

### Symptoms
- After upgrading Flink job, exactly-once guarantee broken
- Duplicates appearing in sink
- Open transactions from old job version not committed

### Root Cause
- Kafka `transactional.id` prefix changed between versions
- Old transactions not cleaned up before new job starts
- Savepoint doesn't include pending Kafka transactions (they're in Kafka, not Flink state)
- Two-phase commit state not properly restored

### Fix
```java
// Keep transactional ID prefix stable across versions
KafkaSink.<String>builder()
    .setTransactionalIdPrefix("my-job-sink-v1")  // Keep SAME across upgrades
    .setDeliveryGuarantee(DeliveryGuarantee.EXACTLY_ONCE)
    .build();
```

```bash
# Before upgrade: ensure all transactions committed
# 1. Take savepoint (triggers commit of pending transactions)
flink savepoint <job-id> s3://bucket/savepoints/pre-upgrade

# 2. Cancel job (after savepoint succeeds)
flink cancel <job-id>

# 3. Wait for transaction timeout (or manually abort old transactions)
kafka-transactions.sh --bootstrap-server kafka:9092 list --status open

# 4. Deploy new version from savepoint
flink run -s s3://bucket/savepoints/pre-upgrade new-job.jar
```

### Prevention
- Keep `transactionalIdPrefix` stable across job versions
- Always stop with savepoint before upgrade (commits pending transactions)
- Set `transaction.timeout.ms` reasonably short (5-15 min)
- Validate exactly-once in staging with upgrade scenario
