# Interview Questions Set 3: Apache Flink & Stream Processing (Q61-90)

---

## Q61: Explain Flink's checkpointing mechanism. How does it achieve exactly-once?

**Answer:**

**Chandy-Lamport algorithm (distributed snapshots):**

```
JobManager triggers checkpoint barrier:

Source 0 ──[data]──[BARRIER n]──[data]──▶ Operator A ──▶ Sink
Source 1 ──[data]──[BARRIER n]──[data]──▶ Operator A ──▶ Sink

1. JobManager: "Start checkpoint n"
2. Sources: Snapshot source state (Kafka offsets), inject barrier into stream
3. Barriers flow downstream WITH data (in-order)
4. Operator receives barrier: Snapshot state, forward barrier
5. Multi-input operators: ALIGN barriers (buffer data from ahead-side)
6. Sink receives barrier: Snapshot sink state, acknowledge to JM
7. JobManager: All operators acked → Checkpoint n COMPLETE

State is stored in STATE BACKEND:
  - HashMapStateBackend: In-memory (JVM heap). Fast, limited by RAM.
  - EmbeddedRocksDBStateBackend: On-disk. Handles TB of state. Async checkpoints.
```

**Exactly-once via checkpoints:**
- On failure: Restore ALL operators to last completed checkpoint
- Sources replay from checkpointed position (Kafka: seek to offset)
- Processing deterministic → same output produced
- Sinks use 2PC or idempotent writes

**Unaligned checkpoints (Flink 1.11+):**
- Don't buffer data during barrier alignment
- Barriers can overtake in-flight records
- Stores in-flight data as part of checkpoint
- Benefit: Lower checkpoint latency under backpressure

---

## Q62: What is the difference between event time, processing time, and ingestion time?

**Answer:**

```
Event Created    Ingested to Kafka    Processed by Flink
     │                   │                    │
     ▼                   ▼                    ▼
─────●───────────────────●────────────────────●──── time
   EVENT TIME        INGESTION TIME      PROCESSING TIME
   (12:00:00)         (12:00:05)          (12:00:15)
   
   5s network         10s backlog
   delay              (consumer lag)
```

| Time notion | Source | Deterministic? | Use case |
|-------------|--------|---------------|----------|
| Event time | Embedded in event | Yes (same result on replay) | Analytics, billing |
| Processing time | System clock at processing | No (depends on speed) | Monitoring, low-latency alerts |
| Ingestion time | Source operator clock | Semi (depends on ingestion) | Compromise |

**Why event time matters:**
```java
// With event time: same answer regardless of processing delay
stream
    .assignTimestampsAndWatermarks(
        WatermarkStrategy.<Event>forBoundedOutOfOrderness(Duration.ofSeconds(5))
            .withTimestampAssigner((event, timestamp) -> event.getTimestamp()))
    .keyBy(Event::getUserId)
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .sum("amount");
// Window [12:00, 12:05) always contains same events regardless of when processed
```

---

## Q63: Explain watermarks in Flink. How do you handle late data?

**Answer:**

**Watermark:** A special timestamp marker saying "no events with timestamp ≤ W will arrive."

```java
// Bounded out-of-orderness: Allow 10 seconds of lateness
WatermarkStrategy
    .forBoundedOutOfOrderness(Duration.ofSeconds(10))
    .withTimestampAssigner((event, ts) -> event.getTimestamp());

// Watermark = max_event_time_seen - 10 seconds
// When watermark passes window end → window fires

Timeline:
Events:    e(12:00:01), e(12:00:08), e(12:00:03), e(12:00:12)
Max seen:  12:00:01    12:00:08     12:00:08     12:00:12
Watermark: 11:59:51    11:59:58     11:59:58     12:00:02
                                                    │
                                     Window [12:00:00, 12:00:05) fires!
                                     (watermark 12:00:02 > window end 12:00:00 - WRONG)
                                     Wait: watermark 12:00:02 means no more events < 12:00:02
                                     Hmm, but window end is 12:00:05...
                                     Actually: window fires when watermark >= window_end
                                     So when watermark reaches 12:00:05 → fire
```

**Handling late data (after watermark):**
```java
OutputTag<Event> lateTag = new OutputTag<Event>("late-data"){};

DataStream<Result> result = stream
    .keyBy(Event::getUserId)
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .allowedLateness(Time.minutes(1))     // Allow 1 min after watermark
    .sideOutputLateData(lateTag)          // Extremely late → side output
    .sum("amount");

// Get late data for manual handling
DataStream<Event> lateData = result.getSideOutput(lateTag);
lateData.addSink(new DlqSink());  // Store for reprocessing
```

**Allowed lateness:** Window result can be UPDATED if late data arrives within allowed lateness.

---

## Q64: Compare Flink's window types. When would you use each?

**Answer:**

```
TUMBLING WINDOW (fixed, non-overlapping):
|--------|--------|--------|
  5 min    5 min    5 min
Use: Hourly aggregations, daily reports

SLIDING WINDOW (fixed, overlapping):
|--------|
   |--------|
      |--------|
  5 min window, 1 min slide
Use: Moving averages, "last 5 minutes updated every minute"

SESSION WINDOW (gap-based, dynamic):
|--events--|   gap   |--events--|   gap   |-events-|
Each session = continuous activity with gaps < threshold
Use: User sessions, click streams, activity tracking

GLOBAL WINDOW (single window per key):
|──────────────────────── all data ─────────────────────|
Must provide custom trigger (otherwise never fires)
Use: Custom windowing logic, count-based windows
```

```java
// Tumbling: Non-overlapping 1-hour windows
.window(TumblingEventTimeWindows.of(Time.hours(1)))

// Sliding: 1-hour window, sliding every 5 minutes
.window(SlidingEventTimeWindows.of(Time.hours(1), Time.minutes(5)))

// Session: New session after 30-min gap
.window(EventTimeSessionWindows.withGap(Time.minutes(30)))

// Global with custom trigger: Fire every 100 elements
.window(GlobalWindows.create())
.trigger(CountTrigger.of(100))
```

---

## Q65: How does Flink handle backpressure? How do you diagnose it?

**Answer:**

**Credit-based flow control:**
```
Upstream Task → Network Buffer → Downstream Task

Downstream has limited buffers (credits)
When buffers full → stops requesting data from upstream
Upstream buffers fill → propagates backward to source
Source: Kafka consumer pauses (or slows poll rate)

No data loss, no dropping, automatic propagation
```

