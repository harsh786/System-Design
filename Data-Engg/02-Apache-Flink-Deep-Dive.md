# Apache Flink - Staff Architect Deep Dive

## Table of Contents
1. [Architecture](#1-architecture)
2. [Execution Model](#2-execution-model)
3. [State Management](#3-state-management)
4. [Checkpointing](#4-checkpointing)
5. [Savepoints](#5-savepoints)
6. [Watermarks](#6-watermarks)
7. [Window Operations](#7-window-operations)
8. [Exactly-Once Guarantees](#8-exactly-once-guarantees)
9. [Table API and SQL](#9-table-api-and-sql)
10. [CEP](#10-cep-complex-event-processing)
11. [Memory Management](#11-memory-management)
12. [Deployment](#12-deployment)
13. [Performance Tuning](#13-performance-tuning)
14. [Fault Tolerance](#14-fault-tolerance)
15. [Flink CDC](#15-flink-cdc)

---

## 1. Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FLINK CLUSTER                             │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐       │
│  │                    JobManager                         │       │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────┐   │       │
│  │  │ Dispatcher │ │ Resource   │ │   JobMaster     │   │       │
│  │  │            │ │ Manager    │ │  (per job)      │   │       │
│  │  │ REST API   │ │            │ │                 │   │       │
│  │  │ Job Submit │ │ Slot Mgmt  │ │ Checkpoint Coord│   │       │
│  │  │ WebUI      │ │ TM Lifecycle│ │ Execution Graph │   │       │
│  │  └────────────┘ └────────────┘ └────────────────┘   │       │
│  └──────────────────────────────────────────────────────┘       │
│                              │                                   │
│              ┌───────────────┼───────────────┐                   │
│              ▼               ▼               ▼                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ TaskManager 0│ │ TaskManager 1│ │ TaskManager 2│            │
│  │              │ │              │ │              │            │
│  │ ┌──────────┐ │ │ ┌──────────┐ │ │ ┌──────────┐ │            │
│  │ │  Slot 0  │ │ │ │  Slot 0  │ │ │ │  Slot 0  │ │            │
│  │ │ ┌──────┐ │ │ │ │ ┌──────┐ │ │ │ │ ┌──────┐ │ │            │
│  │ │ │Task A│ │ │ │ │ │Task A│ │ │ │ │ │Task B│ │ │            │
│  │ │ │Task B│ │ │ │ │ │Task B│ │ │ │ │ │Task C│ │ │            │
│  │ │ └──────┘ │ │ │ │ └──────┘ │ │ │ │ └──────┘ │ │            │
│  │ └──────────┘ │ │ └──────────┘ │ │ └──────────┘ │            │
│  │ ┌──────────┐ │ │ ┌──────────┐ │ │ ┌──────────┐ │            │
│  │ │  Slot 1  │ │ │ │  Slot 1  │ │ │ │  Slot 1  │ │            │
│  │ └──────────┘ │ │ └──────────┘ │ │ └──────────┘ │            │
│  │              │ │              │ │              │            │
│  │ Network Mgr  │ │ Network Mgr  │ │ Network Mgr  │            │
│  │ Memory Mgr   │ │ Memory Mgr   │ │ Memory Mgr   │            │
│  │ State Backend│ │ State Backend│ │ State Backend│            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### JobManager Components

**Dispatcher:**
- REST endpoint for job submission
- Spawns a new JobMaster per submitted job
- Provides the Flink Web UI
- Persists job submissions for HA recovery

**ResourceManager:**
- Manages TaskManager slots
- Communicates with external resource providers (YARN, K8s, Standalone)
- Handles TaskManager registration and deregistration
- Triggers slot allocation/deallocation

**JobMaster (one per running job):**
- Converts JobGraph → ExecutionGraph
- Coordinates checkpoint/savepoint operations
- Handles task failures and restarts
- Manages distributed state snapshots

### TaskManager Internals

Each TaskManager is a JVM process with:
- **Task Slots**: Fixed resource subdivisions (memory is divided, CPU is shared)
- **Network Stack**: Netty-based, credit-based flow control
- **Memory Manager**: Manages off-heap/managed memory
- **State Backend**: Manages keyed/operator state
- **I/O Manager**: Async disk I/O for spilling

**Slot sharing:** Multiple operators from the same job can share a slot, enabling full pipeline within a single slot.

```
Slot Sharing Example:
┌──────────────────────────────────────┐
│              Slot 0                   │
│  Source(p=0) → Map(p=0) → Sink(p=0) │  ← Full pipeline in one slot
│                                       │
│  Managed Memory: 256MB               │
│  Network Memory: 64MB                │
│  Task Heap: 512MB                    │
└──────────────────────────────────────┘
```

### Parallelism and Task Slots

```
Job: Source(p=4) → KeyBy → Window(p=4) → Sink(p=2)

TaskManager 0 (2 slots):          TaskManager 1 (2 slots):
┌──────────┐ ┌──────────┐       ┌──────────┐ ┌──────────┐
│ Source[0] │ │ Source[1] │       │ Source[2] │ │ Source[3] │
│ Window[0] │ │ Window[1] │       │ Window[2] │ │ Window[3] │
│ Sink[0]   │ │          │       │ Sink[1]   │ │          │
└──────────┘ └──────────┘       └──────────┘ └──────────┘
```

---

## 2. Execution Model

### From User Code to Execution

```
User Code (DataStream API / SQL)
       │
       ▼
┌──────────────┐
│  StreamGraph  │  ← Logical DAG of operators
│  (Client)     │     Nodes: StreamNode (operator + parallelism)
└──────┬───────┘     Edges: StreamEdge (partitioning strategy)
       │
       ▼
┌──────────────┐
│   JobGraph    │  ← Optimized (operator chaining applied)
│  (Client)     │     Nodes: JobVertex (chained operators)
└──────┬───────┘     Edges: JobEdge (shuffle strategy)
       │
       ▼ (submitted to JobManager)
┌──────────────┐
│ExecutionGraph │  ← Parallelized execution plan
│ (JobManager)  │     Nodes: ExecutionVertex (parallel subtask)
└──────┬───────┘     Edges: ExecutionEdge (data exchange)
       │
       ▼
┌──────────────┐
│Physical Exec. │  ← Deployed tasks on TaskManagers
│(TaskManagers) │     Actual running subtask instances
└──────────────┘
```

### Operator Chaining

Flink chains operators that can run in the same thread to avoid serialization/network overhead:

```
Before chaining:
Source → Map → Filter → KeyBy → Window → Sink
  ↓       ↓      ↓               ↓         ↓
Task1  Task2  Task3           Task4     Task5

After chaining:
[Source → Map → Filter] → KeyBy → [Window → Sink]
        Task1                        Task2

Chaining conditions:
✓ Same parallelism
✓ Forward or rescale connection
✓ Same slot sharing group
✗ KeyBy/rebalance/broadcast breaks chains
✗ Different parallelism breaks chains
```

**Disabling chaining:**
```java
// Disable globally
env.disableOperatorChaining();

// Disable for specific operator
stream.map(x -> x).disableChaining();

// Start new chain
stream.map(x -> x).startNewChain();
```

### Data Exchange Patterns

```
FORWARD (1:1):
  Source[0] ──────► Map[0]
  Source[1] ──────► Map[1]

HASH (key-based):
  Source[0] ──┬───► KeyedOp[0]  (hash(key) % parallelism)
  Source[1] ──┤
              └───► KeyedOp[1]

REBALANCE (round-robin):
  Source[0] ──┬───► Map[0]
              └───► Map[1]
  Source[1] ──┬───► Map[0]
              └───► Map[1]

BROADCAST:
  Source[0] ──┬───► Map[0]  (all records to all)
              └───► Map[1]

RESCALE (local round-robin):
  Source[0] ──┬───► Map[0]  (within same TM)
              └───► Map[1]
  Source[2] ──┬───► Map[2]
              └───► Map[3]

GLOBAL:
  All records to subtask 0 (for total ordering)
```

### Credit-Based Flow Control

```
Upstream Task          Network Buffer           Downstream Task
┌──────────┐         ┌──────────────┐          ┌──────────┐
│          │──data──▶│ Buffer Pool   │──data──▶ │          │
│ Subtask  │         │              │          │ Subtask  │
│          │◀─credit─│ Credits:     │◀─credit──│          │
│          │         │ exclusive: 2  │          │          │
│          │         │ floating: 8   │          │          │
└──────────┘         └──────────────┘          └──────────┘

Flow:
1. Downstream allocates exclusive buffers per input channel
2. Downstream sends credits (available buffers) upstream
3. Upstream only sends data if it has credits
4. If credits exhausted → backpressure (upstream blocks)
5. As downstream processes data → releases buffers → sends new credits
```

---

## 3. State Management

### State Types

```java
// 1. ValueState - single value per key
public class WordCountFunction extends RichFlatMapFunction<String, Tuple2<String, Integer>> {
    private ValueState<Integer> countState;
    
    @Override
    public void open(Configuration parameters) {
        ValueStateDescriptor<Integer> descriptor = 
            new ValueStateDescriptor<>("word-count", Integer.class);
        // Optional: configure state TTL
        StateTtlConfig ttlConfig = StateTtlConfig
            .newBuilder(Time.hours(24))
            .setUpdateType(StateTtlConfig.UpdateType.OnCreateAndWrite)
            .setStateVisibility(StateTtlConfig.StateVisibility.NeverReturnExpired)
            .cleanupFullSnapshot()
            .build();
        descriptor.enableTimeToLive(ttlConfig);
        countState = getRuntimeContext().getState(descriptor);
    }
    
    @Override
    public void flatMap(String word, Collector<Tuple2<String, Integer>> out) throws Exception {
        Integer currentCount = countState.value();
        if (currentCount == null) currentCount = 0;
        currentCount++;
        countState.update(currentCount);
        out.collect(Tuple2.of(word, currentCount));
    }
}

// 2. ListState - list of values per key
ListState<Transaction> transactionHistory;
transactionHistory.add(newTransaction);
Iterable<Transaction> history = transactionHistory.get();

// 3. MapState - map of key-value pairs per key
MapState<String, Double> productPrices;
productPrices.put("SKU-123", 29.99);
Double price = productPrices.get("SKU-123");
boolean exists = productPrices.contains("SKU-123");

// 4. ReducingState - automatically reduces values
ReducingState<Long> sumState;
// Descriptor with ReduceFunction
new ReducingStateDescriptor<>("sum", Long::sum, Long.class);
sumState.add(100L); // Internally reduces: oldValue + newValue

// 5. AggregatingState - more flexible aggregation
AggregatingState<Event, AggResult> aggState;
// Descriptor with AggregateFunction (IN, ACC, OUT types can differ)
```

### State Backends

```
┌─────────────────────────────────────────────────────────────┐
│                    State Backend Comparison                    │
├─────────────────────┬────────────────┬──────────────────────┤
│                     │ HashMapState   │ EmbeddedRocksDB      │
│                     │ Backend        │ StateBackend          │
├─────────────────────┼────────────────┼──────────────────────┤
│ Storage location    │ JVM Heap       │ Local disk (+ mem)   │
│ State size limit    │ JVM heap size  │ Disk size            │
│ Performance         │ Very fast      │ Fast (SSD) / slower  │
│ Serialization       │ On checkpoint  │ On every access      │
│ Incremental ckpt    │ No             │ Yes                  │
│ Best for           │ Small state    │ Large state          │
│                     │ (< few GB)     │ (TB scale)           │
│ Memory overhead     │ Objects on heap│ Off-heap (managed)   │
│ GC impact          │ High           │ Low                  │
└─────────────────────┴────────────────┴──────────────────────┘
```

**Configuration:**
```java
// HashMapStateBackend
env.setStateBackend(new HashMapStateBackend());

// EmbeddedRocksDBStateBackend
env.setStateBackend(new EmbeddedRocksDBStateBackend(true)); // true = incremental checkpoints

// In flink-conf.yaml
state.backend: rocksdb
state.backend.rocksdb.localdir: /mnt/ssd/flink-state
state.backend.rocksdb.timer-service.factory: ROCKSDB  // or HEAP
state.backend.incremental: true
```

### Broadcast State

```java
// Pattern: Enrich a main stream with dynamically updated rules

// Rules stream (low throughput, broadcast to all operators)
MapStateDescriptor<String, Rule> ruleStateDescriptor = 
    new MapStateDescriptor<>("rules", String.class, Rule.class);
BroadcastStream<Rule> broadcastRules = ruleStream.broadcast(ruleStateDescriptor);

// Main event stream
DataStream<Event> events = env.addSource(kafkaSource);

// Connect and process
events.connect(broadcastRules)
    .process(new BroadcastProcessFunction<Event, Rule, Alert>() {
        @Override
        public void processElement(Event event, ReadOnlyContext ctx, 
                                   Collector<Alert> out) {
            ReadOnlyBroadcastState<String, Rule> rules = 
                ctx.getBroadcastState(ruleStateDescriptor);
            for (Map.Entry<String, Rule> entry : rules.immutableEntries()) {
                if (entry.getValue().matches(event)) {
                    out.collect(new Alert(event, entry.getValue()));
                }
            }
        }
        
        @Override
        public void processBroadcastElement(Rule rule, Context ctx, 
                                            Collector<Alert> out) {
            BroadcastState<String, Rule> state = 
                ctx.getBroadcastState(ruleStateDescriptor);
            state.put(rule.getId(), rule);
        }
    });
```

---

## 4. Checkpointing

### Chandy-Lamport Algorithm in Flink

```
Step-by-step checkpoint process:

1. JobManager triggers checkpoint (CheckpointCoordinator)
   
2. Inject barriers into source operators:

Source[0]:  ──[data]──[data]──|CB n|──[data]──[data]──
Source[1]:  ──[data]──|CB n|──[data]──[data]──[data]──

3. Barriers flow downstream with data:

Source[0] ──[d]──|CB n|──[d]──▶  Map[0]
Source[1] ──|CB n|──[d]──[d]──▶  Map[0]  (barrier alignment!)

4. Operator receives barriers from ALL inputs:

Map[0] receives:
  Input 0: ──[d]──|CB n|         ← barrier arrived, buffer data from this input
  Input 1: ──[d]──[d]──[d]──    ← still processing (no barrier yet)
  
  Alignment: Stop processing input 0, continue input 1
             Until input 1 barrier arrives
  
  Input 1: ──[d]──[d]──|CB n|   ← all barriers received!
  
5. Operator snapshots state, emits barrier downstream

6. When all sinks report barriers: checkpoint complete
```

### Aligned vs Unaligned Checkpoints

```
ALIGNED (default):
┌─────────────────────────────────────────────┐
│ Input 0: ──[d1]──|CB|──[d2]──[d3]──        │
│                   ▲                          │
│                   │ barrier arrives           │
│                   │ BLOCK this channel        │
│ Input 1: ──[d4]──[d5]──[d6]──|CB|──        │
│                                ▲             │
│                   unblock, snapshot state     │
│                                              │
│ Pros: Exactly-once, smaller checkpoint       │
│ Cons: Backpressure during alignment          │
└─────────────────────────────────────────────┘

UNALIGNED (Flink 1.11+):
┌─────────────────────────────────────────────┐
│ Input 0: ──[d1]──|CB|──[d2]──[d3]──        │
│                   ▲                          │
│                   │ barrier arrives           │
│                   │ DON'T block               │
│                   │ Snapshot in-flight data   │
│ Input 1: ──[d4]──[d5]──[d6]──|CB|──        │
│                                              │
│ Pros: No backpressure from alignment         │
│ Cons: Larger checkpoints (in-flight data)    │
│       More I/O during checkpoint             │
│ Use when: Severe backpressure makes aligned  │
│           checkpoints timeout                 │
└─────────────────────────────────────────────┘
```

**Configuration:**
```yaml
# flink-conf.yaml
execution.checkpointing.mode: EXACTLY_ONCE
execution.checkpointing.interval: 60000          # 60 seconds
execution.checkpointing.timeout: 600000           # 10 minutes
execution.checkpointing.min-pause: 30000          # 30s between checkpoints
execution.checkpointing.max-concurrent-checkpoints: 1
execution.checkpointing.unaligned.enabled: false  # Enable for backpressure
state.checkpoints.dir: s3://flink-checkpoints/job1/
state.savepoints.dir: s3://flink-savepoints/
state.backend.incremental: true
```

### Incremental Checkpoints (RocksDB only)

```
Full Checkpoint:         Incremental Checkpoint:
┌──────────────┐        ┌──────────────┐
│ CP-1: 10 GB  │        │ CP-1: 10 GB  │  (full baseline)
│ CP-2: 10 GB  │        │ CP-2: 500 MB │  (only SST file diffs)
│ CP-3: 10 GB  │        │ CP-3: 300 MB │  (only SST file diffs)
│ CP-4: 10 GB  │        │ CP-4: 800 MB │  (only SST file diffs)
└──────────────┘        └──────────────┘
Total: 40 GB            Total: 11.6 GB

How it works:
- RocksDB uses LSM tree with immutable SST files
- Flink tracks which SST files are new since last checkpoint
- Only uploads new/modified SST files
- References unchanged SST files from previous checkpoints
```

---

## 5. Savepoints

### Savepoints vs Checkpoints

| Aspect | Checkpoint | Savepoint |
|--------|-----------|-----------|
| Trigger | Automatic (periodic) | Manual (user-triggered) |
| Purpose | Failure recovery | Planned operations |
| Format | Backend-specific | Canonical (portable) |
| Lifecycle | Auto-deleted (retained count) | Never auto-deleted |
| Incremental | Yes (RocksDB) | No (always full) |
| Use cases | Crash recovery | Version upgrade, scaling, migration |

### Operator UID Best Practices

```java
// CRITICAL: Always assign UIDs for savepoint compatibility
env.addSource(kafkaSource)
    .uid("kafka-source")
    .name("Kafka Orders Source")
    .map(new ParseFunction())
    .uid("parse-orders")
    .name("Parse Orders")
    .keyBy(Order::getCustomerId)
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .uid("5min-window")
    .name("5-Minute Window Aggregation")
    .reduce(new SumReducer())
    .uid("sum-reducer")
    .addSink(sink)
    .uid("output-sink")
    .name("Output Sink");

// Without UIDs: Savepoint restore fails if topology changes
// With UIDs: Can add/remove/reorder operators and still restore
```

### Savepoint Operations

```bash
# Trigger savepoint
flink savepoint <jobId> s3://flink-savepoints/manual/

# Stop job with savepoint (graceful)
flink stop --savepointPath s3://flink-savepoints/ <jobId>

# Cancel job with savepoint
flink cancel --withSavepoint s3://flink-savepoints/ <jobId>

# Resume from savepoint
flink run -s s3://flink-savepoints/savepoint-abc123/ \
  --allowNonRestoredState \
  myapp.jar

# --allowNonRestoredState: Skip state for removed operators
```

---

## 6. Watermarks

### Event Time Processing

```
Event Time vs Processing Time:

Real-world timeline:
Events:  E1(10:00)  E2(10:01)  E3(10:03)  E4(10:02)  E5(10:05)
              │          │          │          │          │
Arrival:  ────┼────────┼──────────┼──┼────────┼──────────┼────▶
         10:01     10:02      10:05  10:06    10:06     10:07
                                     ▲
                                  Late arrival!
                                  (E4 arrives after E5)
```

### Watermark Generation

```java
// Strategy 1: BoundedOutOfOrdernessWatermarks
WatermarkStrategy<Event> strategy = WatermarkStrategy
    .<Event>forBoundedOutOfOrderness(Duration.ofSeconds(5))
    .withTimestampAssigner((event, timestamp) -> event.getTimestamp())
    .withIdleness(Duration.ofMinutes(1));  // Handle idle partitions

// Strategy 2: Monotonously increasing timestamps
WatermarkStrategy<Event> monoStrategy = WatermarkStrategy
    .<Event>forMonotonousTimestamps()
    .withTimestampAssigner((event, ts) -> event.getTimestamp());

// Strategy 3: Custom watermark generator
WatermarkStrategy<Event> customStrategy = WatermarkStrategy
    .forGenerator(ctx -> new WatermarkGenerator<Event>() {
        private long maxTimestamp = Long.MIN_VALUE;
        
        @Override
        public void onEvent(Event event, long eventTimestamp, 
                           WatermarkOutput output) {
            maxTimestamp = Math.max(maxTimestamp, event.getTimestamp());
        }
        
        @Override
        public void onPeriodicEmit(WatermarkOutput output) {
            // Emit watermark every 200ms (autoWatermarkInterval)
            output.emitWatermark(
                new Watermark(maxTimestamp - 5000)); // 5s tolerance
        }
    });
```

### Watermark Propagation

```
Source[0] (Partition 0):   W=10:03
Source[1] (Partition 1):   W=10:01
                              │
                              ▼
Map (receives from both): W = min(10:03, 10:01) = 10:01

Window [10:00-10:05):
  - Fires when watermark >= 10:05
  - Late data: events with timestamp < watermark

Idle partition problem:
  If Source[1] stops producing → watermark stuck at 10:01
  Solution: withIdleness(Duration.ofMinutes(1))
  After 1 minute idle, Source[1] excluded from min calculation
```

### Late Data Handling

```java
OutputTag<Event> lateOutputTag = new OutputTag<Event>("late-data") {};

SingleOutputStreamOperator<Result> result = stream
    .keyBy(Event::getKey)
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .allowedLateness(Time.minutes(10))  // Keep window state 10 more minutes
    .sideOutputLateData(lateOutputTag)   // Really late → side output
    .process(new MyWindowFunction());

// Get late data stream
DataStream<Event> lateStream = result.getSideOutput(lateOutputTag);
lateStream.addSink(new LateSink()); // Store for reconciliation
```

---

## 7. Window Operations

### Window Types

```
TUMBLING (fixed-size, non-overlapping):
|----W1----|----W2----|----W3----|
0          5          10         15  (minutes)

SLIDING (fixed-size, overlapping):
|------W1------|
   |------W2------|
      |------W3------|
Size=10min, Slide=5min

SESSION (dynamic, gap-based):
[E1 E2 E3]     [E4 E5]          [E6]
|---W1----|     |--W2--|         |W3|
  gap>5min ^      gap>5min ^

GLOBAL (single window per key, needs custom trigger):
|──────────────── forever ─────────────────|
```

### Window Implementation Examples

```java
// Tumbling window with AggregateFunction (most efficient)
stream
    .keyBy(Event::getUserId)
    .window(TumblingEventTimeWindows.of(Time.hours(1)))
    .aggregate(new AggregateFunction<Event, Accumulator, Result>() {
        @Override
        public Accumulator createAccumulator() { return new Accumulator(); }
        
        @Override
        public Accumulator add(Event event, Accumulator acc) {
            acc.count++;
            acc.sum += event.getAmount();
            return acc;
        }
        
        @Override
        public Result getResult(Accumulator acc) {
            return new Result(acc.count, acc.sum / acc.count);
        }
        
        @Override
        public Accumulator merge(Accumulator a, Accumulator b) {
            a.count += b.count;
            a.sum += b.sum;
            return a;
        }
    });

// Session window with gap
stream
    .keyBy(Event::getSessionId)
    .window(EventTimeSessionWindows.withGap(Time.minutes(30)))
    .process(new ProcessWindowFunction<Event, SessionResult, String, TimeWindow>() {
        @Override
        public void process(String key, Context ctx, 
                           Iterable<Event> events, 
                           Collector<SessionResult> out) {
            TimeWindow window = ctx.window();
            long sessionDuration = window.getEnd() - window.getStart();
            int eventCount = 0;
            for (Event e : events) eventCount++;
            out.collect(new SessionResult(key, sessionDuration, eventCount));
        }
    });
```

### Custom Triggers

```java
// Fire every 100 elements OR every 1 minute
public class CountOrTimeTrigger extends Trigger<Event, TimeWindow> {
    private final int maxCount;
    private final ReducingStateDescriptor<Long> countDesc = 
        new ReducingStateDescriptor<>("count", Long::sum, Long.class);
    
    @Override
    public TriggerResult onElement(Event element, long timestamp, 
                                    TimeWindow window, TriggerContext ctx) {
        ReducingState<Long> count = ctx.getPartitionedState(countDesc);
        count.add(1L);
        if (count.get() >= maxCount) {
            count.clear();
            return TriggerResult.FIRE_AND_PURGE;
        }
        ctx.registerEventTimeTimer(window.maxTimestamp());
        return TriggerResult.CONTINUE;
    }
    
    @Override
    public TriggerResult onEventTime(long time, TimeWindow window, 
                                      TriggerContext ctx) {
        return TriggerResult.FIRE_AND_PURGE;
    }
    
    @Override
    public TriggerResult onProcessingTime(long time, TimeWindow window, 
                                           TriggerContext ctx) {
        return TriggerResult.CONTINUE;
    }
    
    @Override
    public void clear(TimeWindow window, TriggerContext ctx) {
        ctx.getPartitionedState(countDesc).clear();
        ctx.deleteEventTimeTimer(window.maxTimestamp());
    }
}
```

---

## 8. Exactly-Once Guarantees

### Two-Phase Commit Protocol

```
Phase 1: Pre-commit (during checkpoint)
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Source   │────▶│ Process  │────▶│   Sink   │
│          │     │          │     │          │
│ Barrier  │     │ Barrier  │     │ Pre-     │
│ received │     │ received │     │ commit   │
│ Offset   │     │ State    │     │ (Kafka   │
│ snapshot │     │ snapshot │     │ txn open)│
└──────────┘     └──────────┘     └──────────┘

Phase 2: Commit (checkpoint success notification)
                                  ┌──────────┐
                                  │   Sink   │
                                  │          │
                                  │ Commit   │
                                  │ (Kafka   │
                                  │ txn      │
                                  │ commit)  │
                                  └──────────┘

If checkpoint fails → Abort (Kafka txn abort)
```

### End-to-End Exactly-Once with Kafka

```java
// Kafka Source with exactly-once
KafkaSource<String> source = KafkaSource.<String>builder()
    .setBootstrapServers("kafka:9092")
    .setTopics("input-topic")
    .setGroupId("flink-consumer")
    .setStartingOffsets(OffsetsInitializer.committedOffsets(
        OffsetResetStrategy.EARLIEST))
    .setDeserializer(new SimpleStringSchema())
    .build();

// Kafka Sink with exactly-once
KafkaSink<String> sink = KafkaSink.<String>builder()
    .setBootstrapServers("kafka:9092")
    .setRecordSerializer(
        KafkaRecordSerializationSchema.builder()
            .setTopic("output-topic")
            .setValueSerializationSchema(new SimpleStringSchema())
            .build())
    .setDeliveryGuarantee(DeliveryGuarantee.EXACTLY_ONCE)
    .setTransactionalIdPrefix("flink-txn")
    .setProperty("transaction.timeout.ms", "900000") // 15 min
    .build();

// IMPORTANT: Kafka transaction.timeout.ms must be > checkpoint interval
// Kafka broker max.transaction.timeout.ms must be >= this value
```

---

## 9. Table API and SQL

### Dynamic Tables and Changelog Streams

```
Stream-Table Duality:

Stream (append-only):                Table (materialized):
┌────────┬───────┬────────┐         ┌────────┬────────┐
│  time  │  key  │ value  │         │  key   │ value  │
├────────┼───────┼────────┤         ├────────┼────────┤
│  10:01 │  A    │  5     │  ──▶   │  A     │  8     │
│  10:02 │  B    │  3     │         │  B     │  3     │
│  10:03 │  A    │  8     │         └────────┴────────┘
└────────┴───────┴────────┘
```

### Changelog Modes

```
INSERT-ONLY: Each row is a new insert (append stream)
  +I[A, 5]
  +I[B, 3]
  +I[A, 8]

RETRACT: Delete old, insert new
  +I[A, 5]     (insert A=5)
  +I[B, 3]     (insert B=3)
  -D[A, 5]     (delete A=5)
  +I[A, 8]     (insert A=8)

UPSERT: Key-based update (more efficient)
  +U[A, 5]     (upsert A=5)
  +U[B, 3]     (upsert B=3)
  +U[A, 8]     (upsert A=8, replaces A=5)
```

### Flink SQL Examples

```sql
-- Create Kafka source table
CREATE TABLE orders (
    order_id STRING,
    customer_id STRING,
    amount DECIMAL(10, 2),
    order_time TIMESTAMP(3),
    WATERMARK FOR order_time AS order_time - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'orders',
    'properties.bootstrap.servers' = 'kafka:9092',
    'properties.group.id' = 'flink-sql',
    'scan.startup.mode' = 'earliest-offset',
    'format' = 'json'
);

-- Tumbling window aggregation
SELECT 
    customer_id,
    TUMBLE_START(order_time, INTERVAL '1' HOUR) AS window_start,
    COUNT(*) AS order_count,
    SUM(amount) AS total_amount
FROM orders
GROUP BY 
    customer_id,
    TUMBLE(order_time, INTERVAL '1' HOUR);

-- Temporal join (point-in-time lookup)
CREATE TABLE currency_rates (
    currency STRING,
    rate DECIMAL(10, 6),
    update_time TIMESTAMP(3),
    WATERMARK FOR update_time AS update_time - INTERVAL '10' SECOND,
    PRIMARY KEY (currency) NOT ENFORCED
) WITH (
    'connector' = 'kafka',
    'topic' = 'currency-rates',
    'format' = 'json',
    'scan.startup.mode' = 'earliest-offset'
);

SELECT 
    o.order_id,
    o.amount,
    o.amount * r.rate AS amount_usd,
    r.currency,
    r.rate
FROM orders AS o
JOIN currency_rates FOR SYSTEM_TIME AS OF o.order_time AS r
ON o.currency = r.currency;

-- Top-N query (continuously updated)
SELECT *
FROM (
    SELECT 
        product_id,
        total_sales,
        ROW_NUMBER() OVER (ORDER BY total_sales DESC) AS row_num
    FROM product_sales
)
WHERE row_num <= 10;

-- CDC Source (Debezium format)
CREATE TABLE mysql_orders (
    order_id INT,
    customer_name STRING,
    price DECIMAL(10, 5),
    order_status STRING,
    PRIMARY KEY (order_id) NOT ENFORCED
) WITH (
    'connector' = 'mysql-cdc',
    'hostname' = 'mysql-host',
    'port' = '3306',
    'username' = 'cdc_user',
    'password' = 'cdc_pass',
    'database-name' = 'ecommerce',
    'table-name' = 'orders'
);
```

---

## 10. CEP (Complex Event Processing)

### Pattern API

```java
// Detect: Login → (Failed Login within 5 min) × 3 → Account Lock
Pattern<LoginEvent, ?> bruteForcePattern = Pattern
    .<LoginEvent>begin("first-login")
        .where(new SimpleCondition<LoginEvent>() {
            public boolean filter(LoginEvent event) {
                return event.getType().equals("LOGIN_ATTEMPT");
            }
        })
    .next("failed-logins")
        .where(new SimpleCondition<LoginEvent>() {
            public boolean filter(LoginEvent event) {
                return event.getType().equals("LOGIN_FAILED");
            }
        })
        .timesOrMore(3)
        .greedy()
    .within(Time.minutes(5));

PatternStream<LoginEvent> patternStream = CEP.pattern(
    loginStream.keyBy(LoginEvent::getUserId),
    bruteForcePattern
);

DataStream<Alert> alerts = patternStream.select(
    (Map<String, List<LoginEvent>> pattern) -> {
        LoginEvent firstLogin = pattern.get("first-login").get(0);
        List<LoginEvent> failures = pattern.get("failed-logins");
        return new Alert(
            "BRUTE_FORCE_DETECTED",
            firstLogin.getUserId(),
            failures.size() + " failed attempts in 5 minutes"
        );
    }
);
```

---

## 11. Memory Management

### Memory Model

```
┌─────────────────────────────────────────────────────────────┐
│                   TaskManager Memory                         │
│                                                              │
│  Total Process Memory                                        │
│  ├── Total Flink Memory                                      │
│  │   ├── Framework Heap (128MB default)                      │
│  │   ├── Framework Off-Heap (128MB default)                  │
│  │   ├── Task Heap (user code)                               │
│  │   ├── Task Off-Heap (user native code)                    │
│  │   ├── Network Memory (fraction: 0.1, min: 64MB)          │
│  │   │   └── Shuffle buffers, credit-based flow control      │
│  │   └── Managed Memory (fraction: 0.4)                     │
│  │       ├── RocksDB state backend                           │
│  │       ├── Batch operator sorting/hashing                  │
│  │       └── Python UDF                                      │
│  └── JVM Metaspace (256MB default)                          │
│  └── JVM Overhead (fraction: 0.1, min: 192MB)              │
│      └── Thread stacks, code cache, GC                      │
└─────────────────────────────────────────────────────────────┘
```

**Configuration:**
```yaml
# flink-conf.yaml
taskmanager.memory.process.size: 4096m          # Total process memory
taskmanager.memory.flink.size: 3072m            # Or specify this instead
taskmanager.memory.task.heap.size: 1024m         # For user code
taskmanager.memory.managed.fraction: 0.4         # For RocksDB/batch ops
taskmanager.memory.network.fraction: 0.1         # For shuffle buffers
taskmanager.memory.network.min: 64mb
taskmanager.memory.network.max: 1gb
taskmanager.memory.framework.heap.size: 128m
taskmanager.memory.jvm-overhead.fraction: 0.1
taskmanager.numberOfTaskSlots: 4
```

### RocksDB Memory Tuning

```yaml
# RocksDB memory is allocated from Managed Memory
state.backend.rocksdb.memory.managed: true       # Use managed memory
state.backend.rocksdb.memory.fixed-per-slot: 256m  # Or fixed per slot
state.backend.rocksdb.memory.write-buffer-ratio: 0.5
state.backend.rocksdb.memory.high-prio-pool-ratio: 0.1
state.backend.rocksdb.block.cache-size: 64m
state.backend.rocksdb.writebuffer.size: 64m
state.backend.rocksdb.writebuffer.count: 3
state.backend.rocksdb.compaction.level.max-size-level-base: 256m
```

---

## 12. Deployment

### Deployment Modes Comparison

```
┌──────────────────────────────────────────────────────────────┐
│                    Deployment Modes                           │
├──────────────┬──────────────┬──────────────┬────────────────┤
│              │ Session Mode │ Per-Job Mode │ Application    │
│              │              │ (deprecated) │ Mode           │
├──────────────┼──────────────┼──────────────┼────────────────┤
│ Cluster life │ Long-running │ Per job      │ Per application│
│ Job isolation│ Shared       │ Isolated     │ Isolated       │
│ main() runs  │ Client       │ Client       │ Cluster        │
│ Resource     │ Pre-alloc    │ Per job      │ Per application│
│ Best for     │ Interactive  │ Large batch  │ Production     │
│              │ Short jobs   │              │ streaming      │
│ Jar upload   │ Per submit   │ Per submit   │ In container   │
└──────────────┴──────────────┴──────────────┴────────────────┘
```

### Kubernetes Deployment

```yaml
# Flink Kubernetes Operator - FlinkDeployment
apiVersion: flink.apache.org/v1beta1
kind: FlinkDeployment
metadata:
  name: fraud-detection
spec:
  image: flink:1.17
  flinkVersion: v1_17
  flinkConfiguration:
    taskmanager.numberOfTaskSlots: "4"
    state.backend: rocksdb
    state.checkpoints.dir: s3://flink-checkpoints/fraud-detection/
    state.savepoints.dir: s3://flink-savepoints/fraud-detection/
    execution.checkpointing.interval: "60000"
    execution.checkpointing.min-pause: "30000"
    high-availability: org.apache.flink.kubernetes.highavailability.KubernetesHaServicesFactory
    high-availability.storageDir: s3://flink-ha/fraud-detection/
    restart-strategy: failure-rate
    restart-strategy.failure-rate.max-failures-per-interval: "10"
    restart-strategy.failure-rate.failure-rate-interval: "5 min"
    restart-strategy.failure-rate.delay: "30 s"
  serviceAccount: flink
  jobManager:
    resource:
      memory: "2048m"
      cpu: 1
    replicas: 1
  taskManager:
    resource:
      memory: "4096m"
      cpu: 2
    replicas: 4
  job:
    jarURI: local:///opt/flink/usrlib/fraud-detection.jar
    entryClass: com.example.FraudDetectionJob
    parallelism: 16
    upgradeMode: savepoint
    state: running
    savepointTriggerNonce: 0
```

---

## 13. Performance Tuning

### Key Tuning Parameters

| Parameter | Default | Tuning Guidance |
|-----------|---------|-----------------|
| `parallelism.default` | 1 | Match to source partitions |
| `taskmanager.numberOfTaskSlots` | 1 | CPU cores per TM |
| `taskmanager.memory.network.fraction` | 0.1 | Increase for shuffle-heavy |
| `execution.buffer-timeout` | 100ms | 0 for min latency, higher for throughput |
| `pipeline.object-reuse` | false | true for performance (UNSAFE with mutable objects) |
| `state.backend.rocksdb.thread.num` | 1 | Increase for parallel compaction |

### Serialization Performance

```
Serialization Speed Ranking (fastest to slowest):
1. Flink POJO Serializer (auto-detects POJOs)
2. Flink Tuple types
3. Avro (SpecificRecord)
4. Protobuf
5. Kryo (fallback, SLOWEST - avoid in production)

Rules for Flink POJO detection:
- Public class
- Public no-arg constructor
- All fields are public or have getters/setters
- All field types are serializable by Flink

// Check serialization:
env.getConfig().disableGenericTypes(); // Fail if Kryo would be used
```

### Async I/O

```java
// For enrichment from external databases
AsyncDataStream.unorderedWait(
    stream,
    new AsyncDatabaseLookup(),
    30, TimeUnit.SECONDS,   // timeout
    100                      // max concurrent requests
)

public class AsyncDatabaseLookup extends RichAsyncFunction<Event, EnrichedEvent> {
    private transient AsyncClient client;
    
    @Override
    public void open(Configuration parameters) {
        client = new AsyncClient(/* connection pool */);
    }
    
    @Override
    public void asyncInvoke(Event event, ResultFuture<EnrichedEvent> resultFuture) {
        CompletableFuture<UserProfile> future = client.getUser(event.getUserId());
        future.thenAccept(profile -> {
            resultFuture.complete(
                Collections.singleton(new EnrichedEvent(event, profile))
            );
        });
    }
}
```

---

## 14. Fault Tolerance

### Restart Strategies

```java
// Fixed-delay restart
env.setRestartStrategy(RestartStrategies.fixedDelayRestart(
    3,                          // max attempts
    Time.of(10, TimeUnit.SECONDS) // delay between attempts
));

// Failure-rate restart (recommended for production)
env.setRestartStrategy(RestartStrategies.failureRateRestart(
    10,                           // max failures
    Time.of(5, TimeUnit.MINUTES), // failure rate interval
    Time.of(30, TimeUnit.SECONDS) // delay between restarts
));

// Exponential-delay restart (Flink 1.15+)
env.setRestartStrategy(RestartStrategies.exponentialDelayRestart(
    Time.of(1, TimeUnit.SECONDS),   // initial backoff
    Time.of(5, TimeUnit.MINUTES),   // max backoff
    2.0,                              // backoff multiplier
    Time.of(10, TimeUnit.MINUTES),  // reset backoff threshold
    0.1                               // jitter
));
```

### Failover Strategies

```
Full Restart (default before 1.9):
  All tasks restart → entire pipeline restops
  Simple but wasteful for large jobs

Region Failover (default since 1.9):
  Only restart affected region (connected tasks)
  Much faster recovery for pipelined regions
  
  Example:
  [Source → Map → Filter] → [KeyBy → Window → Sink]
       Region 1                    Region 2
  
  If Filter[2] fails:
  - Only Region 1, subtask 2 restarts
  - Region 2 continues (may need replay from checkpoint)
```

---

## 15. Flink CDC

### Architecture

```
┌─────────────┐    ┌──────────┐    ┌──────────────┐    ┌──────────┐
│   MySQL     │───▶│  Flink   │───▶│  Processing  │───▶│  Sink    │
│   Binlog    │    │  CDC     │    │  (Flink SQL  │    │  (Kafka, │
│             │    │ Connector│    │   or DataStr) │    │  Iceberg)│
└─────────────┘    └──────────┘    └──────────────┘    └──────────┘
```

### Incremental Snapshot Algorithm (Lock-Free)

```
Traditional: LOCK table → Full snapshot → Read binlog → UNLOCK
Problem: Table locked during entire snapshot (hours for large tables)

Flink CDC Incremental Snapshot (Chunk-based, Lock-Free):
1. Split table into chunks by primary key ranges
2. Read each chunk independently (SELECT with range)
3. Record binlog position before/after each chunk read
4. Merge chunk data with binlog events for consistency
5. No global lock needed!

Chunk splitting:
  Table: orders (PK: order_id, 10M rows)
  Chunk 0: order_id IN [1, 100000]
  Chunk 1: order_id IN [100001, 200000]
  ...
  Chunk 99: order_id IN [9900001, 10000000]
  
  Each chunk read in parallel → Much faster snapshot
```

### CDC SQL Example

```sql
-- MySQL CDC source
CREATE TABLE mysql_products (
    id INT,
    name STRING,
    price DECIMAL(10, 2),
    update_time TIMESTAMP(3),
    PRIMARY KEY (id) NOT ENFORCED
) WITH (
    'connector' = 'mysql-cdc',
    'hostname' = 'mysql',
    'port' = '3306',
    'username' = 'cdc_user',
    'password' = 'cdc_pass',
    'database-name' = 'shop',
    'table-name' = 'products',
    'scan.incremental.snapshot.enabled' = 'true',
    'scan.incremental.snapshot.chunk.size' = '8096'
);

-- PostgreSQL CDC source
CREATE TABLE pg_orders (
    order_id INT,
    customer_id INT,
    total DECIMAL(10, 2),
    status STRING,
    created_at TIMESTAMP(3),
    PRIMARY KEY (order_id) NOT ENFORCED
) WITH (
    'connector' = 'postgres-cdc',
    'hostname' = 'postgres',
    'port' = '5432',
    'username' = 'cdc_user',
    'password' = 'cdc_pass',
    'database-name' = 'ecommerce',
    'schema-name' = 'public',
    'table-name' = 'orders',
    'slot.name' = 'flink_slot',
    'decoding.plugin.name' = 'pgoutput'
);

-- Stream to Iceberg sink
CREATE TABLE iceberg_orders (
    order_id INT,
    customer_id INT,
    total DECIMAL(10, 2),
    status STRING,
    created_at TIMESTAMP(3),
    PRIMARY KEY (order_id) NOT ENFORCED
) WITH (
    'connector' = 'iceberg',
    'catalog-type' = 'hive',
    'catalog-name' = 'hive_catalog',
    'catalog-database' = 'analytics',
    'catalog-table' = 'orders',
    'write.upsert.enabled' = 'true'
);

INSERT INTO iceberg_orders SELECT * FROM pg_orders;
```

---

## Production Checklist

```
[ ] Assign UIDs to ALL operators (savepoint compatibility)
[ ] Configure checkpointing (interval, timeout, min-pause)
[ ] Use incremental checkpoints with RocksDB
[ ] Set appropriate restart strategy (failure-rate recommended)
[ ] Configure state TTL for keyed state
[ ] Set watermark idleness timeout for idle partitions
[ ] Tune parallelism to match source partitions
[ ] Monitor: checkpoint duration, checkpoint size, backpressure
[ ] Configure exactly-once sinks with 2PC when needed
[ ] Use Application mode for production deployments
[ ] Set up HA with Kubernetes or ZooKeeper
[ ] Configure managed memory for RocksDB
[ ] Avoid Kryo serialization (use POJOs or Avro)
[ ] Enable unaligned checkpoints only if alignment causes timeouts
[ ] Configure network buffer memory for shuffle-heavy jobs
[ ] Set up savepoint automation for planned maintenance
```
