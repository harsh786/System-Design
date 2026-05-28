# Flink Windows — Quick Reference

> Condensed guide to all Flink window types with visual diagrams, code patterns, and decision guidance.

---

## Window Decision Tree

```
Need to group events by time/count?
│
├─ Fixed-size, non-overlapping chunks?
│  └─ TUMBLING WINDOW
│
├─ Fixed-size, overlapping (smoothing/trends)?
│  └─ SLIDING (HOPPING) WINDOW
│
├─ Group by inactivity gap?
│  └─ SESSION WINDOW
│
├─ Fixed number of elements (not time)?
│  └─ COUNT WINDOW
│
└─ Custom logic (manual triggers)?
   └─ GLOBAL WINDOW + custom Trigger
```

---

## At a Glance

| Window | Size | Overlap | Keyed | Use Case |
|--------|------|---------|-------|----------|
| Tumbling | Fixed time | No | Yes/No | Hourly revenue, minute counts |
| Sliding | Fixed time | Yes | Yes/No | Moving averages, trend detection |
| Session | Dynamic (gap) | No | Yes | User sessions, click streams |
| Global | Infinite | N/A | Yes | Custom trigger logic |
| Count | Fixed count | No/Yes | Yes | Batch-of-N processing |

---

## 1. Tumbling Window

**What:** Fixed-size, non-overlapping, wall-to-wall time intervals.

```
Timeline:  ──────────────────────────────────────────►
Events:     •  •  ••   •    • ••  •   •  ••   •
Windows:   |____5min____|____5min____|____5min____|
           [  window 1  ][  window 2 ][  window 3 ]

Each event belongs to exactly ONE window.
```

### Event-Time Tumbling

```java
stream
    .keyBy(event -> event.getUserId())
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .aggregate(new CountAggregate());
```

### Processing-Time Tumbling

```java
stream
    .keyBy(event -> event.getSensorId())
    .window(TumblingProcessingTimeWindows.of(Time.seconds(30)))
    .sum("value");
```

### With Offset (align to business hours)

```java
// Windows start at 08:00 instead of 00:00
stream
    .keyBy(e -> e.getRegion())
    .window(TumblingEventTimeWindows.of(
        Time.hours(1),
        Time.hours(8)  // offset
    ))
    .reduce(new MaxTemperature());
```

### Example: Hourly Revenue per Store

```java
DataStream<Transaction> transactions = ...;

transactions
    .keyBy(Transaction::getStoreId)
    .window(TumblingEventTimeWindows.of(Time.hours(1)))
    .aggregate(new AggregateFunction<Transaction, Double, StoreRevenue>() {
        public Double createAccumulator() { return 0.0; }
        public Double add(Transaction t, Double acc) { return acc + t.getAmount(); }
        public StoreRevenue getResult(Double acc) { return new StoreRevenue(acc); }
        public Double merge(Double a, Double b) { return a + b; }
    });
```

### When to Use

- Fixed reporting intervals (hourly/daily/weekly aggregates)
- Billing cycles
- Dashboard metric rollups
- Batch-style processing on streaming data

---

## 2. Sliding (Hopping) Window

**What:** Fixed-size windows that overlap. Defined by `size` and `slide`. Each event can belong to `size/slide` windows.

```
Timeline:  ──────────────────────────────────────────►
Events:     •  •  ••   •    • ••  •   •  ••   •

Size=10min, Slide=5min:
           |________10min________|
                     |________10min________|
                               |________10min________|

Event "•" at t=7 belongs to BOTH window 1 and window 2.
Overlap = size - slide = 5min
```

### Basic Pattern

```java
stream
    .keyBy(event -> event.getMetricName())
    .window(SlidingEventTimeWindows.of(
        Time.minutes(10),   // window size
        Time.minutes(5)     // slide interval
    ))
    .aggregate(new AverageAggregate());
```

### Example: 5-Minute Moving Average (updated every 1 minute)

```java
DataStream<SensorReading> readings = ...;

readings
    .keyBy(SensorReading::getSensorId)
    .window(SlidingEventTimeWindows.of(
        Time.minutes(5),   // look back 5 minutes
        Time.minutes(1)    // emit result every 1 minute
    ))
    .aggregate(new AggregateFunction<SensorReading, double[], Double>() {
        public double[] createAccumulator() { return new double[]{0.0, 0}; }
        public double[] add(SensorReading r, double[] acc) {
            acc[0] += r.getTemperature();
            acc[1] += 1;
            return acc;
        }
        public Double getResult(double[] acc) { return acc[0] / acc[1]; }
        public double[] merge(double[] a, double[] b) {
            return new double[]{a[0] + b[0], a[1] + b[1]};
        }
    });
```