**Diagnosing backpressure (Flink UI):**
```
Metrics per operator:
  backPressuredTimeMsPerSecond: Time spent backpressured
  idleTimeMsPerSecond: Time idle (waiting for input)
  busyTimeMsPerSecond: Time processing

Pattern identification:
  Operator A: busy=900ms, idle=0, backpressured=100ms  ← BOTTLENECK
  Operator B: busy=100ms, idle=0, backpressured=900ms  ← Victim (waiting)
  Operator C: busy=100ms, idle=900ms                   ← Upstream of bottleneck

The BOTTLENECK is the operator with HIGH busy + LOW backpressured
```

**Common causes and fixes:**
| Cause | Symptom | Fix |
|-------|---------|-----|
| Slow operator | High busy time | Increase parallelism for that operator |
| State access slow | High busy on stateful ops | Switch to RocksDB, tune compaction |
| External call (DB/API) | High busy, low throughput | Async I/O, batch requests |
| Skewed keys | One subtask backpressured | Better key distribution |
| GC pauses | Spiky backpressure | Tune GC, reduce heap usage |
| Checkpoint alignment | Periodic backpressure | Unaligned checkpoints |

---

## Q66: How do you manage state in Flink? Explain state backends and TTL.

**Answer:**

**State types:**
```java
// ValueState: Single value per key
ValueState<Long> count = getRuntimeContext().getState(
    new ValueStateDescriptor<>("count", Long.class));
count.update(count.value() + 1);

// ListState: List of values per key
ListState<Event> buffer = getRuntimeContext().getListState(
    new ListStateDescriptor<>("buffer", Event.class));
buffer.add(event);

// MapState: Key-value map per key
MapState<String, Double> prices = getRuntimeContext().getMapState(
    new MapStateDescriptor<>("prices", String.class, Double.class));
prices.put("BTC", 45000.0);

// ReducingState / AggregatingState: Pre-aggregated values
```

**State backends:**
```
HashMapStateBackend:
  + Fast (in-memory, JVM objects)
  + Low serialization cost
  - Limited by JVM heap
  - Full state serialized on checkpoint (slow for large state)
  Use: Small to medium state (< 10 GB)

EmbeddedRocksDBStateBackend:
  + Handles TB of state
  + Incremental checkpoints (only changed SST files)
  + State can exceed memory (spills to disk)
  - Slower access (serialization + disk I/O)
  - Need to tune RocksDB (block cache, write buffer)
  Use: Large state, production workloads
```

**State TTL (Time-To-Live):**
```java
StateTtlConfig ttlConfig = StateTtlConfig
    .newBuilder(Time.hours(24))                    // Expire after 24h
    .setUpdateType(UpdateType.OnReadAndWrite)      // Reset TTL on access
    .setStateVisibility(NeverReturnExpired)        // Don't return expired
    .cleanupFullSnapshot()                         // Clean on checkpoint
    .cleanupInRocksdbCompactFilter(1000)          // Clean during compaction
    .build();

ValueStateDescriptor<String> descriptor = 
    new ValueStateDescriptor<>("session", String.class);
descriptor.enableTimeToLive(ttlConfig);
```

---

## Q67: Design a real-time fraud detection system using Flink CEP.

**Answer:**

```java
// Complex Event Processing for fraud detection

// Pattern: 3+ transactions > $1000 within 5 minutes from same user
Pattern<Transaction, ?> fraudPattern = Pattern
    .<Transaction>begin("first")
        .where(new SimpleCondition<Transaction>() {
            public boolean filter(Transaction t) {
                return t.getAmount() > 1000;
            }
        })
    .followedBy("second")
        .where(new SimpleCondition<Transaction>() {
            public boolean filter(Transaction t) {
                return t.getAmount() > 1000;
            }
        })
    .followedBy("third")
        .where(new SimpleCondition<Transaction>() {
            public boolean filter(Transaction t) {
                return t.getAmount() > 1000;
            }
        })
    .within(Time.minutes(5));

// Apply pattern on keyed stream (per user)
PatternStream<Transaction> patternStream = CEP.pattern(
    transactions.keyBy(Transaction::getUserId),
    fraudPattern
);

// Extract matches
DataStream<FraudAlert> alerts = patternStream.process(
    new PatternProcessFunction<Transaction, FraudAlert>() {
        public void processMatch(Map<String, List<Transaction>> match, 
                                  Context ctx, Collector<FraudAlert> out) {
            Transaction first = match.get("first").get(0);
            Transaction third = match.get("third").get(0);
            out.collect(new FraudAlert(
                first.getUserId(),
                match.values().stream().flatMap(List::stream).mapToDouble(Transaction::getAmount).sum(),
                "3+ high-value transactions in 5 minutes"
            ));
        }
    }
);

alerts.addSink(new AlertingSink());  // PagerDuty, Kafka alert topic
```

**Additional patterns:**
- Velocity: Card used in 2 different countries within 1 hour
- Amount: Single transaction > 10x user's average
- Frequency: > 20 transactions per minute (bot behavior)

---

## Q68: How do you handle exactly-once with Flink writing to Kafka?

**Answer:**

**TwoPhaseCommitSinkFunction (Kafka 2PC):**

```java
FlinkKafkaProducer<String> producer = new FlinkKafkaProducer<>(
    "output-topic",
    new SimpleStringSchema(),
    properties,
    FlinkKafkaProducer.Semantic.EXACTLY_ONCE  // Enable 2PC
);

// Properties required:
properties.put("transaction.timeout.ms", "900000");  // > checkpoint interval
// MUST be less than Kafka broker's transaction.max.timeout.ms (default 15min)

stream.addSink(producer);
```

**How it works:**
```
Checkpoint n starts:
  1. Flink pre-commits Kafka transaction (data written but not visible)
  2. Operator snapshots state
  3. Barrier passes to sink

Checkpoint n completes:
  4. JobManager notifies all operators: checkpoint successful
  5. Sink COMMITS Kafka transaction → data visible to consumers
  
If failure before commit:
  6. Kafka transaction times out → ABORTED → data never visible
  7. Flink restores from checkpoint n-1, replays
```

