# Windowing & Watermark Issues (#54-65)

> Windowing and watermarks are the foundation of event-time processing. These issues cause incorrect results, data loss, or jobs that appear stuck.

---

## Issue #54: Watermark Not Advancing (Idle Partitions)

**Severity**: 🔴 Critical  
**Frequency**: Very High  
**Impact**: Windows never fire, results never emitted, state grows unbounded

### Symptoms
- No window output despite data flowing
- `currentOutputWatermark` metric stuck at very old timestamp or Long.MIN_VALUE
- State size growing because windows accumulate events but never fire
- Operators after window show 0 records/sec

### Root Cause
One source partition/split has no data. Watermark = min(all inputs):
- If ANY input has watermark at Long.MIN_VALUE → overall watermark = Long.MIN_VALUE
- Windows trigger on watermark advancement → never triggers

Common scenarios:
- Kafka topic with more partitions than active producers
- Time-based partitioned topics where some hours have no data
- Source split has no data (e.g., empty file)

### Diagnosis
```promql
# Check per-subtask watermark (look for stuck ones)
flink_taskmanager_job_task_operator_currentOutputWatermark

# Look for MIN_VALUE (-9223372036854775808)
# or very old timestamps
```

### Fix
```java
// Solution 1: Configure idleness detection
WatermarkStrategy.<Event>forBoundedOutOfOrderness(Duration.ofSeconds(30))
    .withIdleness(Duration.ofMinutes(1))  // Mark idle after 1 min

// Solution 2: Custom watermark generator that handles idle sources
public class IdleAwareWatermarkGenerator implements WatermarkGenerator<Event> {
    private long maxTimestamp = Long.MIN_VALUE;
    private long lastEventTime = System.currentTimeMillis();
    private static final long IDLE_TIMEOUT = 60_000; // 1 min
    
    @Override
    public void onEvent(Event event, long eventTimestamp, WatermarkOutput output) {
        maxTimestamp = Math.max(maxTimestamp, eventTimestamp);
        lastEventTime = System.currentTimeMillis();
    }
    
    @Override
    public void onPeriodicEmit(WatermarkOutput output) {
        if (System.currentTimeMillis() - lastEventTime > IDLE_TIMEOUT) {
            // Emit watermark based on processing time when idle
            output.markIdle();
        } else {
            output.emitWatermark(new Watermark(maxTimestamp - OUT_OF_ORDERNESS));
        }
    }
}
```

### Prevention
- **ALWAYS** use `.withIdleness()` for any multi-partition source
- Set idle timeout < window size (so windows can still fire)
- Monitor watermark age vs wall clock time

---

## Issue #55: Late Data Silently Dropped

**Severity**: 🔴 Critical  
**Frequency**: High  
**Impact**: Data loss — events processed but results never emitted

### Symptoms
- Input record count > output record count (records disappearing)
- No error in logs (Flink silently drops late data by default)
- Business reports show missing data
- Specific time periods have gaps

### Root Cause
Events arriving after watermark has passed the window end + allowed lateness:
```
Window [10:00, 10:05)
Watermark passes 10:05 → window fires
Event arrives with timestamp 10:02 → DROPPED (watermark already at 10:05+)
```

Default `allowedLateness` is 0 — any event arriving after window fires is dropped.

### Fix
```java
// Solution 1: Configure allowed lateness
stream
    .keyBy(Event::getKey)
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .allowedLateness(Time.hours(1))  // Accept late data up to 1 hour
    .sideOutputLateData(lateOutputTag)  // Capture events beyond even this
    .aggregate(new MyAggregator());

// Solution 2: Capture ALL late data in side output
OutputTag<Event> lateTag = new OutputTag<Event>("late-data") {};

SingleOutputStreamOperator<Result> results = stream
    .keyBy(Event::getKey)
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .allowedLateness(Time.hours(24))        // Very generous
    .sideOutputLateData(lateTag)            // Capture anything beyond 24h
    .aggregate(new MyAggregator());

// Process late data separately
DataStream<Event> lateData = results.getSideOutput(lateTag);
lateData.addSink(new LateDataSink());  // Write to DLQ or correction pipeline
```

### Prevention
- ALWAYS configure `allowedLateness` for production windows
- ALWAYS configure `sideOutputLateData` to capture stragglers
- Monitor: `numLateRecordsDropped` metric
- Set lateness based on business requirements (not arbitrary)

---

## Issue #56: Window Never Fires (Watermark Misconfiguration)

