# Apache Flink Event Processing Deep Dive

This note explains how Flink works end to end for a typical real-time event
processing pipeline:

```text
Event arrives
   |
   v
Event-time assignment + watermark
   |
   v
Dedupe using keyed state
   |
   v
Window aggregation
   |
   v
Join / enrichment
   |
   v
Sink, for example Apache Pinot
```

## 1. What Flink Is

Apache Flink is a distributed stream processing engine. It processes both
unbounded streams, such as Kafka topics, and bounded streams, such as files or
backfills, using the same runtime.

A Flink application is a directed graph of operators:

```text
Kafka Source
  -> Parse / validate
  -> Assign event time and watermarks
  -> keyBy
  -> Dedupe
  -> Window aggregation
  -> Join / enrichment
  -> Sink
```

The most important runtime pieces are:

- `JobManager`: coordinates the Flink job, schedules tasks, manages checkpoints,
  and handles recovery.
- `TaskManager`: runs the actual operators.
- `Task slot`: execution resource inside a TaskManager.
- `Operator`: one processing step, such as `map`, `filter`, `keyBy`, `window`,
  `join`, or `sink`.
- `Subtask`: one parallel instance of an operator.
- `Parallelism`: the number of subtasks for an operator.
- `State`: durable memory owned by operators, for example seen event IDs, window
  aggregates, join buffers, counters, or dimension cache.
- `Checkpoint`: a consistent snapshot of source positions and operator state.

Flink is useful because it combines:

- Low-latency stream processing.
- Stateful processing.
- Event-time correctness.
- Out-of-order event handling.
- Fault tolerance through checkpoints.
- Exactly-once state consistency.
- Integration with systems such as Kafka, databases, object storage, and Pinot.

## 2. Basic Event Processing Flow

Suppose an event arrives from Kafka:

```json
{
  "event_id": "evt-1001",
  "user_id": "u-7",
  "merchant_id": "m-9",
  "amount": 250,
  "event_time": "2026-05-24T10:00:03Z"
}
```

Flink typically processes it like this:

```text
1. Source reads the event from Kafka.
2. Event is deserialized and validated.
3. Flink extracts event_time from the record.
4. Flink assigns timestamp and updates watermarks.
5. Event is repartitioned with keyBy, for example by event_id or merchant_id.
6. Dedupe checks keyed state.
7. Unique event updates a window aggregate.
8. Window emits when watermark passes the window end.
9. Result is joined with dimension data or another stream.
10. Final row is written to a sink such as Kafka, Pinot, Iceberg, or a database.
```

## 3. Streams, Partitions, and `keyBy`

Flink parallelizes work across subtasks. To do correct stateful work, related
events must go to the same subtask.

That is what `keyBy` does.

Example:

```text
keyBy(event_id)       -> all duplicates of one event go to the same subtask
keyBy(user_id)        -> all user activity goes to the same subtask
keyBy(merchant_id)    -> all merchant metrics go to the same subtask
```

After `keyBy`, Flink can safely maintain per-key state:

```text
Key: event_id
State: has this event already been seen?
```

or:

```text
Key: merchant_id
State: rolling revenue for current window
```

If the key is wrong, correctness breaks. For example, dedupe by `event_id` only
works if the stream is keyed by `event_id` before the dedupe operator.

## 4. Time in Flink

There are three common notions of time.

### Processing Time

Processing time is the wall-clock time on the Flink machine.

Example:

```text
The event arrived at Flink at 10:01:00.
```

Processing time is simple and fast, but it is not correct for delayed or
out-of-order events.

### Event Time

Event time is the timestamp inside the event.

Example:

```text
event_time = 10:00:03
```

Event time is the preferred choice for most real systems because it represents
when the business action actually happened.

### Ingestion Time

Ingestion time is when Flink first sees the event. It sits between event time
and processing time, but it is less commonly used for correctness-sensitive
pipelines.

## 5. Event-Time Assignment

