# Backpressure & Performance Issues (#27-40)

> Backpressure is the most common day-to-day operational issue. Understanding where it originates and how to fix it is essential for maintaining SLAs.

---

## Issue #27: Backpressure from Slow Sink

**Severity**: 🔴 Critical  
**Frequency**: Very High  
**Impact**: End-to-end latency spikes, consumer lag grows, SLA breach

### Symptoms
- All upstream operators show HIGH backpressure
- Sink operator shows `busyTimeMsPerSecond` near 1000
- Source operator `idleTimeMsPerSecond` near 0
- Kafka consumer lag growing linearly

### Root Cause
Sink cannot write fast enough:
- Database connection pool exhausted
- Elasticsearch bulk queue full
- Redis timeout due to network issue
- S3 upload throttled

### Diagnosis
```promql
# Identify bottleneck (last operator with LOW backpressure = problem)
flink_taskmanager_job_task_backPressuredTimeMsPerSecond{task_name=~".*Sink.*"}
flink_taskmanager_job_task_busyTimeMsPerSecond{task_name=~".*Sink.*"}

# Check specific sink metrics
flink_taskmanager_job_task_operator_numRecordsOutPerSecond{operator_name=~".*sink.*"}
```

```bash
# Check downstream system health
# Elasticsearch
curl localhost:9200/_cluster/health?pretty
curl localhost:9200/_cat/thread_pool/write?v

# Redis
redis-cli info clients | grep blocked
redis-cli info stats | grep rejected
```

### Fix
```java
// 1. Increase sink parallelism
sinkStream.addSink(new MySink()).setParallelism(100); // Was 20

// 2. Add async buffering before sink
AsyncDataStream.unorderedWait(
    stream,
    new AsyncDatabaseSink(),
    30, TimeUnit.SECONDS,
    5000  // High capacity buffer
);

// 3. Batch writes to sink
public class BatchingSink extends RichSinkFunction<Record> {
    private List<Record> buffer = new ArrayList<>(BATCH_SIZE);
    
    @Override
    public void invoke(Record value, Context ctx) {
        buffer.add(value);
        if (buffer.size() >= BATCH_SIZE) {
            flushBatch(buffer);
            buffer.clear();
        }
    }
}
```

### Prevention
- Always benchmark sink throughput independently
- Use async sinks with bounded buffers
- Set sink parallelism ≥ source parallelism / fan-in ratio
- Monitor downstream system health separately

---

## Issue #28: Backpressure from Expensive Operator

**Severity**: 🔴 Critical  
**Frequency**: High  
**Impact**: Throughput limited by single slow operator

### Symptoms
- One specific operator shows `busyTimeMsPerSecond` = 1000
- Upstream of that operator: HIGH backpressure
- Downstream of that operator: LOW busy time (idle, waiting)

### Root Cause
Operator doing expensive computation per record:
- Complex regex parsing
- Synchronous HTTP/DB call inside `processElement`
- Expensive serialization/deserialization
- Complex ML model inference
- Large state lookups with poor cache hit rate

### Diagnosis
```bash
# Identify slow operator via flamegraph
# Flink Web UI → Job → Task → Thread → Flame Graph

# Check per-operator throughput
curl http://jobmanager:8081/jobs/<id>/vertices/<vertex-id>/metrics?get=numRecordsInPerSecond

# Profile specific TM
async-profiler -d 30 -f /tmp/flame.html <pid>
```

### Fix
```java
// Option 1: Increase parallelism of slow operator only
expensiveStream
    .setParallelism(200)  // 4x the source parallelism
    .uid("expensive-op");

// Option 2: Make synchronous calls async
AsyncDataStream.unorderedWait(
    stream,
    new AsyncHttpLookup(),
    10, TimeUnit.SECONDS,
    1000
).setParallelism(100);

// Option 3: Pre-compute and cache
private transient LoadingCache<String, Result> cache;

@Override
public void open(Configuration params) {
    cache = CacheBuilder.newBuilder()
        .maximumSize(100_000)
        .expireAfterWrite(5, TimeUnit.MINUTES)
        .build(new CacheLoader<>() {
            public Result load(String key) { return computeExpensive(key); }
        });
}
```

### Prevention
- Profile operators during load testing
- Use Async I/O for any external calls
- Cache expensive computations with TTL
- Consider pre-aggregation to reduce volume before expensive operators

---

## Issue #29: Backpressure Due to Data Skew

**Severity**: 🔴 Critical  
**Frequency**: High  
**Impact**: One subtask at 100% while others idle, wasted resources