**Caveats:**
- `transaction.timeout.ms` must be > checkpoint interval
- Consumers must use `isolation.level=read_committed`
- Max open transactions = checkpoint concurrency (usually 1)
- Kafka transactions hold resources on broker (don't set timeout too high)

---

## Q69: Explain Flink's Table API / SQL. How does it relate to DataStream API?

**Answer:**

```java
// Table API (programmatic, type-safe)
Table orders = tableEnv.from("kafka_orders");
Table result = orders
    .filter($("amount").isGreater(100))
    .groupBy($("category"))
    .select($("category"), $("amount").sum().as("total"));

// SQL (declarative)
Table result = tableEnv.sqlQuery("""
    SELECT category, SUM(amount) as total
    FROM kafka_orders
    WHERE amount > 100
    GROUP BY category
""");

// Conversion between Table and DataStream:
DataStream<Row> stream = tableEnv.toDataStream(result);
Table table = tableEnv.fromDataStream(stream);

// Dynamic tables concept:
// A streaming query on a table produces a CHANGELOG STREAM:
// +I (insert), -U (update before), +U (update after), -D (delete)
```

**Connectors in SQL:**
```sql
CREATE TABLE kafka_orders (
    order_id STRING,
    customer_id STRING,
    amount DECIMAL(10,2),
    order_time TIMESTAMP(3),
    WATERMARK FOR order_time AS order_time - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'orders',
    'properties.bootstrap.servers' = 'broker:9092',
    'format' = 'json',
    'scan.startup.mode' = 'latest-offset'
);

CREATE TABLE result_sink (
    category STRING,
    window_start TIMESTAMP,
    total_amount DECIMAL(10,2)
) WITH (
    'connector' = 'jdbc',
    'url' = 'jdbc:postgresql://db:5432/analytics',
    'table-name' = 'hourly_revenue'
);

INSERT INTO result_sink
SELECT category, window_start, SUM(amount)
FROM TABLE(
    TUMBLE(TABLE kafka_orders, DESCRIPTOR(order_time), INTERVAL '1' HOUR))
GROUP BY category, window_start;
```

---

## Q70: How do you handle state migration in Flink when upgrading application logic?

**Answer:**

**Savepoint:** Manually triggered, portable checkpoint for upgrades.

```bash
# Take savepoint before upgrade
flink savepoint <job-id> s3://savepoints/v1/

# Stop job gracefully
flink cancel --withSavepoint s3://savepoints/v1/ <job-id>

# Deploy new version, resume from savepoint
flink run -s s3://savepoints/v1/ new-job.jar
```

**State compatibility rules:**
```java
// Rule 1: Assign UNIQUE IDs to all operators
env.addSource(source).uid("kafka-source")
   .map(mapper).uid("enrichment-mapper")
   .keyBy(...)
   .window(...).uid("hourly-window")
   .addSink(sink).uid("output-sink");

// Without uid(), Flink auto-generates IDs based on topology
// Topology change → different ID → state LOST
// ALWAYS set .uid() explicitly!
```

**Schema evolution for state:**
```java
// Approach 1: Use Avro for state serialization (built-in evolution)
ValueStateDescriptor<GenericRecord> desc = new ValueStateDescriptor<>(
    "user-state", new AvroSerializer<>(UserState.class));

// Approach 2: State processor API (offline state manipulation)
// Read savepoint, transform state, write new savepoint
SavepointReader reader = SavepointReader.read(env, savepointPath, backend);
DataSet<KeyedState> oldState = reader.readKeyedState("my-uid", ...);
// Transform schema
DataSet<KeyedState> newState = oldState.map(this::migrateSchema);
// Write modified savepoint
SavepointWriter.fromExistingSavepoint(savepointPath)
    .withOperator("my-uid", newState)
    .write(newSavepointPath);
```

**What you CAN change:**
- Add/remove operators (with uid)
- Change parallelism
- Change operator logic (same state schema)

**What BREAKS state restore:**
- Change state type (ValueState → MapState)
- Remove operator without uid (can't find state)
- Change key type/serializer

---

## Q71: Explain Flink's async I/O. When and why would you use it?

**Answer:**

**Problem:** Synchronous external calls (DB lookup, API call) block processing. One slow call blocks entire operator.

**Solution:** Async I/O pattern — issue many concurrent requests, process responses as they arrive.

```java
// Synchronous (bad): 1 request at a time, 10ms each
// Throughput: 100 events/sec per subtask

// Asynchronous (good): 100 concurrent requests
// Throughput: 10,000 events/sec per subtask

class AsyncDatabaseLookup extends RichAsyncFunction<Event, EnrichedEvent> {
    private transient AsyncClient client;
    
    @Override
    public void open(Configuration params) {
        client = AsyncDatabaseClient.create(config);
    }
    
    @Override
    public void asyncInvoke(Event event, ResultFuture<EnrichedEvent> resultFuture) {
        CompletableFuture<UserProfile> future = client.getUser(event.getUserId());
        
        future.thenAccept(profile -> {
            resultFuture.complete(
                Collections.singleton(new EnrichedEvent(event, profile))
            );
        }).exceptionally(ex -> {
            resultFuture.complete(Collections.singleton(
                new EnrichedEvent(event, UserProfile.UNKNOWN)  // Default on failure
            ));
            return null;
        });
    }
    
    @Override
    public void timeout(Event event, ResultFuture<EnrichedEvent> resultFuture) {
        resultFuture.complete(Collections.singleton(
            new EnrichedEvent(event, UserProfile.TIMEOUT)));
    }
}

// Apply with ordering guarantee
AsyncDataStream.orderedWait(
    inputStream,
    new AsyncDatabaseLookup(),
    5000,               // Timeout: 5 seconds
    TimeUnit.MILLISECONDS,
    100                 // Max concurrent requests
);

// Or unordered (higher throughput, no ordering guarantee):
AsyncDataStream.unorderedWait(...);
```

---

## Q72: How would you implement a streaming join between two Kafka topics in Flink?

**Answer:**

**Regular join (requires bounded state):**
```java
// Join orders with payments within 1 hour
DataStream<OrderPayment> joined = orders
    .keyBy(Order::getOrderId)
    .intervalJoin(payments.keyBy(Payment::getOrderId))
    .between(Time.minutes(-5), Time.minutes(60))  // Payment 5min before to 60min after order
    .process(new ProcessJoinFunction<Order, Payment, OrderPayment>() {
        public void processElement(Order order, Payment payment, Context ctx, 
                                    Collector<OrderPayment> out) {
            out.collect(new OrderPayment(order, payment));
        }
    });
```

**Window join:**
```java
orders.join(payments)
    .where(Order::getOrderId)
    .equalTo(Payment::getOrderId)
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .apply((order, payment) -> new OrderPayment(order, payment));
```

**Temporal join (versioned table lookup):**
```sql
-- Join with latest version of customer at the time of order
SELECT o.*, c.name, c.tier
FROM orders o
JOIN customers FOR SYSTEM_TIME AS OF o.order_time AS c
ON o.customer_id = c.customer_id;
```

**Comparison:**
| Join type | State | Use case |
|-----------|-------|----------|
| Interval join | Bounded by interval | Correlate events within time window |
| Window join | Bounded by window | Aggregate matching events per window |
| Temporal join | Versioned table | Lookup dimension at event time |
| Regular join | Unbounded (need TTL!) | Continuous enrichment |

---

## Q73: Your Flink job checkpoint is taking 10 minutes. How do you fix it?

**Answer:**

**Diagnosis:**
```
Flink UI → Checkpoints tab:
  Checkpoint duration: 10 min (target: < 30s)
  Alignment duration: 8 min (barrier alignment taking too long)
  Sync phase: 30s
  Async phase: 2 min
  Checkpoint size: 50 GB
```

**Fixes by root cause:**

**1. Slow alignment (backpressure during checkpoint):**
```yaml
# Enable unaligned checkpoints
execution.checkpointing.unaligned: true
# Barriers skip ahead of buffered data
# Stores in-flight data as part of checkpoint
```

**2. Large state (50 GB):**
```yaml
# Use incremental checkpoints (RocksDB only)
state.backend: rocksdb
state.backend.incremental: true
# Only uploads changed SST files (not entire state)
# Reduces checkpoint size from 50GB to ~5GB
```

**3. Slow checkpoint storage:**
```yaml
# Use faster storage
state.checkpoints.dir: s3://checkpoints/  # Ensure sufficient throughput
# Or: HDFS with local SSD for temp files
state.backend.rocksdb.localdir: /local-ssd/rocksdb/
```

**4. Too many small states (overhead per subtask):**
```
# Reduce parallelism (fewer subtask states to checkpoint)
# Or: Increase checkpoint interval
execution.checkpointing.interval: 5min  # vs 1min
```

**5. State TTL not configured:**
```java
// State growing forever → checkpoint grows forever
// Add TTL to evict old state
StateTtlConfig.newBuilder(Time.hours(24)).build();
```

---

## Q74: Explain Flink's memory model. How do you configure it?

**Answer:**

```
┌──────────────────────────────────────────────────────────────┐
│              FLINK TASKMANAGER MEMORY                          │
│                                                               │
│  Total Process Memory (taskmanager.memory.process.size)       │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ JVM Metaspace (256MB default)                          │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │ JVM Overhead (10% of total, 192MB-1GB)                 │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │ Total Flink Memory                                     │  │
│  │ ┌──────────────────────────────────────────────────┐   │  │
│  │ │ Framework Heap (128MB) - Flink internals         │   │  │
│  │ ├──────────────────────────────────────────────────┤   │  │
│  │ │ Framework Off-Heap (128MB) - Flink internals     │   │  │
│  │ ├──────────────────────────────────────────────────┤   │  │
│  │ │ Task Heap - User code objects                    │   │  │
│  │ │ (taskmanager.memory.task.heap.size)              │   │  │
│  │ ├──────────────────────────────────────────────────┤   │  │
│  │ │ Task Off-Heap - Native memory, RocksDB          │   │  │
│  │ │ (taskmanager.memory.task.off-heap.size)          │   │  │
│  │ ├──────────────────────────────────────────────────┤   │  │
│  │ │ Network Memory (10% of Flink memory)            │   │  │
│  │ │ Network buffers for shuffle                      │   │  │
│  │ ├──────────────────────────────────────────────────┤   │  │
│  │ │ Managed Memory (40% of Flink memory)            │   │  │
│  │ │ - RocksDB state backend                         │   │  │
│  │ │ - Batch sort/hash operations                    │   │  │
│  │ │ - Python processes                              │   │  │
│  │ └──────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘

Configuration example:
  taskmanager.memory.process.size: 8GB
  taskmanager.memory.managed.fraction: 0.4  (3.2GB for RocksDB)
  taskmanager.memory.network.fraction: 0.1
  taskmanager.memory.task.heap.size: 2GB
  state.backend.rocksdb.memory.managed: true  (RocksDB uses managed memory)
```

---

## Q75: How do you scale a Flink job without losing state?

**Answer:**

**Rescaling with savepoint:**
```bash
# 1. Take savepoint
flink savepoint <job-id> s3://savepoints/

# 2. Cancel job
flink cancel <job-id>

# 3. Restart with new parallelism
flink run -s s3://savepoints/savepoint-xyz -p 20 my-job.jar
# Changed from parallelism 10 → 20
```

**How state redistribution works:**
```
Keyed state: Redistributed by key groups
  Flink divides key space into max-parallelism groups
  Groups reassigned to new subtasks
  
  Old: 10 subtasks, each owns ~13 key groups (128 total)
  New: 20 subtasks, each owns ~6 key groups
  
  Key groups are atomic units of redistribution
  → Some subtasks give away key groups, others receive
  → No key is split across subtasks

Operator state: Redistributed via:
  - Even-split: List split evenly across new subtasks
  - Union: Each subtask gets full list (for broadcast-like state)
```

**Reactive scaling (Flink 1.13+):**
```yaml
# Flink auto-adjusts parallelism based on available TaskManagers
scheduler-mode: reactive
# Add TMs → Flink automatically rescales job
# Remove TMs → Flink automatically rescales down
# No manual savepoint/restart needed!
```

---

## Q76: Compare Flink vs Spark Structured Streaming for a real-time pipeline.

**Answer:**

| Aspect | Flink | Spark Structured Streaming |
|--------|-------|---------------------------|
| Model | True stream (record-at-a-time) | Micro-batch (default) |
| Latency | Milliseconds | Seconds (100ms best case) |
| State | First-class (RocksDB, TB-scale) | Limited (HDFS-backed) |
| Checkpointing | Async barriers (Chandy-Lamport) | End-of-batch snapshot |
| Exactly-once | Native (2PC sinks) | Via idempotent sinks |
| Event time | Advanced (watermarks, late data) | Watermarks (simpler) |
| CEP | Built-in library | Not native |
| SQL | Full streaming SQL | Streaming SQL |
| Backpressure | Credit-based (propagates) | Micro-batch (natural bound) |
| Rescaling | Savepoint + key groups | Checkpoint + restart |
| Ecosystem | Standalone, YARN, K8s | Part of Spark ecosystem |
| Batch | Supported (but Spark is better) | Native (same engine) |
| Community | Growing fast | Very large |
| Operations | More complex (dedicated cluster) | Easier (Spark infra) |

**Choose Flink:**
- Sub-second latency requirements
- Complex event processing
- Very large state (TB)
- Advanced event-time semantics
- True streaming (not micro-batch)

**Choose Spark SS:**
- Unified batch + stream
- Team already knows Spark
- Latency > 1 second acceptable
- Simpler operational model
- Rich ML integration (MLlib)

---

## Q77: How do you implement a streaming deduplication in Flink?

**Answer:**

```java
public class DeduplicationFunction 
    extends KeyedProcessFunction<String, Event, Event> {
    
    // State: Have we seen this event?
    private ValueState<Boolean> seen;
    
    @Override
    public void open(Configuration params) {
        ValueStateDescriptor<Boolean> desc = new ValueStateDescriptor<>(
            "seen", Boolean.class);
        
        // TTL: Forget events after 24 hours
        StateTtlConfig ttl = StateTtlConfig
            .newBuilder(Time.hours(24))
            .setUpdateType(UpdateType.OnCreateAndWrite)
            .cleanupInRocksdbCompactFilter(1000)
            .build();
        desc.enableTimeToLive(ttl);
        
        seen = getRuntimeContext().getState(desc);
    }
    
    @Override
    public void processElement(Event event, Context ctx, Collector<Event> out) 
        throws Exception {
        if (seen.value() == null) {
            // First time seeing this key → emit
            seen.update(true);
            out.collect(event);
        }
        // Duplicate → drop silently
    }
}

// Usage:
stream
    .keyBy(Event::getDeduplicationKey)  // Key by unique event ID
    .process(new DeduplicationFunction())
    .addSink(outputSink);
```

**SQL approach:**
```sql
SELECT *
FROM (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_time) AS row_num
    FROM events
)
WHERE row_num = 1;
-- Flink translates this to stateful deduplication
```

---

## Q78: Explain Flink's savepoint vs checkpoint. When to use each?

**Answer:**

| Aspect | Checkpoint | Savepoint |
|--------|-----------|-----------|
| Trigger | Automatic (periodic) | Manual (operator action) |
| Purpose | Failure recovery | Planned operations |
| Lifecycle | Auto-deleted when superseded | Kept until manually deleted |
| Format | Backend-specific (optimized) | Canonical format (portable) |
| Incremental | Yes (RocksDB) | Always full |
| Use case | Crash recovery | Upgrade, rescale, A/B test |
| Cost | Low (incremental) | Higher (full snapshot) |
| Portability | Same job only | Different job version OK |

**When to use savepoint:**
- Application upgrade (new business logic)
- Flink version upgrade
- Change parallelism
- A/B testing (fork state to two job variants)
- Bug fix deployment
- Cluster migration

**When checkpoint is sufficient:**
- Normal crash recovery
- TaskManager restarts
- Network failures

---

## Q79: How do you monitor a Flink application in production?

**Answer:**

**Key metrics to monitor:**

```
THROUGHPUT:
  numRecordsInPerSecond / numRecordsOutPerSecond (per operator)
  numBytesInPerSecond / numBytesOutPerSecond
  Alert: Drop > 50% from baseline

LATENCY:
  latency.source.id.operator.id.operator_subtask_index.latency
  (end-to-end event processing latency)
  Alert: p99 > SLA threshold

CHECKPOINT:
  lastCheckpointDuration: Time to complete last checkpoint
  lastCheckpointSize: Bytes checkpointed
  numberOfFailedCheckpoints: Failed checkpoints (state at risk!)
  Alert: Failed checkpoints > 0, duration > 2x normal

BACKPRESSURE:
  backPressuredTimeMsPerSecond (per operator)
  Alert: > 500ms/sec sustained

STATE:
  State size per operator (growing unbounded?)
  RocksDB compaction metrics
  Alert: State growth > expected rate

RESOURCE:
  JVM heap used / committed
  GC time per second
  CPU utilization
  Network buffer usage
  Alert: Heap > 85%, GC > 10%

KAFKA (if source):
  Consumer lag (records-lag-max)
  Alert: Lag increasing over 5 min window
```

**Monitoring stack:**
```
Flink → Prometheus (metrics reporter)
     → Grafana (dashboards)
     → PagerDuty (alerts)

Configuration:
  metrics.reporter.prom.class: org.apache.flink.metrics.prometheus.PrometheusReporter
  metrics.reporter.prom.port: 9249
```

---

## Q80: Design a real-time analytics pipeline: page views → real-time dashboard with 1-second freshness.

**Answer:**

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Web App  │───▶│  Kafka   │───▶│  Flink   │───▶│  Redis / │───▶│Dashboard │
│ (events) │    │          │    │          │    │  Druid   │    │(Grafana) │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘

Flink job:
```

```java
// Real-time pageview analytics
DataStream<PageView> pageviews = env
    .addSource(new FlinkKafkaConsumer<>("pageviews", schema, kafkaProps))
    .assignTimestampsAndWatermarks(
        WatermarkStrategy.<PageView>forBoundedOutOfOrderness(Duration.ofSeconds(3))
            .withTimestampAssigner((pv, ts) -> pv.getTimestamp()));

// Metric 1: Pageviews per second (1-second tumbling window)
pageviews
    .windowAll(TumblingEventTimeWindows.of(Time.seconds(1)))
    .aggregate(new CountAggregate())
    .addSink(new RedisSink<>("pageviews:per_second"));

// Metric 2: Top pages (sliding window, 5 min, slide 10s)
pageviews
    .keyBy(PageView::getPageUrl)
    .window(SlidingEventTimeWindows.of(Time.minutes(5), Time.seconds(10)))
    .aggregate(new CountAggregate())
    .keyBy(x -> "global")
    .process(new TopNFunction(10))  // Keep top 10
    .addSink(new RedisSink<>("top_pages:5min"));

// Metric 3: Unique visitors (HyperLogLog approximate)
pageviews
    .keyBy(x -> "global")
    .window(TumblingEventTimeWindows.of(Time.minutes(1)))
    .aggregate(new HLLAggregate())  // HyperLogLog for distinct count
    .addSink(new RedisSink<>("unique_visitors:per_minute"));

// Metric 4: Real-time session detection
pageviews
    .keyBy(PageView::getUserId)
    .window(EventTimeSessionWindows.withGap(Time.minutes(30)))
    .process(new SessionWindowFunction())
    .addSink(new KafkaSink<>("user_sessions"));
```

---

## Q81: What is Flink CDC? How does it differ from Debezium + Kafka approach?

**Answer:**

**Debezium + Kafka (traditional):**
```
Database → Debezium → Kafka → Flink → Sink
  4 components, 3 network hops
  + Kafka provides buffering, replay, multi-consumer
  + Mature, widely adopted
  - More infrastructure to manage
  - Higher latency (hop through Kafka)
```

**Flink CDC (direct):**
```
Database → Flink CDC Source → Flink → Sink
  2 components, direct read from binlog/WAL
  + Lower latency (no Kafka in between)
  + Simpler architecture
  + Full Flink SQL integration
  - No replay buffer (if Flink fails, must re-snapshot)
  - Single consumer (vs Kafka multi-consumer)
```

```sql
-- Flink CDC SQL example
CREATE TABLE orders_cdc (
    order_id INT,
    amount DECIMAL(10,2),
    status STRING,
    updated_at TIMESTAMP(3),
    PRIMARY KEY (order_id) NOT ENFORCED
) WITH (
    'connector' = 'mysql-cdc',
    'hostname' = 'mysql-host',
    'port' = '3306',
    'username' = 'cdc_user',
    'password' = '...',
    'database-name' = 'orders_db',
    'table-name' = 'orders'
);

-- Materialize CDC stream to Iceberg
INSERT INTO iceberg_orders
SELECT * FROM orders_cdc;
-- Automatically handles INSERT, UPDATE, DELETE events
```

**When to use Flink CDC directly:**
- Simple pipeline (source → transform → sink)
- Lowest latency required
- Don't need Kafka's multi-consumer replay

**When to use Debezium + Kafka:**
- Multiple consumers need same CDC stream
- Need replay capability
- Already have Kafka infrastructure
- Need decoupling between source and sink

---

## Q82: How do you implement a streaming aggregation with retraction in Flink SQL?

**Answer:**

```sql
-- Retraction example: Running count per category

-- Input stream (append-only):
-- +I [order1, electronics, 100]
-- +I [order2, electronics, 200]
-- +I [order3, books, 50]

SELECT category, COUNT(*) as order_count, SUM(amount) as total
FROM orders
GROUP BY category;

-- Output changelog stream:
-- +I [electronics, 1, 100]      (first electronics order)
-- -U [electronics, 1, 100]      (retract old result)
-- +U [electronics, 2, 300]      (emit new result)
-- +I [books, 1, 50]             (first books order)

-- RETRACTION:
-- -U means "previous result was wrong, here's the correction"
-- Downstream operators use retractions to maintain correct state

-- For Kafka sink (append-only), use upsert mode:
CREATE TABLE result_sink (
    category STRING,
    order_count BIGINT,
    total DECIMAL(10,2),
    PRIMARY KEY (category) NOT ENFORCED
) WITH (
    'connector' = 'upsert-kafka',
    'topic' = 'category-stats',
    'key.format' = 'json',
    'value.format' = 'json',
    'properties.bootstrap.servers' = 'broker:9092'
);
-- Upsert-kafka: latest value per key (compacted topic)
```

---

## Q83: What is the difference between keyed state and operator state?

**Answer:**

**Keyed state:** Partitioned by key. Each key has its own state instance.
```java
// Only accessible in keyed context (after keyBy())
stream.keyBy(Event::getUserId)
      .process(new KeyedProcessFunction<>() {
          ValueState<Integer> count;  // Per USER state
          // user_A has count=5, user_B has count=3
      });

// Redistributed on rescale by key groups
// Types: ValueState, ListState, MapState, ReducingState, AggregatingState
```

**Operator state:** Not partitioned by key. One state per operator subtask.
```java
// Accessible in non-keyed context (e.g., source operators)
public class MySource extends RichSourceFunction<String>
    implements CheckpointedFunction {
    
    private ListState<Long> offsetState;  // Per SUBTASK state
    
    @Override
    public void snapshotState(FunctionSnapshotContext ctx) {
        offsetState.clear();
        offsetState.add(currentOffset);
    }
    
    @Override
    public void initializeState(FunctionInitializationContext ctx) {
        offsetState = ctx.getOperatorStateStore()
            .getListState(new ListStateDescriptor<>("offsets", Long.class));
    }
}

// Redistribution on rescale:
// Even-split: List divided evenly among new subtasks
// Union: Each subtask gets full list (for broadcast state)
```

**Broadcast state:** Special operator state replicated to all subtasks.
```java
// Pattern: Dynamic rules/config broadcast to all processing subtasks
BroadcastStream<Rule> rules = rulesStream
    .broadcast(new MapStateDescriptor<>("rules", String.class, Rule.class));

events.connect(rules)
    .process(new BroadcastProcessFunction<>() {
        // processBroadcastElement: Update rules in broadcast state
        // processElement: Apply current rules to each event
    });
```

---

## Q84: How do you handle schema evolution in a long-running Flink job?

**Answer:**

**Challenge:** Flink jobs run for months/years. Source schemas change. State schemas need updating.

**Source schema evolution:**
```java
// Option 1: Use Avro with schema registry (automatic evolution)
FlinkKafkaConsumer<GenericRecord> consumer = new FlinkKafkaConsumer<>(
    "orders",
    ConfluentRegistryAvroDeserializationSchema.forGeneric(schema, registryUrl),
    props);
// New fields added → GenericRecord has them, old code ignores
// Fields removed → GenericRecord returns null, handle gracefully

// Option 2: Lenient JSON deserialization
// Parse JSON loosely, handle missing/extra fields in code
ObjectMapper mapper = new ObjectMapper()
    .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
```

**State schema evolution:**
```java
// Flink supports state schema evolution for:
// - POJO types (add/remove fields with defaults)
// - Avro types (following Avro evolution rules)
// - NOT supported: Kryo, raw types

// POJO evolution example:
// v1: class UserState { String name; int age; }
// v2: class UserState { String name; int age; String email = ""; }
// → Restore from v1 savepoint with v2 code works (email defaults to "")

// For incompatible changes: Use State Processor API
// Read old state → transform → write new savepoint
```

---

## Q85: Design a streaming pipeline that joins a high-volume click stream with a slowly-changing user profile table.

**Answer:**

```java
// Approach: Temporal join (lookup profile version at event time)

// Click stream: 1M events/sec from Kafka
DataStream<ClickEvent> clicks = env
    .addSource(kafkaSource)
    .assignTimestampsAndWatermarks(...);

// User profiles: CDC from PostgreSQL (slow changes, ~100 updates/sec)
DataStream<UserProfile> profiles = env
    .addSource(new FlinkCDCSource<>(postgresConfig))
    .assignTimestampsAndWatermarks(...);

// Convert profiles to a temporal table (versioned by time)
Table profileTable = tableEnv.fromDataStream(profiles,
    $("user_id"), $("name"), $("tier"), $("updated_at").rowtime());

tableEnv.createTemporaryView("profiles", profileTable);
tableEnv.createTemporaryView("clicks", 
    tableEnv.fromDataStream(clicks));

// Temporal join: Get profile AS OF click time
Table enriched = tableEnv.sqlQuery("""
    SELECT c.*, p.name, p.tier
    FROM clicks c
    JOIN profiles FOR SYSTEM_TIME AS OF c.event_time AS p
    ON c.user_id = p.user_id
""");

// Alternative: Broadcast join (if profiles fit in memory)
// Broadcast all profiles to all subtasks
// Pro: No state per click event
// Con: Profiles must fit in memory (< 1GB typically)

MapStateDescriptor<String, UserProfile> profileState = 
    new MapStateDescriptor<>("profiles", String.class, UserProfile.class);
BroadcastStream<UserProfile> broadcastProfiles = 
    profiles.broadcast(profileState);

clicks.connect(broadcastProfiles)
    .process(new BroadcastProcessFunction<>() {
        @Override
        public void processElement(ClickEvent click, ReadOnlyContext ctx, 
                                    Collector<EnrichedClick> out) {
            UserProfile profile = ctx.getBroadcastState(profileState)
                .get(click.getUserId());
            out.collect(new EnrichedClick(click, profile));
        }
        
        @Override
        public void processBroadcastElement(UserProfile profile, Context ctx,
                                             Collector<EnrichedClick> out) {
            ctx.getBroadcastState(profileState)
                .put(profile.getUserId(), profile);
        }
    });
```

---

## Q86: What are the common pitfalls when deploying Flink in production?

**Answer:**

**1. No operator UIDs:**
```java
// BAD: No UIDs → state lost on any topology change
stream.map(x -> x).keyBy(...).sum("amount").addSink(sink);

// GOOD: Explicit UIDs on ALL stateful operators
stream.map(x -> x).uid("passthrough")
    .keyBy(...).sum("amount").uid("revenue-sum")
    .addSink(sink).uid("output-sink");
```

**2. Unbounded state growth:**
```java
// BAD: State grows forever (one entry per unique key, never cleaned)
stream.keyBy(Event::getUserId)
    .process(new StatefulFunction());  // No TTL → OOM eventually

// GOOD: Configure state TTL
StateTtlConfig.newBuilder(Time.days(7)).build();
```

**3. Wrong checkpoint interval:**
```
Too frequent (1s): High overhead, degraded throughput
Too infrequent (30min): Long recovery time, more reprocessing

Sweet spot: 1-5 minutes for most workloads
Also set: min pause between checkpoints = 30s
```

**4. Insufficient checkpoint timeout:**
```yaml
# If checkpoint takes longer than timeout → cancelled → next one starts → cascade
execution.checkpointing.timeout: 10min  # Must be >> normal checkpoint duration
```

**5. Not handling backpressure:**
```
Symptom: Checkpoints timeout, lag increases, eventually OOM
Fix: Scale bottleneck operator, use async I/O, optimize state access
```

**6. Serialization issues:**
```java
// BAD: Non-serializable objects in operator
public class MyFunction extends RichMapFunction<Event, Event> {
    private DatabaseConnection conn;  // Not serializable!
    // Solution: Initialize in open(), mark transient
    private transient DatabaseConnection conn;
    
    @Override
    public void open(Configuration params) {
        conn = new DatabaseConnection(config);
    }
}
```

---

## Q87: How does Flink handle exactly-once when writing to a database?

**Answer:**

**Option 1: Idempotent writes (simplest):**
```java
// Use UPSERT (INSERT ON CONFLICT UPDATE)
// If Flink replays data → same keys overwritten → same result
jdbcSink = JdbcSink.sink(
    "INSERT INTO results (id, value) VALUES (?, ?) ON CONFLICT (id) DO UPDATE SET value = ?",
    (ps, record) -> {
        ps.setString(1, record.getId());
        ps.setDouble(2, record.getValue());
        ps.setDouble(3, record.getValue());
    },
    jdbcExecutionOptions, jdbcConnectionOptions);
```

**Option 2: Two-phase commit (2PC):**
```java
// Custom TwoPhaseCommitSinkFunction
public class ExactlyOnceDatabaseSink 
    extends TwoPhaseCommitSinkFunction<Record, Connection, Void> {
    
    @Override
    protected Connection beginTransaction() {
        Connection conn = dataSource.getConnection();
        conn.setAutoCommit(false);  // Start transaction
        return conn;
    }
    
    @Override
    protected void invoke(Connection txn, Record record, Context ctx) {
        // Write to DB within transaction (not committed yet)
        PreparedStatement ps = txn.prepareStatement("INSERT ...");
        ps.execute();
    }
    
    @Override
    protected void preCommit(Connection txn) {
        // Flush any buffers, validate
        txn.flush();
    }
    
    @Override
    protected void commit(Connection txn) {
        txn.commit();  // Called only after checkpoint completes
        txn.close();
    }
    
    @Override
    protected void abort(Connection txn) {
        txn.rollback();  // Called on failure
        txn.close();
    }
}
```

**Option 3: Write-ahead log (WAL):**
- Buffer writes in Flink state
- On checkpoint complete → flush buffer to database
- On failure → discard uncommitted buffer, replay from checkpoint
- Pro: Works with any database
- Con: Higher latency (data visible only after checkpoint)

---

## Q88: How do you test a Flink application?

**Answer:**

```java
// Unit test with MiniCluster
@ExtendWith(MiniClusterExtension.class)
public class OrderProcessingTest {
    
    @Test
    void testOrderEnrichment() throws Exception {
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);
        
        // Create test input
        DataStream<Order> input = env.fromElements(
            new Order("o1", "c1", 100.0),
            new Order("o2", "c2", 200.0)
        );
        
        // Apply business logic
        DataStream<EnrichedOrder> result = OrderPipeline.process(input);
        
        // Collect results
        List<EnrichedOrder> output = new ArrayList<>();
        result.addSink(new CollectSink<>(output));
        env.execute();
        
        // Assert
        assertEquals(2, output.size());
        assertEquals(110.0, output.get(0).getTotalWithTax());  // 100 + 10% tax
    }
}

// Testing with test harnesses (stateful operators)
@Test
void testDeduplication() throws Exception {
    OneInputStreamOperatorTestHarness<Event, Event> harness = 
        new KeyedOneInputStreamOperatorTestHarness<>(
            new KeyedProcessOperator<>(new DeduplicationFunction()),
            Event::getId, Types.STRING);
    
    harness.open();
    
    // Process elements
    harness.processElement(new StreamRecord<>(event1, 1000L));
    harness.processElement(new StreamRecord<>(event1, 2000L));  // Duplicate
    harness.processElement(new StreamRecord<>(event2, 3000L));
    
    // Verify output
    assertEquals(2, harness.getOutput().size());  // event1 + event2 (no dup)
    
    harness.close();
}

// Integration test with embedded Kafka
@Test
void testEndToEnd() {
    // Use testcontainers for Kafka + database
    KafkaContainer kafka = new KafkaContainer(...);
    PostgreSQLContainer postgres = new PostgreSQLContainer(...);
    
    // Produce test events
    produceEvents(kafka, testEvents);
    
    // Run Flink job
    FlinkJob.run(kafka.getBootstrapServers(), postgres.getJdbcUrl());
    
    // Verify results in database
    List<Result> results = queryPostgres(postgres);
    assertExpectedResults(results);
}
```

---

## Q89: Explain how Flink handles network shuffles differently from Spark.

**Answer:**

```
SPARK SHUFFLE:
  Stage boundary → ALL map tasks write shuffle files → ALL reduce tasks read
  Blocking: Entire map stage completes before reduce stage starts
  
  Map Task 0: [write all output to disk] ─┐
  Map Task 1: [write all output to disk] ─┼─ Stage Boundary (blocking)
  Map Task 2: [write all output to disk] ─┘
                                           │
  Reduce Task 0: [fetch + merge + process] ◀┘
  
FLINK SHUFFLE:
  Pipelined: Upstream and downstream operators run SIMULTANEOUSLY
  Data flows record-by-record through the pipeline
  
  Source → Map → KeyBy(shuffle) → Aggregate → Sink
  ALL running concurrently, connected by network buffers
  
  Map Task 0 ──buffer──▶ Aggregate Task 0
             ──buffer──▶ Aggregate Task 1
  Map Task 1 ──buffer──▶ Aggregate Task 0
             ──buffer──▶ Aggregate Task 1
  
  No stage boundary! Records flow continuously.
  Backpressure via credit-based flow control.
```

**Implications:**
| Aspect | Spark (Blocking) | Flink (Pipelined) |
|--------|-----------------|-------------------|
| Latency | High (full stage) | Low (per-record) |
| Fault tolerance | Recompute from shuffle files | Recompute from checkpoint |
| Memory | Shuffle on disk (bounded) | Buffers in memory (bounded by credits) |
| Deadlocks | No (sequential stages) | Possible (circular dependencies) |
| Resource | Stages can reuse slots | All operators run simultaneously |

---

## Q90: Design a Flink-based real-time recommendation engine for an e-commerce platform.

**Answer:**

```
┌──────────────────────────────────────────────────────────────────┐
│          REAL-TIME RECOMMENDATION ENGINE (FLINK)                  │
│                                                                    │
│  DATA SOURCES:                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Clicks   │  │ Purchases│  │ Cart     │  │ Product  │        │
│  │ (Kafka)  │  │ (Kafka)  │  │ (Kafka)  │  │ Catalog  │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       └──────────────┴──────────────┴──────────────┘              │
│                              │                                    │
│  ┌───────────────────────────▼───────────────────────────┐       │
│  │                    FLINK JOB                            │       │
│  │                                                         │       │
│  │  1. USER SESSION BUILDER                                │       │
│  │     Session window (30 min gap)                         │       │
│  │     Accumulate: clicks, views, cart adds per session    │       │
│  │     State: user_id → SessionState                       │       │
│  │                                                         │       │
│  │  2. FEATURE COMPUTATION (real-time)                     │       │
│  │     - Recently viewed categories (last 1h)              │       │
│  │     - Purchase history (last 30d from state)            │       │
│  │     - Trending products (global sliding window)         │       │
│  │     - User affinity scores (incrementally updated)      │       │
│  │                                                         │       │
│  │  3. SCORING (model inference)                           │       │
│  │     - Load ML model (updated periodically via broadcast)│       │
│  │     - Score candidate products against user features    │       │
│  │     - Async I/O to feature store for historical features│       │
│  │                                                         │       │
│  │  4. RANKING + FILTERING                                 │       │
│  │     - Apply business rules (no recently purchased)      │       │
│  │     - Diversity (not all same category)                 │       │
│  │     - Personalized ranking                              │       │
│  │                                                         │       │
│  └───────────────────────────┬───────────────────────────┘       │
│                              │                                    │
│  ┌───────────────────────────▼───────────────────────────┐       │
│  │  OUTPUT:                                                │       │
│  │  Redis: user_id → top_10_recommendations (real-time)    │       │
│  │  Kafka: recommendation_events (for tracking/analytics)  │       │
│  │  API: Serve from Redis with < 5ms latency               │       │
│  └─────────────────────────────────────────────────────────┘       │
│                                                                    │
│  Model update pattern:                                            │
│  ML Platform → Train new model → Kafka "model-updates" topic      │
│  Flink broadcast state: All subtasks load new model atomically    │
│  Zero-downtime model swap                                         │
└──────────────────────────────────────────────────────────────────┘
```

```java
// Model broadcast pattern
BroadcastStream<ModelUpdate> modelStream = env
    .addSource(new FlinkKafkaConsumer<>("model-updates", ...))
    .broadcast(new MapStateDescriptor<>("model", Void.class, MLModel.class));

userFeatures.connect(modelStream)
    .process(new BroadcastProcessFunction<UserFeatures, ModelUpdate, Recommendations>() {
        private transient MLModel currentModel;
        
        @Override
        public void processBroadcastElement(ModelUpdate update, Context ctx, 
                                             Collector<Recommendations> out) {
            currentModel = MLModel.load(update.getModelPath());
            ctx.getBroadcastState(modelDescriptor).put(null, currentModel);
        }
        
        @Override
        public void processElement(UserFeatures features, ReadOnlyContext ctx,
                                    Collector<Recommendations> out) {
            MLModel model = ctx.getBroadcastState(modelDescriptor).get(null);
            double[] scores = model.predict(features.toVector());
            out.collect(new Recommendations(features.getUserId(), 
                rankByScore(scores, candidateProducts)));
        }
    });
```