Flink needs to know which field represents event time.

Conceptually:

```text
timestamp = event.event_time
```

With event-time processing, Flink does not decide window completion based on
machine time. It decides based on watermarks.

## 6. Watermarks

A watermark is Flink's estimate of event-time progress.

If the current watermark is:

```text
10:05:00
```

then Flink is saying:

```text
I believe I have probably seen all events up to event time 10:05:00.
```

For bounded out-of-order streams, the common formula is:

```text
watermark = max_event_time_seen - allowed_out_of_orderness
```

Example:

```text
Max event time seen:          10:05:30
Allowed out-of-orderness:     30 seconds
Current watermark:            10:05:00
```

This means Flink will still accept events around `10:05:00`, but a much older
event may be treated as late.

Watermarks are what let Flink close event-time windows.

Example:

```text
Window: [10:00, 10:05)
Window closes when watermark >= 10:05
```

## 7. Out-of-Order Events

Streams are often not ordered by event time.

Example arrival order:

```text
Event A: event_time = 10:00:01
Event B: event_time = 10:00:05
Event C: event_time = 10:00:03
```

Event C is out of order because it arrived after a newer event. It is not
necessarily late. It is late only if the watermark has already passed the time
or the window it belongs to.

The distinction matters:

```text
Out-of-order event:
  Arrives after newer events, but before the watermark has closed its window.

Late event:
  Arrives after the watermark has closed its window.
```

## 8. Allowed Lateness

Allowed lateness tells Flink how long to keep a window around after the first
result is emitted.

Example:

```text
Window:           [10:00, 10:05)
Watermark:        reaches 10:05
Flink emits:      first result
Allowed lateness: 2 minutes
Cleanup time:     watermark reaches 10:07
```

If a late event for `[10:00, 10:05)` arrives before the watermark reaches
`10:07`, Flink can update the window and emit another result.

If it arrives after cleanup, Flink usually drops it or sends it to a side output.

Important consequences:

- Higher allowed lateness improves correctness for delayed events.
- Higher allowed lateness increases state size.
- Late updates can cause multiple output rows for the same window.
- If the sink is append-only, late updates can create duplicate-looking results.
- If the sink supports upsert, late updates can replace older results.

## 9. Dedupe

Duplicate events happen because of retries, producer bugs, source replay,
network failures, and recovery.

Typical dedupe logic:

```text
keyBy(event_id)

if event_id has not been seen:
    mark event_id as seen
    emit event
else:
    drop event
```

The state might look like:

```text
Key: event_id
Value: true
TTL: 24 hours
```

TTL is important. If duplicates can arrive up to 7 days late, but dedupe state
expires after 1 hour, duplicates after 1 hour will pass through.

Common dedupe keys:

- `event_id`: best option for raw event dedupe.
- `business_id + version`: useful for update streams.
- `user_id + action + event_time`: fallback when no true event ID exists, but
  this can produce false positives or false negatives.

Dedupe usually happens before aggregation:

```text
Raw events -> dedupe -> window aggregation
```

If duplicates are not removed before aggregation, counts and sums become wrong.

## 10. Keyed State

Keyed state is state scoped to a key after `keyBy`.

Examples:

```text
keyBy(event_id)
  ValueState<Boolean> seen
```

```text
keyBy(merchant_id)
  ValueState<Long> order_count
  ValueState<Double> revenue
```

```text
keyBy(order_id)
  ValueState<Order> order
  ValueState<Payment> payment
```

Common state types:

- `ValueState`: one value per key.
- `ListState`: list of values per key.
- `MapState`: map per key.
- `ReducingState`: state maintained through reduce logic.
- `AggregatingState`: state maintained through aggregate logic.
- `BroadcastState`: shared state broadcast to all parallel subtasks, commonly
  used for dimension data or rules.

State needs cleanup. Without TTL or timer-based cleanup, state grows forever.

## 11. Timers

Timers let a keyed process function do work at a future event-time or
processing-time point.