### Symptoms
- One subtask of an operator: busy 100%, backpressured
- Other subtasks of same operator: idle 80-90%
- KeyBy causing uneven distribution
- Metrics show uneven `numRecordsIn` across subtasks

### Root Cause
Data is not uniformly distributed across keys:
- One user/account has 1000x more events than average
- Time-based key (e.g., date) causing temporal hotspot
- Null key routing all nulls to same partition
- Hash collision causing multiple popular keys to same subtask

### Diagnosis
```promql
# Compare throughput across subtasks of same operator
flink_taskmanager_job_task_operator_numRecordsInPerSecond{
  operator_name="MyWindow",
  subtask_index=~".*"
}
# Look for one subtask with 10-100x others
```

```java
// Add metrics in your operator to track key distribution
getRuntimeContext().getMetricGroup()
    .counter("records-for-key-" + key.hashCode() % 100);
```

### Fix
```java
// Solution 1: Two-phase aggregation (salt + combine)
// Phase 1: Distribute with salt
stream
    .keyBy(event -> event.getKey() + "_" + ThreadLocalRandom.current().nextInt(10))
    .window(TumblingEventTimeWindows.of(Time.minutes(1)))
    .aggregate(new PreAggregator())  // Partial aggregate per salted key
    .uid("pre-agg")
    
// Phase 2: Combine results by original key
    .keyBy(result -> result.getOriginalKey())
    .window(TumblingEventTimeWindows.of(Time.minutes(1)))
    .aggregate(new FinalAggregator())  // Merge partial results
    .uid("final-agg");

// Solution 2: Local pre-aggregation (mini-batch)
stream
    .keyBy(Event::getKey)
    .process(new LocalPreAggregator())  // Buffer and pre-aggregate locally
    .uid("local-preagg")
    .keyBy(PreAggResult::getKey)
    .window(...)
    .aggregate(...);

// Solution 3: Filter hot keys to dedicated path
SingleOutputStreamOperator<Event> mainStream = stream
    .process(new HotKeyRouter(HOT_KEYS))
    .uid("hot-key-router");

DataStream<Event> hotStream = mainStream.getSideOutput(HOT_KEY_TAG);
// Process hot keys with higher parallelism
hotStream.keyBy(Event::getKey)
    .process(new HotKeyProcessor())
    .setParallelism(50);
```

### Prevention
- Analyze key distribution before deployment
- Add monitoring for per-subtask throughput variance
- Design keys to be uniformly distributed
- Never keyBy on a nullable field without null handling

---

## Issue #30: Hot Key Causing Single Subtask Overload

**Severity**: 🔴 Critical  
**Frequency**: High  
**Impact**: Processing bottleneck, one subtask defines overall throughput

### Symptoms
- Single subtask processing 10-100x more records than peers
- That subtask has huge state, others have tiny state
- Checkpoints take long because of one subtask's state
- Cannot solve by just increasing parallelism (key stays on one subtask)

### Root Cause
Power-law distribution in data:
- E-commerce: Amazon/Walmart account generating 1M events/day
- Social: Celebrity accounts with millions of followers
- IoT: One sensor reporting 1000x more than others
- Gaming: Bot accounts generating artificial traffic

### Diagnosis
```java
// Add to your keyed operator
private transient Counter hotKeyCounter;

@Override
public void processElement(Event e, Context ctx, Collector<Out> out) {
    hotKeyCounter.inc();
    if (hotKeyCounter.getCount() % 1_000_000 == 0) {
        LOG.warn("Hot key detected: {} has processed {}M records", 
            ctx.getCurrentKey(), hotKeyCounter.getCount() / 1_000_000);
    }
}
```

### Fix
See Issue #29 solutions, plus:

```java
// Dynamic hot key detection and splitting
public class DynamicHotKeySplitter extends KeyedProcessFunction<String, Event, Event> {
    private ValueState<Long> counter;
    private static final long HOT_THRESHOLD = 10_000; // per window
    
    @Override
    public void processElement(Event event, Context ctx, Collector<Event> out) {
        long count = counter.value() == null ? 0 : counter.value();
        counter.update(count + 1);
        
        if (count > HOT_THRESHOLD) {
            // Append random suffix to split hot key
            event.setKey(event.getKey() + "_split_" + 
                ThreadLocalRandom.current().nextInt(SPLIT_FACTOR));
        }
        out.collect(event);
    }
}
```

---

## Issue #31: Thread Contention in Operator

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Reduced throughput, increased latency