### Example: Anomaly Detection (spike in last 2 min vs last 10 min)

```java
// Short-term window
DataStream<Double> shortTermAvg = readings
    .keyBy(SensorReading::getSensorId)
    .window(SlidingEventTimeWindows.of(Time.minutes(2), Time.minutes(1)))
    .aggregate(new AverageAggregate());

// Long-term window
DataStream<Double> longTermAvg = readings
    .keyBy(SensorReading::getSensorId)
    .window(SlidingEventTimeWindows.of(Time.minutes(10), Time.minutes(1)))
    .aggregate(new AverageAggregate());

// Compare: if short-term > 2x long-term → anomaly
```

### Memory Warning

```
Number of active windows per key = ceil(size / slide)

Size=1hour, Slide=1second → 3600 concurrent windows per key!
Rule of thumb: keep size/slide ratio ≤ 20
```

### When to Use

- Moving averages and trend detection
- Rate-of-change calculations
- Smoothing noisy data
- "Last N minutes" dashboards with frequent updates

---

## 3. Session Window

**What:** Dynamic-size windows that close after an inactivity gap. No fixed start/end — driven entirely by event arrival pattern.

```
Timeline:  ──────────────────────────────────────────►
Events:     •• •  •          ••• •             • •

Gap = 5min:
           |__session 1__|   |_session 2_|     |_s3_|
            (activity)    gap  (activity)  gap

Sessions merge if a new event arrives within the gap.
```

### Basic Pattern

```java
stream
    .keyBy(event -> event.getUserId())
    .window(EventTimeSessionWindows.withGap(Time.minutes(30)))
    .process(new SessionSummaryFunction());
```

### Dynamic Gap (different timeout per user tier)

```java
stream
    .keyBy(event -> event.getUserId())
    .window(EventTimeSessionWindows.withDynamicGap(
        new SessionWindowTimeGapExtractor<ClickEvent>() {
            public long extract(ClickEvent event) {
                if (event.getUserTier().equals("premium")) {
                    return Time.minutes(45).toMilliseconds();
                }
                return Time.minutes(15).toMilliseconds();
            }
        }
    ))
    .aggregate(new SessionMetrics());
```

### Example: User Session Analytics

```java
DataStream<ClickEvent> clicks = ...;

clicks
    .keyBy(ClickEvent::getUserId)
    .window(EventTimeSessionWindows.withGap(Time.minutes(30)))
    .process(new ProcessWindowFunction<ClickEvent, SessionReport, String, TimeWindow>() {
        public void process(String userId, Context ctx, 
                           Iterable<ClickEvent> events, Collector<SessionReport> out) {
            long start = ctx.window().getStart();
            long end = ctx.window().getEnd();
            int clickCount = 0;
            Set<String> pagesVisited = new HashSet<>();
            
            for (ClickEvent e : events) {
                clickCount++;
                pagesVisited.add(e.getPageUrl());
            }
            
            out.collect(new SessionReport(
                userId, 
                end - start,          // session duration
                clickCount,
                pagesVisited.size()   // unique pages
            ));
        }
    });
```

### Session Merge Visualization

```
User A events at: t=0, t=2, t=4, t=8, t=20, t=22
Gap threshold: 5 units

Step 1: t=0 → create session [0, 5)
Step 2: t=2 → merge into [0, 7)     (2 + gap=5)
Step 3: t=4 → merge into [0, 9)     (4 + gap=5)
Step 4: t=8 → merge into [0, 13)    (8 + gap=5)
         ↑ gap between 8 and 0's window end is < 5, so merge
Step 5: t=20 → new session [20, 25) (gap since 13 > 5)
Step 6: t=22 → merge into [20, 27)

Final: Session 1 = [0, 13), Session 2 = [20, 27)
```

### When to Use

- User session tracking (web, mobile, gaming)
- Conversation/interaction grouping
- Machine activity bursts (IoT)
- Any "group events until idle" pattern

---

## 4. Global Window