Example use cases:

- Remove dedupe state after TTL.
- Emit an alert if a matching event does not arrive within 10 minutes.
- Close custom sessions.
- Delay output until enough event-time progress has happened.

Event-time timers fire when the watermark passes the timer timestamp.

Processing-time timers fire based on machine clock time.

## 12. Windows

Windows group events by key and time.

Usually the structure is:

```text
stream
  -> keyBy(...)
  -> window(...)
  -> aggregate(...)
```

Flink stores state per:

```text
key + window
```

Example:

```text
Key: merchant_id = m-9
Window: [10:00, 10:05)
State:
  order_count = 98
  total_amount = 12345
```

When the watermark passes the window end, Flink emits the aggregate.

Example output:

```json
{
  "merchant_id": "m-9",
  "window_start": "2026-05-24T10:00:00Z",
  "window_end": "2026-05-24T10:05:00Z",
  "order_count": 98,
  "total_amount": 12345
}
```

## 13. Tumbling Windows

A tumbling window has fixed size and does not overlap.

Example: 5-minute tumbling windows.

```text
[10:00, 10:05)
[10:05, 10:10)
[10:10, 10:15)
```

Each event belongs to exactly one window.

Use cases:

- Revenue per minute.
- Orders per hour.
- Active users per day.
- Error count per 5 minutes.

## 14. Sliding Windows

A sliding window has fixed size but overlaps.

In Flink SQL, this is commonly called a hopping window and is expressed with
`HOP`. A hopping window has two important parameters:

```text
Window size = how much time each window covers
Hop size    = how often a new window starts
```

Example:

```text
Window size: 10 minutes
Hop size:    5 minutes

[10:00, 10:10)
[10:05, 10:15)
[10:10, 10:20)
```

One event can belong to multiple windows.

Example:

```text
Event time: 10:07

Belongs to:
  [10:00, 10:10)
  [10:05, 10:15)
```

Flink SQL example:

```sql
SELECT
  window_start,
  window_end,
  user_id,
  COUNT(*) AS event_count
FROM HOP(
  TABLE events,
  DESCRIPTOR(event_time),
  INTERVAL '5' MINUTES,
  INTERVAL '10' MINUTES
)
GROUP BY window_start, window_end, user_id;
```

This means:

```text
Every 5 minutes, calculate metrics over the last 10 minutes.
```

Use cases:

- Rolling 10-minute error count.
- Moving average.
- Fraud signals over the last N minutes.
- Monitoring dashboards.

Tradeoff:

```text
More overlap = more state and more computation.
```

## 15. Session Windows

A session window is based on inactivity gap.

Example:

```text
Session gap: 5 minutes

User event at 10:00
User event at 10:01
User event at 10:03
Same session

User event at 10:20
New session
```

Use cases:

- User web sessions.
- Shopping journeys.
- Chat activity.
- App usage bursts.

Session windows are dynamic. Flink may merge session windows if events arrive
that connect two sessions.

## 16. Global Windows

A global window puts all events for a key into one logical window.

It does not naturally close by event time. You need a trigger.

Use cases:

- Custom count-based processing.
- Custom triggers.
- Long-running keyed state patterns.

Global windows are powerful but easy to misuse because state can grow without
careful cleanup.

## 17. Count Windows

A count window fires after a number of events.

Example:

```text
Every 100 events per key
```

Use cases:

- Batch every N records.
- Emit every N sensor readings.

Count windows are not event-time windows. They do not care whether events are
old, new, delayed, or out of order.

## 18. Window Triggers

A trigger decides when a window emits.

Common behavior:

```text
Emit when watermark passes window end.
```

Other possible triggers:

- Emit early every N seconds.
- Emit when count reaches N.
- Emit on processing time.
- Emit on custom business condition.

Early triggers can reduce latency but may produce multiple updates for the same
window.

## 19. Window Evictors

An evictor removes elements from a window before or after processing.