### Symptoms
- Operator `busyTime` high but throughput low
- CPU usage below expected for given busy time
- Thread dump shows threads in BLOCKED/WAITING state
- Flame graph shows lock contention

### Root Cause
- Shared static resources with synchronization
- Connection pool with insufficient connections
- Synchronized collections (e.g., `Collections.synchronizedMap`)
- Logger contention (synchronous appender)

### Fix
```java
// Bad: Shared synchronized resource
private static final Map<String, Config> SHARED_CONFIG = 
    Collections.synchronizedMap(new HashMap<>());  // Contention!

// Good: Per-instance or thread-local
private transient Map<String, Config> localConfig;

@Override
public void open(Configuration params) {
    localConfig = new HashMap<>(sharedConfig);  // Local copy, no contention
}

// Good: Use concurrent data structures
private transient ConcurrentHashMap<String, Config> concurrentConfig;
```

### Prevention
- Never use synchronized collections in operators
- Use per-instance (transient) resources, not static shared
- Use async logging (log4j2 AsyncAppender)
- Profile under load to catch contention early

---

## Issue #32: Serialization Overhead Dominating CPU

**Severity**: 🟡 Warning  
**Frequency**: Medium-High  
**Impact**: Throughput 2-5x lower than expected

### Symptoms
- CPU usage high but effective throughput low
- Flame graph shows > 40% time in serialization
- Between operators: data serialized and deserialized unnecessarily
- Kryo serializer being used (slow fallback)

### Root Cause
Flink serializes data at:
- Network shuffle boundaries (between operators on different TMs)
- State access (read/write from RocksDB)
- Checkpoint creation

Slow serialization happens with:
- Kryo fallback (generic, reflection-based, slow)
- Complex nested objects
- Operator chaining broken unnecessarily

### Diagnosis
```bash
# Check for Kryo fallback warnings
grep "Kryo\|GenericType" jobmanager.log

# Profile serialization time
async-profiler -e wall -d 30 -f /tmp/flame.html <pid>
# Look for: TypeSerializer.serialize, Kryo.writeObject, RocksDB.get
```

### Fix
```java
// 1. Register custom serializers (avoid Kryo)
env.getConfig().registerTypeWithKryoSerializer(MyClass.class, MySerializer.class);

// 2. Better: Use POJOs (Flink's efficient serializer auto-detects)
// Requirements: public class, public no-arg constructor, all fields public or have getters/setters
public class MyEvent {
    public String userId;
    public long timestamp;
    public double amount;
    // Flink auto-generates efficient serializer!
}

// 3. Best: Use Flink's TypeInformation
env.getConfig().disableGenericTypes();  // Fail fast if Kryo would be used

// 4. Enable object reuse (skip serialization between chained operators)
env.getConfig().enableObjectReuse();
```

```yaml
# Ensure operator chaining is not disabled unnecessarily
pipeline.operator-chaining: true  # Default, but check it's not overridden
```

### Prevention
- Always call `env.getConfig().disableGenericTypes()` in production
- Use POJOs or Avro/Protobuf with generated serializers
- Keep operator chaining enabled
- Profile serialization in load tests

---

## Issue #33: Event Time Skew Causing Processing Delay

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Increased state size, delayed window results

### Symptoms
- Windows fire late (much after expected real time)
- State grows because events arrive far in the past
- Watermark is held back by slow sources
- Dashboard shows stale data despite high throughput

### Root Cause
One source partition has events much older than others:
- Source replay (catching up from offset 0)
- One producer lagging (network issues)
- Clock skew between producers
- Watermark = min(all partition watermarks), so slowest partition dominates

### Fix
```java
// Enable idle source marking
WatermarkStrategy.<Event>forBoundedOutOfOrderness(Duration.ofSeconds(30))
    .withIdleness(Duration.ofMinutes(2))  // Mark partition idle after 2 min of no data
    .withTimestampAssigner((event, ts) -> event.getTimestamp());

// Per-partition watermarks with alignment
env.getConfig().setAutoWatermarkInterval(200);

// Split fast and slow streams
// Fast path: current data → real-time processing
// Slow path: replay data → separate job, backfill
```

### Prevention
- Always configure `.withIdleness()` for multi-partition sources
- Monitor per-partition watermark lag
- Separate replay/backfill from real-time processing

---

## Issue #34: Record De/Serialization for RocksDB Becoming Bottleneck

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: State access latency high, reduced throughput