**What:** Single infinite window per key. Does nothing until you attach a custom `Trigger`. The "escape hatch" for custom windowing logic.

```
Timeline:  ──────────────────────────────────────────►
Events:     •  •  ••   •    • ••  •   •  ••   •
Window:    |________________ infinite ________________|

Without a trigger, this window NEVER fires.
You MUST provide a Trigger and usually an Evictor.
```

### Basic Pattern

```java
stream
    .keyBy(event -> event.getCategory())
    .window(GlobalWindows.create())
    .trigger(new MyCustomTrigger())
    .evictor(CountEvictor.of(1000))  // prevent unbounded state
    .process(new MyProcessFunction());
```

### Example: Fire on Every 100th Event OR Every 5 Minutes

```java
public class HybridTrigger extends Trigger<Event, GlobalWindow> {
    private int count = 0;
    
    public TriggerResult onElement(Event e, long ts, GlobalWindow w, TriggerContext ctx) {
        count++;
        if (count >= 100) {
            count = 0;
            return TriggerResult.FIRE_AND_PURGE;
        }
        // Register a timer for 5-minute timeout
        ctx.registerProcessingTimeTimer(ctx.getCurrentProcessingTime() + 300_000);
        return TriggerResult.CONTINUE;
    }
    
    public TriggerResult onProcessingTime(long time, GlobalWindow w, TriggerContext ctx) {
        count = 0;
        return TriggerResult.FIRE_AND_PURGE;
    }
    
    public TriggerResult onEventTime(long time, GlobalWindow w, TriggerContext ctx) {
        return TriggerResult.CONTINUE;
    }
    
    public void clear(GlobalWindow w, TriggerContext ctx) { count = 0; }
}
```

### Example: Fire When a "Complete" Signal Arrives

```java
stream
    .keyBy(Order::getOrderId)
    .window(GlobalWindows.create())
    .trigger(new Trigger<OrderEvent, GlobalWindow>() {
        public TriggerResult onElement(OrderEvent e, long ts, 
                                       GlobalWindow w, TriggerContext ctx) {
            if (e.getType() == EventType.ORDER_COMPLETED) {
                return TriggerResult.FIRE_AND_PURGE;
            }
            return TriggerResult.CONTINUE;
        }
        // ... other methods return CONTINUE
    })
    .process(new BuildCompleteOrder());
```

### When to Use

- Business-logic–driven window boundaries
- Event-count + time hybrid triggers
- Waiting for a "completion" event
- Complex custom windowing not covered by other types

---

## 5. Count Window

**What:** Windows that fire after a fixed number of elements per key. Not time-based.

```
Events per key: • • • • • • • • • • • •
Count window(4):
               [• • • •][• • • •][• • • •]
               window 1  window 2  window 3

Each window fires after exactly 4 events for that key.
```

### Tumbling Count Window

```java
stream
    .keyBy(event -> event.getDeviceId())
    .countWindow(100)  // fire every 100 events per key
    .aggregate(new BatchStatistics());
```

### Sliding Count Window

```java
// Window of 100 elements, slides every 10
stream
    .keyBy(event -> event.getSymbol())
    .countWindow(100, 10)
    .aggregate(new MovingAveragePrice());
```

### Example: Micro-Batch to External System

```java
DataStream<LogEntry> logs = ...;

logs
    .keyBy(LogEntry::getService)
    .countWindow(500)  // batch 500 logs together
    .process(new ProcessWindowFunction<LogEntry, BulkPayload, String, GlobalWindow>() {
        public void process(String service, Context ctx, 
                           Iterable<LogEntry> logs, Collector<BulkPayload> out) {
            List<LogEntry> batch = new ArrayList<>();
            logs.forEach(batch::add);
            out.collect(new BulkPayload(service, batch));
        }
    });
```

### Caveat: Starvation Risk

```
If a key receives events slowly:
  Key "A": gets 100 events/sec  → window fires every 1 second ✓
  Key "B": gets 1 event/min     → window fires after 100 MINUTES! ✗

Solution: Combine with a processing-time trigger timeout,
or use a Global Window with a count+time hybrid trigger.
```

### When to Use

- Micro-batching for bulk APIs (Elasticsearch, S3, databases)
- Statistical sampling (every Nth event)
- Rate-independent grouping (process N items regardless of speed)

---

## Watermarks & Late Data

### How Watermarks Drive Window Firing