Evictors are less common in high-throughput systems because they often require
keeping more raw events instead of only incremental aggregate state.

Prefer incremental aggregation when possible.

## 20. Window Aggregation Functions

Common aggregation options:

- `ReduceFunction`: combines two records into one record.
- `AggregateFunction`: maintains compact accumulator state.
- `ProcessWindowFunction`: has access to window metadata and all elements.
- `AggregateFunction + ProcessWindowFunction`: efficient aggregate plus access
  to window start/end metadata.

Best practice for scalable windows:

```text
Use incremental aggregation where possible.
Avoid storing every event in the window unless needed.
```

## 21. Joins and Enrichment

Enrichment adds context to events.

Example:

```text
Order event:
  merchant_id = m-9

Merchant dimension:
  merchant_id = m-9
  category = grocery
  country = IN

Enriched event:
  merchant_id = m-9
  category = grocery
  country = IN
```

There are several patterns.

## 22. Static or Slowly Changing Dimension Enrichment

If the dimension data is small enough, use broadcast state.

```text
Dimension updates -> broadcast to all subtasks
Events -> keyed stream
BroadcastProcessFunction joins event with local broadcast state
```

Use this for:

- Rules.
- Small lookup tables.
- Configuration.
- Feature flags.
- Merchant metadata if it fits in memory.

## 23. Async I/O Enrichment

If the dimension table is large or lives in an external database, use async I/O.

```text
Event -> async lookup in Redis / Cassandra / database / service -> enriched event
```

Benefits:

- Avoids blocking Flink operator threads.
- Allows many concurrent lookups.

Risks:

- External service latency affects pipeline latency.
- Retries can duplicate calls.
- Need timeouts and fallback behavior.
- Exactly-once output does not mean the external lookup is exactly once.

## 24. Stream-Stream Joins

Stream-stream joins combine two live streams.

Example:

```text
Orders stream
Payments stream

Join on order_id
Payment must arrive within 15 minutes of order
```

Flink must buffer records from both sides:

```text
Key: order_id
State:
  order event
  payment event
```

When a match arrives, Flink emits a joined record.

Watermarks and timers are used to clean up old unmatched state.

## 25. Interval Joins

An interval join joins two keyed streams where timestamps are within a time
range.

Example:

```text
payment.order_id = order.order_id
payment.event_time between order.event_time and order.event_time + 15 minutes
```

Use cases:

- Order and payment matching.
- Click and impression attribution.
- Request and response matching.

State size depends on the interval length and event volume.

## 26. Temporal Joins

Temporal joins are common in Flink SQL.

They join a stream event with a versioned table as of the event time.

Example:

```text
Order at 10:05 joins merchant dimension as it existed at 10:05.
```

Use this when dimension values change over time and historical correctness
matters.

## 27. Checkpointing

Checkpointing is Flink's fault-tolerance mechanism.

It snapshots:

- Source offsets or positions.
- Operator state.
- Window state.
- Dedupe state.
- Join state.
- Sink state, if the sink participates.

Simplified checkpoint flow:

```text
1. Source emits records.
2. Flink injects checkpoint barrier #42.
3. Operators process all records before the barrier.
4. Operators snapshot their state.
5. Sink snapshots pending output if supported.
6. Checkpoint #42 completes.
```

If the job fails:

```text
1. Flink restores checkpoint #42.
2. Source resumes from checkpointed offsets.
3. Dedupe/window/join state is restored.
4. Records after checkpoint #42 are replayed.
```

This is why source replayability matters.

Kafka is a good source because Flink can restore offsets and replay records.

## 28. Aligned and Unaligned Checkpoints

Aligned checkpoints wait for checkpoint barriers to line up across inputs.

This gives clean consistency, but under backpressure checkpointing can become
slow.

Unaligned checkpoints can include in-flight data in the checkpoint. They can
reduce checkpoint time under backpressure, but checkpoint size may grow.