### Symptoms
- RocksDB state access latency > 1ms per operation
- CPU flame graph shows time in state serializer
- Happens with complex state objects (deep nesting, large collections)

### Root Cause
Every RocksDB state access requires:
- Key serialization → byte[]
- Value serialization → byte[] (on write)
- Key deserialization ← byte[] (on read)
- Value deserialization ← byte[] (on read)

For complex objects, this dominates processing time.

### Fix
```java
// Bad: Complex nested state
ValueState<Map<String, List<ComplexObject>>> state; // Expensive ser/de

// Good: Use MapState (only serializes accessed key)
MapState<String, ComplexObject> state;  // Only accessed entries serialized

// Good: Flatten complex objects
public class FlatState {
    public long count;
    public double sum;
    public long lastTimestamp;
    // Simple fields = fast serialization
}

// Good: Use primitive state where possible
ValueState<Long> countState;   // Fastest possible
ValueState<Double> sumState;
```

### Prevention
- Keep state objects flat and simple
- Use `MapState` instead of `ValueState<Map<>>`
- Use `ListState` instead of `ValueState<List<>>`
- Benchmark state access latency during development

---

## Issue #35: Checkpoint Alignment Causing Latency Spike

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Periodic latency spikes aligned with checkpoint interval

### Symptoms
- Latency spikes every N minutes (= checkpoint interval)
- Spike duration increases with skew between source partitions
- One input channel blocked while waiting for barrier from other channel

### Root Cause
Aligned checkpoints block one input channel while waiting for barriers from all channels to arrive at an operator. If channels have different speeds:

```
Channel 1: [data][data][BARRIER][data]...  ← arrived, channel blocked
Channel 2: [data][data][data][data][data]... ← still processing, barrier not here yet
                                              Channel 1 blocked for entire time!
```

### Fix
```yaml
# Option 1: Enable unaligned checkpoints (recommended)
execution.checkpointing.unaligned.enabled: true

# Option 2: Increase buffer-debloating (reduces buffered data = faster barrier propagation)
taskmanager.network.memory.buffer-debloat.enabled: true
taskmanager.network.memory.buffer-debloat.target: 1000  # 1 second of data buffered
```

### Prevention
- Enable unaligned checkpoints for latency-sensitive jobs
- Enable buffer debloating to reduce data in-flight
- Monitor `checkpointAlignmentTime` metric

---

## Issue #36: Processing Time Skew in Windowed Operations

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Some subtasks finish window processing before others, idle time

### Symptoms
- Window aggregation subtasks have very different `busyTime`
- Some subtasks idle waiting for watermark while others busy
- End-to-end latency high due to stragglers

### Fix
```java
// Use rebalance() before window to distribute evenly
stream
    .rebalance()  // Round-robin distribution
    .keyBy(Event::getKey)
    .window(TumblingEventTimeWindows.of(Time.minutes(1)))
    .aggregate(new MyAggregator());

// Or use rescale() for better locality (same TM)
stream.rescale().keyBy(...).window(...).aggregate(...);
```

---

## Issue #37: Operator Chain Breaking Unintentionally

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Unnecessary network shuffle, increased latency and CPU

### Symptoms
- Web UI shows operators in separate boxes (not chained)
- Network bytes between operators on same TM is non-zero
- More network buffers consumed than expected

### Root Cause
Chaining breaks when:
1. Different parallelism between operators
2. `disableChaining()` called explicitly
3. Different slot sharing groups
4. `rebalance()`, `rescale()`, `keyBy()`, `broadcast()` between operators
5. Different resource profiles

### Diagnosis
```bash
# Check job plan for operator chains
curl http://jobmanager:8081/jobs/<job-id>/plan | jq '.nodes[].parallelism'

# Look for broken chains in Web UI
# Chained operators show in same box
# Unchained operators in separate boxes with lines between them
```

### Fix
```java
// Ensure same parallelism for operators you want chained
source.map(new MyMapper()).setParallelism(64)      // Same
      .filter(new MyFilter()).setParallelism(64)    // Same → chained!
      .keyBy(...)  // This naturally breaks chain (different partitioning)
      .process(new MyProcess()).setParallelism(128);

// Don't break chains unnecessarily
stream.map(x -> transform(x))
    // .disableChaining()  // DON'T do this without good reason
    .filter(x -> x != null);
```

### Prevention
- Keep parallelism same for operators that should chain
- Only use `disableChaining()` for debugging
- Review job plan in Web UI before deploying

---

## Issue #38: Async I/O Timeout Causing Backpressure

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Effective parallelism reduced, throughput drops