```
Event-time progress:
  Events:    e(t=3) e(t=7) e(t=5) e(t=9) e(t=12)
  Watermark:  W=2    W=6    W=6    W=8    W=11

Window [0,10) fires when watermark passes 10.
  → fires after e(t=12) arrives (W=11 ≥ 10)
  → e(t=5) arrived "late" relative to W=6 but is STILL in window [0,10)
```

### Allowed Lateness

```java
stream
    .keyBy(e -> e.getKey())
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .allowedLateness(Time.minutes(2))  // keep window state 2 extra minutes
    .sideOutputLateData(lateOutputTag)  // events beyond lateness go here
    .aggregate(new MyAggregate());

// Collect truly late events
DataStream<Event> lateEvents = result.getSideOutput(lateOutputTag);
```

### Lateness Timeline

```
Window [0, 5min):
  ├── Watermark reaches 5min → FIRE (first result)
  ├── Late event at t=3, watermark=6 → FIRE again (updated result)
  ├── Late event at t=4, watermark=6.5 → FIRE again (updated result)
  ├── Watermark reaches 7min (5 + 2min lateness) → PURGE state
  └── Event at t=2, watermark=8 → dropped (or side output)
```

---

## Triggers Reference

| Trigger | Fires When | Use With |
|---------|-----------|----------|
| `EventTimeTrigger` | Watermark passes window end | Event-time windows (default) |
| `ProcessingTimeTrigger` | Wall clock passes window end | Processing-time windows (default) |
| `CountTrigger` | N elements in window | Global windows |
| `PurgingTrigger` | Wraps another trigger + clears state | Any window needing state reset |
| `DeltaTrigger` | Value delta exceeds threshold | Global windows, change detection |
| `ContinuousEventTimeTrigger` | Every N time units (event-time) | Early results from long windows |
| `ContinuousProcessingTimeTrigger` | Every N time units (wall clock) | Early results from long windows |

### Early Results Pattern

```java
// Emit partial results every 30 seconds for a 5-minute window
stream
    .keyBy(e -> e.getKey())
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .trigger(ContinuousProcessingTimeTrigger.of(Time.seconds(30)))
    .aggregate(new RunningCount());
```

---

## Evictors Reference

| Evictor | Behavior | Typical Use |
|---------|----------|-------------|
| `CountEvictor.of(n)` | Keep last N elements | Bound state in global windows |
| `TimeEvictor.of(time)` | Keep elements within time range | Sliding-style over global window |
| `DeltaEvictor` | Keep elements within delta threshold | Outlier removal |

```java
// Global window that keeps only the last 1000 events
stream
    .keyBy(e -> e.getKey())
    .window(GlobalWindows.create())
    .trigger(CountTrigger.of(100))
    .evictor(CountEvictor.of(1000))
    .process(new MyFunction());
```

---

## Aggregation Functions Comparison

| Function | State | Access to All Elements | Incremental | Use When |
|----------|-------|----------------------|-------------|----------|
| `ReduceFunction` | Single value (same type as input) | No | Yes | Sum, min, max |
| `AggregateFunction` | Accumulator (any type) | No | Yes | Average, complex aggs |
| `ProcessWindowFunction` | All elements buffered | Yes | No | Need metadata (window bounds, key) |
| `Aggregate + Process` | Combined | Yes (final result) | Yes | Incremental + metadata |

### Best Practice: AggregateFunction + ProcessWindowFunction

```java
// Incremental aggregation with window metadata
stream
    .keyBy(e -> e.getKey())
    .window(TumblingEventTimeWindows.of(Time.hours(1)))
    .aggregate(
        new MyAggregateFunction(),       // incremental: O(1) memory
        new MyProcessWindowFunction()    // adds window start/end to result
    );

// ProcessWindowFunction receives the pre-aggregated result, not all elements
public class MyProcessWindowFunction 
    extends ProcessWindowFunction<AggResult, FinalOutput, String, TimeWindow> {
    
    public void process(String key, Context ctx, 
                       Iterable<AggResult> results, Collector<FinalOutput> out) {
        AggResult agg = results.iterator().next();  // single pre-aggregated value
        out.collect(new FinalOutput(
            key, 
            ctx.window().getStart(), 
            ctx.window().getEnd(), 
            agg
        ));
    }
}
```

---

## Keyed vs Non-Keyed Windows