Use unaligned checkpoints when backpressure causes checkpoint timeouts, and
verify the operational tradeoffs.

## 29. Savepoints

A savepoint is a manually triggered consistent snapshot.

Use savepoints for:

- Deploying a new version of a job.
- Changing code safely.
- Migrating a job.
- Pausing and resuming processing.

Checkpoint:

```text
Automatic fault-tolerance snapshot.
```

Savepoint:

```text
User-controlled operational snapshot.
```

## 30. Exactly-Once Semantics

Exactly-once is often misunderstood.

There are two levels:

1. Exactly-once state consistency inside Flink.
2. End-to-end exactly-once delivery into the sink.

## 31. Flink Internal Exactly-Once

Flink can guarantee that its internal state is updated exactly once with respect
to the input stream.

Example state:

```text
Kafka offset
Dedupe seen-event state
Window aggregate state
Join buffer state
```

These are checkpointed together.

If the job fails, Flink restores the last completed checkpoint and replays input
after that checkpoint.

So the final state is correct as if each input event was applied once.

## 32. End-to-End Exactly-Once

End-to-end exactly-once requires all of the following:

```text
Replayable source
+ Flink checkpointing
+ deterministic processing
+ sink that is transactional or idempotent
```

If the sink does not participate in checkpoints, Flink may recover correctly
internally while the external sink still sees duplicates.

Examples:

- Kafka transactional sink can provide strong exactly-once behavior.
- File/table formats with checkpoint-aware commit protocols can provide strong
  guarantees.
- Plain HTTP calls usually cannot provide exactly-once writes by themselves.
- Databases can be effectively exactly-once if writes are idempotent by primary
  key or transactional with checkpoint coordination.

Important rule:

```text
Flink exactly-once state does not automatically mean exactly-once writes to
every external system.
```

## 33. Two-Phase Commit Sink Pattern

Some sinks use a two-phase commit style:

```text
1. Write data into a pending transaction.
2. Snapshot transaction handle during checkpoint.
3. Commit transaction only when checkpoint completes.
4. Abort pending transaction if checkpoint fails or job restarts.
```

This allows the sink to align external visibility with Flink checkpoints.

Without this, a failure can happen after writing to the sink but before the
checkpoint completes. On recovery, Flink replays records and the sink may get
duplicates.

## 34. Idempotent Sink Pattern

If the sink cannot do two-phase commit, make writes idempotent.

Example for window aggregates:

```text
Primary key = merchant_id + window_start + window_end
```

If Flink writes the same aggregate again after recovery, the sink overwrites the
same row instead of inserting another row.

This is the common practical approach with serving stores.

## 35. Backpressure

Backpressure happens when downstream operators or sinks are slower than upstream
operators.

Example:

```text
Source reads 100k events/sec
Sink writes 40k events/sec
```

Backpressure propagates upstream. Flink slows the source, checkpointing may take
longer, and latency increases.

Common causes:

- Slow external sink.
- Hot keys.
- Too much window state.
- Slow async lookup dependency.
- Insufficient parallelism.
- Large serialization cost.

Common fixes:

- Increase sink parallelism.
- Repartition better.
- Add buffering carefully.
- Tune checkpointing.
- Use async I/O.
- Reduce per-event work.
- Fix hot keys with key salting where business logic allows.

## 36. How the Full Pipeline Works

Given this pipeline:

```text
Event arrives
   |
   v
Event-time assignment + watermark
   |
   v
Dedupe
   |
   v
Window aggregation
   |
   v
Join
   |
   v
Sink
```

Detailed processing:

```text
1. Kafka source reads event at offset 500.
2. Flink deserializes event.
3. Event timestamp is assigned from event_time.
4. Watermark strategy updates event-time progress.
5. keyBy(event_id) sends the event to the dedupe subtask for that event ID.
6. Dedupe checks ValueState.
7. If unseen, it marks event_id as seen and emits the event.
8. keyBy(merchant_id) sends the event to the aggregation subtask for that merchant.
9. Event is assigned to a window, for example [10:00, 10:05).
10. Window accumulator updates count and sum.
11. When watermark >= 10:05, Flink emits the aggregate.
12. Aggregate is enriched with merchant metadata.
13. Final record is written to the sink.
14. Checkpoint snapshots Kafka offset, dedupe state, window state, join state,
    and sink state if supported.
```

## 37. Example: Fraud or Analytics Pipeline

Input:

```json
{
  "event_id": "evt-1",
  "user_id": "u1",
  "merchant_id": "m1",
  "amount": 100,
  "event_time": "2026-05-24T10:01:10Z"
}
```

Pipeline:

```text
Kafka raw_orders
  -> Flink timestamp + watermark
  -> dedupe by event_id
  -> enrich merchant_id with merchant category
  -> 5-minute merchant revenue tumbling window
  -> join with risk rules
  -> emit merchant_window_metrics
  -> sink to Kafka or Pinot
```

Output:

```json
{
  "merchant_id": "m1",
  "category": "grocery",
  "window_start": "2026-05-24T10:00:00Z",
  "window_end": "2026-05-24T10:05:00Z",
  "order_count": 42,
  "total_amount": 9500,
  "updated_at": "2026-05-24T10:05:30Z"
}
```

## 38. Pinot as the Sink

Apache Pinot is a real-time OLAP serving system. It is optimized for low-latency
analytical queries over high-volume data.

Pinot is not where event-time correctness is computed. Flink computes event-time
logic. Pinot stores and serves the results.

Typical architecture:

```text
Kafka raw_events
   |
   v
Flink
   |
   v
Kafka pinot_ready_events
   |
   v
Pinot realtime table
   |
   v
Dashboards / APIs
```

Another possible architecture:

```text
Kafka / files
   |
   v
Flink
   |
   v
PinotSinkFunction
   |
   v
Pinot segments uploaded to Pinot
```

The Kafka-in-the-middle pattern is often operationally cleaner for real-time
pipelines because Kafka remains the durable replay log between Flink and Pinot.

## 39. Pinot Flink Connector

Pinot provides a Flink connector with `PinotSinkFunction`.

The connector can be integrated into Flink streaming or batch jobs. It buffers
records, generates Pinot segments, and uploads them to the Pinot cluster.

According to Pinot documentation, the connector supports:

- Offline tables.
- Realtime tables.
- Full upsert tables.

Important limitation:

```text
Flink-based upload is not recommended for partial upsert tables unless the
uploaded data represents the final state for each primary key.
```

For partial upsert use cases, stream-based ingestion is often safer.

## 40. Writing Raw Events to Pinot

If Flink writes raw or enriched events to Pinot, choose a stable primary key.

Example:

```text
primary key = event_id
time column = event_time
```

Benefits:

- Pinot dedup can drop duplicate event IDs.
- Replays from Flink or Kafka are safer.
- Queries can inspect raw event details.

Pinot dedup requires a primary key. If a record arrives with an already known
primary key, Pinot drops the duplicate.

## 41. Writing Window Aggregates to Pinot

If Flink writes aggregate rows to Pinot, use a deterministic aggregate key.

Example primary key:

```text
merchant_id + window_start + window_end
```

Example row:

```json
{
  "merchant_id": "m1",
  "window_start": "2026-05-24T10:00:00Z",
  "window_end": "2026-05-24T10:05:00Z",
  "order_count": 98,
  "total_amount": 12345,
  "updated_at": "2026-05-24T10:05:30Z"
}
```

For Pinot upsert:

```text
primary key = merchant_id + window_start + window_end
comparison column = updated_at or version
```

This allows a late Flink update for the same window to replace the older value.

## 42. Late Events and Pinot

Suppose Flink emits:

```text
Window: [10:00, 10:05)
Count: 100
```

Then a late event arrives within allowed lateness. Flink updates the window:

```text
Window: [10:00, 10:05)
Count: 101
```

If Pinot is append-only, Pinot may store both:

```text
merchant=m1, window=10:00-10:05, count=100
merchant=m1, window=10:00-10:05, count=101
```

That can make queries wrong unless queries select only the latest row.

Better options:

- Use Pinot upsert with deterministic primary key.
- Use Pinot dedup for raw event tables.
- Use a Kafka compacted topic before Pinot when appropriate.
- Set `allowedLateness = 0` if the business accepts dropping late events.
- Send very late events to a correction pipeline.

## 43. Pinot Upsert

Pinot upsert keeps the latest record for a primary key.

For full upsert, a new record replaces the older record completely.

Pinot uses a comparison column to decide which record is newer. By default this
is often the table time column, but it can be configured.

Example:

```text
Primary key:       merchant_id + window_start + window_end
Comparison column: updated_at
```

If a row arrives with the same primary key and a larger comparison value, Pinot
keeps the newer row.

If a row arrives with a smaller comparison value, Pinot can skip it as
out-of-order.

## 44. Pinot Dedup

Pinot dedup drops records whose primary key has already been seen.

Use this for raw immutable events:

```text
primary key = event_id
```

Do not use plain dedup for mutable aggregate rows if late updates should replace
old values. For aggregates, upsert is usually a better fit.

## 45. Pinot Partitioning Requirements

For Pinot upsert and dedup tables, partitioning matters.

Records with the same primary key must go to the correct partition so Pinot can
make consistent dedup or upsert decisions.

If the original stream is not partitioned by the required primary key, Flink can
repartition it before writing:

```text
Flink keyBy / partitionCustom on primary key
```

For direct Pinot segment upload into upsert tables, Pinot documentation calls
out strict requirements:

- Data must be partitioned using the same strategy as the upstream stream.
- Flink job parallelism should match the number of upstream stream or table
  partitions.
- The comparison column must have ordering consistent with the upstream stream.

## 46. Exactly-Once With Pinot

Flink can provide exactly-once state consistency internally.

But end-to-end exactly-once into Pinot depends on the sink path.

If writing:

```text
Flink -> Pinot direct sink
```

then validate the exact connector version and its checkpoint behavior. Do not
assume every external write is exactly-once just because Flink checkpointing is
enabled.

Practical protection:

```text
Use deterministic primary keys.
Use Pinot upsert or dedup where appropriate.
Use deterministic window keys.
Use comparison columns for aggregate replacement.
Keep Kafka as a replayable boundary when possible.
```

For stronger operational isolation, prefer:

```text
Flink -> Kafka transactional/idempotent sink -> Pinot realtime ingestion
```

This gives you:

- Replayable handoff.
- Easier backfills.
- Easier debugging.
- Better isolation between stream processing and serving storage.

## 47. Recommended Real-Time Analytics Architecture

Recommended architecture for most Flink-to-Pinot systems:

```text
Kafka raw_events
   |
   v
Flink
   - parse
   - validate
   - assign event time
   - generate watermarks
   - dedupe by event_id
   - enrich dimensions
   - compute windows
   - emit deterministic output rows
   |
   v
Kafka pinot_ready_events
   |
   v
Pinot realtime table
   - dedup for raw events
   - upsert for mutable aggregates
   |
   v
Dashboard / API / analytics query
```

For aggregate table:

```text
Primary key:
  business_key + window_start + window_end

Comparison column:
  updated_at or version
```

For raw event table:

```text
Primary key:
  event_id

Time column:
  event_time
```

## 48. Backfill Architecture

For backfills:

```text
Files / Kafka replay
   |
   v
Flink batch or bounded stream job
   |
   v
Pinot segment generation / upload
```

Backfills need special care with upsert tables:

- Use the same primary key.
- Use consistent partitioning.
- Use correct comparison column values.
- Avoid writing partial intermediate states into partial upsert tables.
- Ensure backfilled rows do not overwrite newer real-time rows accidentally.