### Symptoms
- Async I/O operator shows low throughput despite high capacity
- Timeout exceptions in logs
- External service latency spikes causing cascade
- `asyncOperatorBufferSize` reaching capacity

### Root Cause
When async requests timeout:
1. Capacity slot is consumed until timeout fires
2. If many concurrent requests timeout, buffer fills up
3. When buffer is full, operator blocks (becomes synchronous)
4. Backpressure propagates upstream

### Fix
```java
// Increase timeout capacity and add circuit breaker
AsyncDataStream.unorderedWait(
    stream,
    new AsyncDatabaseRequest() {
        @Override
        public void asyncInvoke(Event event, ResultFuture<Result> future) {
            // Add circuit breaker
            if (circuitBreaker.isOpen()) {
                future.complete(Collections.singleton(defaultResult(event)));
                return;
            }
            
            CompletableFuture<Result> dbFuture = asyncClient.query(event);
            dbFuture.whenComplete((result, throwable) -> {
                if (throwable != null) {
                    circuitBreaker.recordFailure();
                    future.complete(Collections.singleton(defaultResult(event)));
                } else {
                    circuitBreaker.recordSuccess();
                    future.complete(Collections.singleton(result));
                }
            });
        }
        
        @Override
        public void timeout(Event event, ResultFuture<Result> future) {
            // Return default on timeout instead of failing
            circuitBreaker.recordFailure();
            future.complete(Collections.singleton(defaultResult(event)));
        }
    },
    30, TimeUnit.SECONDS,   // Timeout
    2000                     // Capacity (higher = more in-flight)
);
```

### Prevention
- Implement circuit breaker pattern for external calls
- Return defaults on timeout (don't fail the record)
- Set capacity = expected_latency_ms × expected_throughput / 1000
- Monitor async operator buffer utilization

---

## Issue #39: Task Scheduling Delay on Cluster Startup

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Job takes minutes to start after submit

### Symptoms
- Job stays in CREATED/SCHEDULED state for minutes
- TaskManagers registering slowly
- Slot allocation takes long
- K8s pods pending (insufficient resources)

### Root Cause
1. TaskManager pods not yet scheduled (K8s resource pressure)
2. Slot allocation waiting for TM registration
3. Too many jobs competing for limited slots
4. PVC provisioning for state storage taking time

### Fix
```yaml
# Pre-warm TaskManagers (keep running even without jobs)
kubernetes.taskmanager.replicas: 10  # Keep 10 TMs warm

# Faster TM registration
resourcemanager.taskmanager-timeout: 60000  # 1 min timeout

# Use pod priority for streaming jobs
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: flink-streaming-high
value: 1000000
globalDefault: false
description: "High priority for Flink streaming jobs"
```

### Prevention
- Keep buffer TaskManagers running (warm pool)
- Use PriorityClass for critical streaming jobs
- Pre-provision PVCs with StorageClass volumeBindingMode: Immediate
- Monitor slot availability vs demand

---

## Issue #40: Source Reading Faster Than Processing (Unbounded Buffering)

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Memory growth, increased checkpoint size, GC pressure

### Symptoms
- Source `numRecordsIn` >> downstream operator `numRecordsIn`
- Network buffers filling up
- In-flight data growing (backPressuredTime on source is 0 but downstream is high)

### Root Cause
Source reads faster than downstream can process. Without backpressure reaching source (due to buffering), source keeps reading and buffering data. This creates:
- Memory pressure from buffered records
- Larger checkpoints (in-flight data stored in unaligned checkpoints)
- Higher end-to-end latency

### Fix
```yaml
# Enable buffer debloating (Flink 1.14+)
taskmanager.network.memory.buffer-debloat.enabled: true
taskmanager.network.memory.buffer-debloat.target: 1000  # Target 1s of buffered data

# Limit source read rate
# For Kafka source:
connector.source.rate-limit: 50000  # Max records/sec per subtask
```

```java
// Custom rate limiter in source
public class RateLimitedSource extends RichSourceFunction<Event> {
    private final RateLimiter rateLimiter = RateLimiter.create(100_000); // 100K/sec
    
    @Override
    public void run(SourceContext<Event> ctx) {
        while (running) {
            rateLimiter.acquire();
            ctx.collect(readNext());
        }
    }
}
```

### Prevention
- Always enable buffer debloating for streaming jobs
- Set source rate limits during catch-up scenarios
- Monitor buffer utilization percentage
- Size downstream parallelism to match source throughput