**Severity**: 🔴 Critical  
**Frequency**: High  
**Impact**: No results produced, state accumulates forever

### Symptoms
- Input records flowing (non-zero throughput)
- Zero output from window operator
- State growing continuously
- Watermark metric shows advancement but windows don't trigger

### Root Cause
1. **Timestamp assigner returning wrong field** (e.g., processing time instead of event time)
2. **Watermark set to processing time** but windows use event time
3. **Bounded out-of-orderness too large** (watermark always behind window end)
4. **Window size too large** for data rate (minutes of gap in data)
5. **TimeCharacteristic.ProcessingTime** set but using event time windows

### Diagnosis
```java
// Debug: Print watermarks and window assignments
stream.process(new ProcessFunction<Event, Event>() {
    @Override
    public void processElement(Event e, Context ctx, Collector<Event> out) {
        LOG.info("Event time: {}, Current watermark: {}", 
            e.getTimestamp(), ctx.timerService().currentWatermark());
        out.collect(e);
    }
});
```

### Fix
```java
// Verify timestamp assignment is correct
WatermarkStrategy.<Event>forBoundedOutOfOrderness(Duration.ofSeconds(5))
    .withTimestampAssigner((event, recordTimestamp) -> {
        long ts = event.getEventTimeMillis();  // Ensure this is milliseconds!
        if (ts < 1000000000000L) {
            ts *= 1000;  // Convert seconds to milliseconds if needed
        }
        return ts;
    });

// Ensure env is set to event time (Flink 1.12+ default)
env.setStreamTimeCharacteristic(TimeCharacteristic.EventTime);
```

### Prevention
- Always log/metric the first few watermarks to verify correctness
- Unit test timestamp extraction
- Monitor `currentOutputWatermark` vs expected event time

---

## Issue #57: Duplicate Window Results After Checkpoint Recovery

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Duplicate results emitted to sink

### Symptoms
- After job restart, same window results emitted again
- Downstream sees duplicate entries for same window
- Happens because window fires, result sent to sink, but checkpoint didn't complete before crash

### Root Cause
```
Timeline:
1. Window fires → emit result to sink ✓
2. Result written to sink ✓
3. Checkpoint starts (would capture window as fired)
4. JOB CRASHES before checkpoint completes ✗
5. Recovery from previous checkpoint (window NOT fired yet)
6. Window fires again → duplicate result!
```

### Fix
```java
// Solution 1: Use exactly-once sinks (two-phase commit)
stream.sinkTo(
    KafkaSink.<Result>builder()
        .setDeliveryGuarantee(DeliveryGuarantee.EXACTLY_ONCE)
        .build()
);

// Solution 2: Idempotent sink (upsert semantics)
// Write with deterministic key: window_start + key → result
// Second write simply overwrites first (same result)

// Solution 3: Deduplication at sink level
public class DeduplicatingSink extends RichSinkFunction<WindowResult> {
    private transient Set<String> processedWindows;
    
    @Override
    public void invoke(WindowResult result, Context ctx) {
        String key = result.getKey() + "_" + result.getWindowStart();
        if (!processedWindows.contains(key)) {
            writeToDatabase(result);
            processedWindows.add(key);
        }
    }
}
```

### Prevention
- Use exactly-once sinks for window results
- Design sinks to be idempotent (upsert pattern)
- Set checkpoint interval < window duration

---

## Issue #58: Session Window Gap Timeout Too Short/Long

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Sessions split incorrectly or merged incorrectly

### Symptoms
- Single user sessions being split into multiple windows
- OR: Multiple distinct sessions merged into one giant window
- Session metrics (duration, page count) seem wrong

### Root Cause
Session gap is the wrong duration for the use case:
- Too short: Natural pauses in activity split sessions (reading an article)
- Too long: Sequential visits merge into one session (lunch break)

### Fix
```java
// Dynamic session gap based on user behavior
public class DynamicSessionGapAssigner 
    implements SessionWindowTimeGapExtractor<Event> {
    
    @Override
    public long extract(Event event) {
        // Different gap based on event type
        switch (event.getType()) {
            case "video_play": return 30 * 60 * 1000;  // 30 min for video
            case "page_view": return 30 * 60 * 1000;   // 30 min for browsing
            case "search": return 5 * 60 * 1000;       // 5 min for search
            default: return 15 * 60 * 1000;            // 15 min default
        }
    }
}

stream
    .keyBy(Event::getUserId)
    .window(EventTimeSessionWindows.withDynamicGap(new DynamicSessionGapAssigner()))
    .process(new SessionProcessor());
```