## 49. Design Checklist

Before building a Flink pipeline, answer these questions.

Event identity:

- Does every event have a stable `event_id`?
- What is the dedupe key?
- How long can duplicates arrive after the original?

Time:

- What field is event time?
- How late can events arrive?
- What out-of-orderness bound should watermarks use?
- What happens to very late events?

Windows:

- Do you need tumbling, sliding, session, count, or custom windows?
- Should late events update previous results?
- Does the sink support updates?

State:

- How large can dedupe state get?
- How large can window state get?
- Is TTL configured?
- Are timers cleaning up custom state?

Joins:

- Is enrichment data small enough for broadcast state?
- Should enrichment use async lookup?
- Is the join event-time correct?
- How long must unmatched events be buffered?

Exactly-once:

- Is the source replayable?
- Are checkpoints enabled?
- Is the sink transactional, checkpoint-aware, or idempotent?
- What happens if the job fails after writing to the sink but before checkpoint
  completion?

Pinot:

- Is the Pinot table append-only, dedup, or upsert?
- What is the primary key?
- What is the comparison column?
- Is the input partitioned correctly?
- Are late window updates represented as upserts?

## 50. Common Mistakes

Mistake:

```text
Using processing time when the business needs event-time correctness.
```

Result:

```text
Delayed events land in the wrong window.
```

Mistake:

```text
Dedupe after aggregation.
```

Result:

```text
Duplicate events inflate counts and sums.
```

Mistake:

```text
No TTL on dedupe state.
```

Result:

```text
State grows forever.
```

Mistake:

```text
Append-only Pinot table for mutable window aggregates.
```

Result:

```text
Late updates create multiple rows for the same logical aggregate.
```

Mistake:

```text
Assuming Flink exactly-once means exactly-once sink writes.
```

Result:

```text
Duplicates can appear in external systems after recovery.
```

Mistake:

```text
Wrong partitioning for Pinot upsert or dedup.
```

Result:

```text
Pinot cannot consistently dedupe or upsert records.
```

## 51. Short Mental Model

Flink handles correctness before the sink:

```text
Watermarks decide event-time progress.
Dedupe state removes duplicate events.
Windows compute time-based aggregates.
Joins enrich with state, streams, or lookup systems.
Checkpoints make Flink state fault tolerant.
```

Pinot handles serving after the sink:

```text
Pinot stores raw, enriched, or aggregated rows.
Pinot serves low-latency OLAP queries.
Pinot can dedup or upsert if configured with primary keys.
Pinot does not understand Flink watermarks directly.
```

The most important design rule:

```text
Flink correctness happens in the stream processor.
Pinot correctness depends on primary keys, partitioning, upsert or dedup config,
and idempotent sink design.
```

## References

- Apache Flink event time and watermarks:
  https://github.com/apache/flink/blob/master/docs/content/docs/dev/datastream/event-time/generating_watermarks.md
- Apache Flink windows:
  https://github.com/apache/flink/blob/master/docs/content/docs/dev/datastream/operators/windows.md
- Apache Flink checkpointing:
  https://github.com/apache/flink/blob/master/docs/content/docs/dev/datastream/fault-tolerance/checkpointing.md
- Apache Flink state and dedupe example:
  https://github.com/apache/flink/blob/master/docs/content/docs/learn-flink/etl.md
- Apache Flink connector delivery guarantees:
  https://github.com/apache/flink/blob/master/docs/content/docs/connectors/datastream/guarantees.md
- Apache Pinot Flink connector:
  https://docs.pinot.apache.org/build-with-pinot/ingestion/batch-ingestion/flink
- Apache Pinot upsert:
  https://docs.pinot.apache.org/build-with-pinot/ingestion/upsert-dedup/upsert
- Apache Pinot dedup:
  https://docs.pinot.apache.org/build-with-pinot/ingestion/upsert-dedup/dedup