```
Keyed (parallel, per-key state):
  stream.keyBy(e -> e.getKey())
        .window(...)         → KeyedStream window

Non-keyed (parallelism=1, single operator):
  stream.windowAll(...)      → All-window (use sparingly)

Rule: Always prefer keyed windows. Non-keyed = bottleneck.
```

---

## Common Patterns

### Pattern 1: Late Event Recovery

```java
OutputTag<Event> lateTag = new OutputTag<>("late"){};

SingleOutputStreamOperator<Result> result = stream
    .keyBy(e -> e.getKey())
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .allowedLateness(Time.minutes(10))
    .sideOutputLateData(lateTag)
    .aggregate(new MyAgg());

// Re-process late events with longer window
result.getSideOutput(lateTag)
    .keyBy(e -> e.getKey())
    .window(TumblingEventTimeWindows.of(Time.hours(1)))
    .aggregate(new LateRecoveryAgg());
```

### Pattern 2: Window Join (two streams)

```java
streamA
    .join(streamB)
    .where(a -> a.getId())
    .equalTo(b -> b.getId())
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .apply((a, b) -> new JoinedResult(a, b));
```

### Pattern 3: Interval Join (bounded time difference)

```java
// Join events where B arrives within [-5min, +5min] of A
streamA
    .keyBy(a -> a.getId())
    .intervalJoin(streamB.keyBy(b -> b.getId()))
    .between(Time.minutes(-5), Time.minutes(5))
    .process(new IntervalJoinFunction());
```

### Pattern 4: Pre-Aggregation for High-Cardinality Keys

```java
// Two-phase: local pre-agg then global agg
stream
    .keyBy(e -> e.getKey())
    .window(TumblingEventTimeWindows.of(Time.minutes(1)))
    .aggregate(new LocalCount())  // per-key partial count
    .keyBy(r -> "global")
    .window(TumblingEventTimeWindows.of(Time.minutes(1)))
    .aggregate(new GlobalSum());  // sum all partial counts
```

---

## Performance & State Considerations

| Concern | Guideline |
|---------|-----------|
| State size | Use `AggregateFunction` (O(1)) over `ProcessWindowFunction` (O(n)) |
| Sliding windows | Keep `size/slide ≤ 20` to limit concurrent windows |
| Session windows | Set realistic gap; very short gaps = many small windows = high state |
| Late data | `allowedLateness` extends state lifetime; balance accuracy vs memory |
| Count windows | Add time-based timeout to prevent starvation on slow keys |
| Global windows | Always use `Evictor` to bound state growth |
| Checkpointing | Larger window state = slower checkpoints; tune interval accordingly |
| Parallelism | Keyed windows scale with parallelism; non-keyed (windowAll) = parallelism 1 |

---

## Quick Comparison: Which Window?

```
┌─────────────────────────────────────────────────────────────────┐
│ "I want to..."                        │ Use                     │
├───────────────────────────────────────┼─────────────────────────┤
│ Aggregate every 5 minutes             │ Tumbling(5min)          │
│ Compute a 1-hour moving average       │ Sliding(1h, 5min)      │
│ Group user activity into sessions     │ Session(30min gap)      │
│ Process every 100 events              │ countWindow(100)        │
│ Fire on a business event              │ Global + custom trigger │
│ Get early partial results             │ Any + Continuous trigger│
│ Handle late data gracefully           │ Any + allowedLateness   │
│ Join two streams in same time bucket  │ Window Join             │
│ Join with bounded time difference     │ Interval Join           │
└───────────────────────────────────────┴─────────────────────────┘
```

---

## Anti-Patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| `ProcessWindowFunction` for simple sums | Buffers all events in state | Use `ReduceFunction` or `AggregateFunction` |
| Very small slide (1s) with large size (1h) | 3600 concurrent windows per key | Increase slide or reduce size |
| Count window on skewed keys | Hot keys fire fast, cold keys never fire | Add time-based fallback trigger |
| No `allowedLateness` with event-time | Late events silently dropped | Set lateness + side output |
| `windowAll()` in production | Parallelism bottleneck (=1) | Use `keyBy()` + `window()` |
| Unbounded global window without evictor | State grows forever → OOM | Add `CountEvictor` or `TimeEvictor` |

---

*Quick reference companion to `flink-event-processing-deep-dive.md`*