### Prevention
- Analyze actual user behavior data to determine gaps
- Add session duration cap (max 24 hours regardless of activity)
- A/B test different gap durations

---

## Issue #59: Window State Too Large for Large Windows

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Checkpoint grows very large, potential timeout

### Symptoms
- 1-hour windows accumulating millions of events per key
- State size = window_duration × event_rate × num_keys
- Checkpoint size growing until window fires, then drops

### Root Cause
`ProcessWindowFunction` stores ALL events until window fires:
```java
// BAD: All events stored until window end
.process(new ProcessWindowFunction<Event, Result, String, TimeWindow>() {
    @Override
    public void process(String key, Context ctx, Iterable<Event> elements, 
                       Collector<Result> out) {
        // 'elements' contains ALL events in window (millions!)
    }
});
```

### Fix
```java
// GOOD: Use incremental aggregation (AggregateFunction)
.aggregate(new MyAggregateFunction())  // Only accumulator stored, not all events

// GOOD: Combine incremental + full (get window metadata)
.aggregate(new MyAggregateFunction(), new MyProcessWindowFunction())
// Accumulator is pre-computed, ProcessWindowFunction only sees final result

public class MyAggregateFunction 
    implements AggregateFunction<Event, MyAccumulator, MyResult> {
    @Override
    public MyAccumulator createAccumulator() { return new MyAccumulator(); }
    
    @Override
    public MyAccumulator add(Event event, MyAccumulator acc) {
        acc.count++;
        acc.sum += event.getAmount();
        // Only accumulator in state, NOT individual events!
        return acc;
    }
    
    @Override
    public MyResult getResult(MyAccumulator acc) {
        return new MyResult(acc.count, acc.sum / acc.count);
    }
    
    @Override
    public MyAccumulator merge(MyAccumulator a, MyAccumulator b) {
        a.count += b.count;
        a.sum += b.sum;
        return a;
    }
}
```

### Prevention
- ALWAYS prefer `AggregateFunction` over `ProcessWindowFunction` alone
- If you need window metadata, use combined `aggregate(agg, processWindow)`
- Monitor per-window state size

---

## Issue #60: Allowed Lateness Causing State Explosion

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Window state not cleaned up for lateness duration

### Symptoms
- State grows proportional to: `num_keys × allowed_lateness / window_size`
- Setting `allowedLateness(Time.days(7))` → 7 days of window state retained
- With 1M keys × 5-min windows × 7 days = 2.016M window instances in state

### Root Cause
Flink keeps window state alive until `window_end + allowed_lateness`:
- Window [10:00, 10:05) with 7-day lateness
- State kept until watermark reaches 10:05 + 7 days
- For high cardinality keys, this multiplies massively

### Fix
```java
// Solution 1: Reduce lateness, use side output for very late data
stream
    .keyBy(Event::getKey)
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .allowedLateness(Time.hours(1))       // 1 hour, not 7 days!
    .sideOutputLateData(lateTag)          // Capture beyond 1 hour
    .aggregate(new MyAgg());

// Process very late data in separate batch job (daily correction)
results.getSideOutput(lateTag)
    .addSink(new S3LateDataSink());  // Store for batch correction

// Solution 2: Use global window with custom purging trigger
.window(GlobalWindows.create())
.trigger(new CustomPurgingTrigger())  // Fire and purge based on custom logic
```

### Prevention
- Calculate state impact: `keys × (lateness / window_size) × state_per_window`
- Use shortest lateness that meets business requirements
- Handle very late data in separate pipeline (batch correction)

---

## Issue #61: Tumbling Window Alignment Issues

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Windows not aligned to expected boundaries (e.g., hour boundary)

### Symptoms
- 1-hour windows firing at 10:03, 11:03, 12:03 (3 minutes off)
- Time zone issues causing misaligned daily windows

### Root Cause
Windows aligned to epoch by default. With offset/timezone:
- `TumblingEventTimeWindows.of(Time.hours(1))` aligns to epoch (UTC midnight)
- If you expect alignment to local timezone, results shift

### Fix
```java
// Align to specific offset
TumblingEventTimeWindows.of(
    Time.hours(1), 
    Time.hours(-8)  // Align to PST (UTC-8)
)

// Daily windows aligned to business day (e.g., 6 AM start)
TumblingEventTimeWindows.of(
    Time.days(1),
    Time.hours(6)  // Day starts at 6 AM
)
```

---

## Issue #62: Processing Time Timer Drift in Long-Running Jobs

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Timers fire later than expected, accumulated drift

### Symptoms
- Processing time timers drifting from expected fire time
- Timers registered for T fire at T+seconds/minutes
- More drift under heavy load (CPU saturation)

### Root Cause
Processing time timers are best-effort:
- Timer thread checks periodically (not exactly at fire time)
- Under CPU pressure, timer callbacks delayed
- GC pauses delay timer processing
- Timer resolution depends on system clock

### Fix
```java
// Don't rely on exact processing time timer precision
// Use event time timers where possible
ctx.timerService().registerEventTimeTimer(
    event.getTimestamp() + TIMEOUT_MS);  // Deterministic!

// For processing time timers, add tolerance
@Override
public void onTimer(long timestamp, OnTimerContext ctx, Collector<Out> out) {
    long drift = System.currentTimeMillis() - timestamp;
    if (drift > ACCEPTABLE_DRIFT_MS) {
        metrics.counter("timer-drift-high").inc();
    }
    // Process regardless of drift
}
```

---

## Issue #63: Event Time vs Ingestion Time Confusion

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Incorrect window assignment, wrong results

### Symptoms
- Windows contain wrong events
- Results don't match expected business logic
- Timestamp field is Kafka ingestion time, not actual event time

### Root Cause
Using wrong timestamp for event time:
- Kafka `record.timestamp()` = producer time (not event time)
- Using CreateTime vs LogAppendTime confusion
- Event time embedded in payload but not extracted

### Fix
```java
// Explicitly extract event time from payload
WatermarkStrategy.<MyEvent>forBoundedOutOfOrderness(Duration.ofSeconds(10))
    .withTimestampAssigner((event, kafkaTimestamp) -> {
        // Use the BUSINESS event time, not Kafka timestamp
        return event.getOccurredAt().toInstant().toEpochMilli();
    });
```

---

## Issue #64: Window Trigger Fires Multiple Times Unexpectedly

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Multiple results per window, confusing downstream consumers

### Symptoms
- Same window key+start combination appearing multiple times in output
- `allowedLateness` causing re-fires
- Custom trigger emitting too often

### Root Cause
Windows re-fire for late data when `allowedLateness > 0`:
- First fire at watermark = window_end
- Re-fires for each late element that updates the window
- Downstream must handle UPDATES not just INSERTS

### Fix
```java
// Solution 1: Use FIRE_AND_PURGE to prevent re-fires (lose updates)
.trigger(PurgingTrigger.of(EventTimeTrigger.create()))

// Solution 2: Send update mode to downstream (retract/upsert)
// Mark results with fire count so downstream can handle
public class MyWindowFunction 
    extends ProcessWindowFunction<Event, Result, String, TimeWindow> {
    
    @Override
    public void process(String key, Context ctx, Iterable<Event> elements,
                       Collector<Result> out) {
        // ctx.window().maxTimestamp() for window identification
        boolean isLatefire = ctx.currentWatermark() > ctx.window().maxTimestamp();
        
        Result result = compute(elements);
        result.setIsUpdate(isLatefire);  // Mark as update for downstream
        out.collect(result);
    }
}
```

---

## Issue #65: Custom Watermark Generator Memory Leak

**Severity**: 🟡 Warning  
**Frequency**: Low-Medium  
**Impact**: Slow memory growth in source operator

### Symptoms
- Source operator memory growing slowly
- Custom WatermarkGenerator accumulating state

### Root Cause
Custom watermark generator storing data per-partition without cleanup:
```java
// Bad: Accumulating per-partition timestamps without bound
Map<Integer, Long> partitionTimestamps = new HashMap<>();  // Never cleaned!
```

### Fix
```java
// Use simple stateless watermark generator
public class MyWatermarkGenerator implements WatermarkGenerator<Event> {
    private long maxTimestamp = Long.MIN_VALUE;
    
    @Override
    public void onEvent(Event event, long eventTimestamp, WatermarkOutput output) {
        maxTimestamp = Math.max(maxTimestamp, eventTimestamp);
        // No collection, no accumulation
    }
    
    @Override
    public void onPeriodicEmit(WatermarkOutput output) {
        output.emitWatermark(new Watermark(maxTimestamp - TOLERANCE));
    }
}
```

### Prevention
- Keep watermark generators stateless or with bounded state
- Don't store per-key data in watermark generators
- Prefer built-in strategies (`forBoundedOutOfOrderness`)
