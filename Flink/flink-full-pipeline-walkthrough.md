# Flink Full Pipeline Walkthrough: End-to-End Event Processing

## The Pipeline Architecture

```
┌─────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   Kafka     │───▶│ Event-Time Assignment │───▶│  Deduplication      │
│  (Source)   │    │   + Watermark Gen     │    │  (Keyed State)      │
└─────────────┘    └──────────────────────┘    └─────────────────────┘
                                                          │
                   ┌──────────────────────┐               ▼
                   │    Apache Pinot      │    ┌─────────────────────┐
                   │      (Sink)          │◀───│  Window Aggregation  │
                   └──────────────────────┘    └─────────────────────┘
                              ▲                           │
                              │                           ▼
                   ┌──────────────────────┐    ┌─────────────────────┐
                   │   Result Assembly    │◀───│  Join / Enrichment   │
                   └──────────────────────┘    └─────────────────────┘
```

---

## Unified Scenario: E-Commerce Order Analytics

We're building a real-time analytics pipeline for an e-commerce platform that:
- Ingests order events from Kafka
- Deduplicates retried/duplicate events
- Computes revenue per product category in 5-minute windows
- Enriches results with product metadata
- Sinks aggregated metrics to Apache Pinot for dashboarding

### Event Schema

```java
public class OrderEvent {
    String orderId;          // "ORD-12345"
    String userId;           // "USR-9876"
    String productId;        // "PROD-555"
    String category;         // "electronics"
    double amount;           // 149.99
    long eventTimestamp;     // 1716900000000 (epoch ms)
    String eventType;        // "ORDER_PLACED"
}
```

---

## Stage 1: Event Arrives (Kafka Source)

### What Happens

The pipeline starts by consuming events from a Kafka topic. Flink's Kafka connector
provides exactly-once semantics through checkpointing and offset management.

### Why This Matters

- **Offset tracking**: Flink manages Kafka consumer offsets through its checkpoint mechanism,
  not Kafka's consumer group protocol. This ensures exactly-once processing on recovery.
- **Parallelism**: Each Kafka partition maps to a Flink subtask. If you have 8 partitions
  and parallelism=4, each subtask reads from 2 partitions.
- **Backpressure**: If downstream stages slow down, Flink pauses reading from Kafka
  (TCP-level backpressure), preventing OOM.

### Code

```java
// Environment setup
StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
env.setParallelism(8);
env.enableCheckpointing(60_000); // checkpoint every 60s
env.getCheckpointConfig().setCheckpointingMode(CheckpointingMode.EXACTLY_ONCE);

// Kafka source
KafkaSource<OrderEvent> kafkaSource = KafkaSource.<OrderEvent>builder()
    .setBootstrapServers("kafka-broker-1:9092,kafka-broker-2:9092")
    .setTopics("order-events")
    .setGroupId("flink-order-analytics")
    .setStartingOffsets(OffsetsInitializer.committedOffsets(OffsetResetStrategy.EARLIEST))
    .setDeserializer(new OrderEventDeserializationSchema())
    .build();

DataStream<OrderEvent> rawEvents = env.fromSource(
    kafkaSource,
    WatermarkStrategy.noWatermarks(), // watermarks assigned in next stage
    "Kafka Order Events"
);
```

### Custom Deserializer

```java
public class OrderEventDeserializationSchema implements KafkaRecordDeserializationSchema<OrderEvent> {
    
    private transient ObjectMapper mapper;
    
    @Override
    public void open(DeserializationSchema.InitializationContext context) {
        mapper = new ObjectMapper();
    }
    
    @Override
    public void deserialize(ConsumerRecord<byte[], byte[]> record, 
                           Collector<OrderEvent> out) throws IOException {
        OrderEvent event = mapper.readValue(record.value(), OrderEvent.class);
        out.collect(event);
    }
    
    @Override
    public TypeInformation<OrderEvent> getProducedType() {
        return TypeInformation.of(OrderEvent.class);
    }
}
```

### What the Data Looks Like at This Point

```
Raw Kafka record:
  Key: "ORD-12345"
  Value: {"orderId":"ORD-12345","userId":"USR-9876","productId":"PROD-555",
          "category":"electronics","amount":149.99,"eventTimestamp":1716900000000,
          "eventType":"ORDER_PLACED"}
  Kafka timestamp: 1716900002000 (ingestion time, 2s after event time)
  Partition: 3, Offset: 847291
```

---

## Stage 2: Event-Time Assignment + Watermark Generation

### What Happens

Each event gets assigned an **event timestamp** (from the payload, not Kafka ingestion time),
and the system generates **watermarks** — monotonically increasing markers that signal
"no more events with timestamp ≤ W will arrive."

### Why This Matters

- **Event time vs Processing time**: An order placed at 10:00:00 might arrive at 10:00:05
  due to network delays. Using event time ensures correct window assignment regardless
  of when the event physically arrives.
- **Out-of-order handling**: Events can arrive out of order. Watermarks with bounded
  out-of-orderness tolerate late events up to a specified threshold.
- **Window triggering**: Windows fire when the watermark passes the window's end time,
  not when wall-clock time reaches it.

### How Watermarks Propagate

```
Subtask 1 (Partition 0,1):  Watermark = 10:04:55
Subtask 2 (Partition 2,3):  Watermark = 10:04:50  ← slowest
Subtask 3 (Partition 4,5):  Watermark = 10:04:58
Subtask 4 (Partition 6,7):  Watermark = 10:04:52

Downstream operator receives: min(10:04:55, 10:04:50, 10:04:58, 10:04:52) = 10:04:50
```

The downstream watermark is always the **minimum** across all upstream subtasks.
This is why one slow partition can hold back the entire pipeline.

### Code

```java
WatermarkStrategy<OrderEvent> watermarkStrategy = WatermarkStrategy
    .<OrderEvent>forBoundedOutOfOrderness(Duration.ofSeconds(10))
    .withTimestampAssigner((event, recordTimestamp) -> event.getEventTimestamp())
    .withIdleness(Duration.ofMinutes(2)); // handle idle partitions

DataStream<OrderEvent> timestampedEvents = rawEvents
    .assignTimestampsAndWatermarks(watermarkStrategy)
    .name("Assign Event-Time & Watermarks");
```

### Understanding `forBoundedOutOfOrderness(10 seconds)`

```
Timeline of arriving events:

  Event A: event_time = 10:00:03  → arrives at processing_time 10:00:05
  Event B: event_time = 10:00:01  → arrives at processing_time 10:00:06 (late!)
  Event C: event_time = 10:00:08  → arrives at processing_time 10:00:08
  Event D: event_time = 10:00:05  → arrives at processing_time 10:00:09

After Event C arrives, watermark = 10:00:08 - 10s = 09:59:58
After Event D arrives, watermark = max(10:00:08, 10:00:05) - 10s = 09:59:58 (unchanged)

So watermark = max_event_time_seen - out_of_orderness
```

### Idle Source Handling

```java
// Problem: If partition 3 has no events for 5 minutes, its watermark stays at
// the last event's time, blocking all downstream watermark advancement.

// Solution: withIdleness marks the source as idle after 2 minutes of inactivity,
// excluding it from watermark computation.

.withIdleness(Duration.ofMinutes(2))
```

### What the Data Looks Like at This Point

```
OrderEvent:
  orderId: "ORD-12345"
  eventTimestamp: 1716900000000 (May 28, 2024 10:00:00.000 UTC)
  
Internal Flink metadata:
  assignedTimestamp: 1716900000000  ← extracted from event
  currentWatermark: 1716899990000  ← (10:00:00 - 10s = 09:59:50)
```

---

## Stage 3: Deduplication Using Keyed State

### What Happens

Events can be duplicated due to Kafka producer retries, at-least-once upstream systems,
or application-level retries. We use **keyed state** to track seen event IDs and drop duplicates.

### Why This Matters

- **Exactly-once semantics**: Even if Kafka delivers the same message twice (producer retry
  with acks=1), we only process it once.
- **State management**: Flink's keyed state is partitioned by key and checkpointed.
  On failure recovery, state is restored and dedup resumes correctly.
- **TTL for state cleanup**: Without TTL, state grows unbounded. We expire entries after
  a window where duplicates are no longer expected (e.g., 10 minutes).

### How Keyed State Works Internally

```
Key Group Assignment (parallelism=4):

  "ORD-12345".hashCode() % 128 = keyGroup 47 → Subtask 1 (keyGroups 0-31)... wait
  Actually: maxParallelism=128, keyGroup = hash(key) % 128
  Subtask 0: keyGroups 0-31
  Subtask 1: keyGroups 32-63  ← keyGroup 47 goes here
  Subtask 2: keyGroups 64-95
  Subtask 3: keyGroups 96-127
  
State is stored in RocksDB (on disk) per subtask:
  Subtask 1 RocksDB:
    key="ORD-12345" → value=true (seen)
    key="ORD-12300" → value=true
    key="ORD-12299" → value=true (will be cleaned by TTL)
```

### Code

```java
DataStream<OrderEvent> deduplicatedEvents = timestampedEvents
    .keyBy(OrderEvent::getOrderId)
    .process(new DeduplicationFunction())
    .name("Deduplicate Orders");
```

### Deduplication Function

```java
public class DeduplicationFunction extends KeyedProcessFunction<String, OrderEvent, OrderEvent> {
    
    // State: tracks whether we've seen this orderId before
    private ValueState<Boolean> seenState;
    
    @Override
    public void open(Configuration parameters) {
        ValueStateDescriptor<Boolean> descriptor = new ValueStateDescriptor<>(
            "order-seen",
            Types.BOOLEAN
        );
        
        // TTL: auto-expire state after 10 minutes (no duplicates expected after that)
        StateTtlConfig ttlConfig = StateTtlConfig.newBuilder(Time.minutes(10))
            .setUpdateType(StateTtlConfig.UpdateType.OnCreateAndWrite)
            .setStateVisibility(StateTtlConfig.StateVisibility.NeverReturnExpired)
            .cleanupFullSnapshot()    // clean during checkpoints
            .cleanupInRocksdbCompactFilter(1000) // clean during RocksDB compaction
            .build();
        
        descriptor.enableTimeToLive(ttlConfig);
        seenState = getRuntimeContext().getState(descriptor);
    }
    
    @Override
    public void processElement(OrderEvent event, Context ctx, Collector<OrderEvent> out) 
            throws Exception {
        
        Boolean seen = seenState.value();
        
        if (seen == null || !seen) {
            // First time seeing this order — emit downstream
            seenState.update(true);
            out.collect(event);
        }
        // else: duplicate — silently drop
    }
}
```

### Deduplication in Action

```
Incoming events (time-ordered by arrival):

  t=10:00:01  OrderEvent{orderId="ORD-12345", amount=149.99}  → EMIT ✓
  t=10:00:02  OrderEvent{orderId="ORD-12346", amount=29.99}   → EMIT ✓
  t=10:00:03  OrderEvent{orderId="ORD-12345", amount=149.99}  → DROP (duplicate!)
  t=10:00:04  OrderEvent{orderId="ORD-12347", amount=89.50}   → EMIT ✓
  t=10:00:05  OrderEvent{orderId="ORD-12345", amount=149.99}  → DROP (Kafka retry)
  
  t=10:12:00  (TTL expires for ORD-12345, state cleaned up)
  t=10:15:00  OrderEvent{orderId="ORD-12345", amount=149.99}  → EMIT ✓ (new order cycle)
```

### Alternative: Deduplication with Event-Time Timer

```java
// More sophisticated: use event-time timer to clean state precisely
@Override
public void processElement(OrderEvent event, Context ctx, Collector<OrderEvent> out) 
        throws Exception {
    
    Boolean seen = seenState.value();
    
    if (seen == null || !seen) {
        seenState.update(true);
        out.collect(event);
        
        // Register cleanup timer for 10 minutes after event time
        ctx.timerService().registerEventTimeTimer(
            event.getEventTimestamp() + Duration.ofMinutes(10).toMillis()
        );
    }
}

@Override
public void onTimer(long timestamp, OnTimerContext ctx, Collector<OrderEvent> out) {
    // Timer fired → clean up state
    seenState.clear();
}
```

---

## Stage 4: Window Aggregation

### What Happens

Deduplicated events are grouped into **time windows** and aggregated. We use a 5-minute
tumbling window to compute revenue per product category.

### Why This Matters

- **Bounded computation**: Without windows, aggregation would accumulate forever.
  Windows bound the computation to a time range.
- **Event-time semantics**: Windows are defined over event time, not wall-clock time.
  A 10:00–10:05 window contains events with event_time in [10:00, 10:05).
- **Incremental aggregation**: Using `AggregateFunction`, Flink maintains a running
  accumulator rather than buffering all events. Memory usage is O(1) per window per key.

### Window Lifecycle

```
Timeline for window [10:00:00, 10:05:00):

  10:00:01  Event(category="electronics", amount=149.99) → accumulator: {count:1, sum:149.99}
  10:00:45  Event(category="electronics", amount=299.00) → accumulator: {count:2, sum:448.99}
  10:02:30  Event(category="electronics", amount=59.99)  → accumulator: {count:3, sum:508.98}
  10:04:55  Event(category="electronics", amount=199.00) → accumulator: {count:4, sum:707.98}
  
  --- Watermark reaches 10:05:00 ---
  
  WINDOW FIRES! → emits CategoryRevenue{category="electronics", windowStart=10:00:00,
                                          windowEnd=10:05:00, totalRevenue=707.98,
                                          orderCount=4, avgOrderValue=176.995}
  
  10:05:03  Event(category="electronics", amount=79.99, event_time=10:04:58)
            → LATE! (arrived after watermark passed window end)
            → Handled by allowedLateness or dropped
```

### Code

```java
DataStream<CategoryRevenue> windowedRevenue = deduplicatedEvents
    .keyBy(OrderEvent::getCategory)
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .allowedLateness(Time.minutes(1))
    .sideOutputLateData(lateEventsTag)
    .aggregate(
        new RevenueAggregator(),      // incremental aggregation
        new RevenueWindowFunction()   // adds window metadata
    )
    .name("5-min Revenue Aggregation");

// Capture late events for monitoring
OutputTag<OrderEvent> lateEventsTag = new OutputTag<>("late-orders") {};
DataStream<OrderEvent> lateEvents = windowedRevenue.getSideOutput(lateEventsTag);
```

### Revenue Aggregator (Incremental)

```java
public class RevenueAggregator 
        implements AggregateFunction<OrderEvent, RevenueAccumulator, RevenueResult> {
    
    @Override
    public RevenueAccumulator createAccumulator() {
        return new RevenueAccumulator(0, 0.0, Double.MAX_VALUE, 0.0);
    }
    
    @Override
    public RevenueAccumulator add(OrderEvent event, RevenueAccumulator acc) {
        return new RevenueAccumulator(
            acc.count + 1,
            acc.totalRevenue + event.getAmount(),
            Math.min(acc.minOrder, event.getAmount()),
            Math.max(acc.maxOrder, event.getAmount())
        );
    }
    
    @Override
    public RevenueResult getResult(RevenueAccumulator acc) {
        return new RevenueResult(
            acc.count,
            acc.totalRevenue,
            acc.totalRevenue / acc.count, // average
            acc.minOrder,
            acc.maxOrder
        );
    }
    
    @Override
    public RevenueAccumulator merge(RevenueAccumulator a, RevenueAccumulator b) {
        // Used in session windows when two windows merge
        return new RevenueAccumulator(
            a.count + b.count,
            a.totalRevenue + b.totalRevenue,
            Math.min(a.minOrder, b.minOrder),
            Math.max(a.maxOrder, b.maxOrder)
        );
    }
}
```

### Window Function (Adds Metadata)

```java
public class RevenueWindowFunction 
        extends ProcessWindowFunction<RevenueResult, CategoryRevenue, String, TimeWindow> {
    
    @Override
    public void process(String category, Context context, 
                       Iterable<RevenueResult> results, 
                       Collector<CategoryRevenue> out) {
        
        RevenueResult result = results.iterator().next(); // single result from aggregate
        TimeWindow window = context.window();
        
        out.collect(new CategoryRevenue(
            category,
            window.getStart(),
            window.getEnd(),
            result.totalRevenue,
            result.orderCount,
            result.avgOrderValue,
            result.minOrder,
            result.maxOrder,
            System.currentTimeMillis() // processing timestamp for latency tracking
        ));
    }
}
```

### Accumulator and Result Classes

```java
public class RevenueAccumulator {
    int count;
    double totalRevenue;
    double minOrder;
    double maxOrder;
    // constructor, getters...
}

public class RevenueResult {
    int orderCount;
    double totalRevenue;
    double avgOrderValue;
    double minOrder;
    double maxOrder;
    // constructor, getters...
}

public class CategoryRevenue {
    String category;           // "electronics"
    long windowStart;          // 1716900000000
    long windowEnd;            // 1716900300000
    double totalRevenue;       // 707.98
    int orderCount;            // 4
    double avgOrderValue;      // 176.995
    double minOrder;           // 59.99
    double maxOrder;           // 299.00
    long processingTimestamp;  // for latency measurement
}
```

### Late Event Handling

```java
// Late events go to side output — send to dead-letter queue or separate analytics
lateEvents
    .map(event -> new LateEventAlert(
        event.getOrderId(),
        event.getEventTimestamp(),
        System.currentTimeMillis(),
        System.currentTimeMillis() - event.getEventTimestamp() // delay
    ))
    .addSink(new KafkaSink<>("late-events-dlq"))
    .name("Late Events → DLQ");
```

---

## Stage 5: Join / Enrichment

### What Happens

Window aggregation results are enriched with additional context — in this case, product
category metadata (display name, department, margin tier) from a slowly-changing reference
stream.

### Why This Matters

- **Real-time enrichment**: Rather than storing category metadata in each event (denormalization),
  we join with a reference stream at processing time. This keeps events small and
  metadata always current.
- **Join types in Flink**:
  - **Interval Join**: Join two keyed streams within a time range
  - **Temporal Table Join**: Join with a versioned lookup table
  - **Broadcast State Join**: Small reference data broadcast to all subtasks
  - **Async I/O**: Non-blocking lookups to external databases

### Approach: Broadcast State Pattern

For slowly-changing reference data (product categories), broadcast state is ideal:
the category metadata stream is small and changes infrequently.

```
                    ┌─────────────────────────────────────┐
                    │       Category Metadata Stream       │
                    │  (Kafka: "category-metadata")        │
                    │  ~100 categories, updates rarely     │
                    └─────────────────┬───────────────────┘
                                      │ broadcast
                                      ▼
┌──────────────────┐    ┌─────────────────────────────────┐
│ CategoryRevenue  │───▶│     BroadcastProcessFunction     │───▶ EnrichedRevenue
│  (keyed stream)  │    │  Joins revenue with metadata     │
└──────────────────┘    └─────────────────────────────────┘
```

### Code

```java
// Reference data: category metadata from Kafka (compacted topic)
DataStream<CategoryMetadata> categoryMetadataStream = env.fromSource(
    KafkaSource.<CategoryMetadata>builder()
        .setBootstrapServers("kafka-broker-1:9092")
        .setTopics("category-metadata")
        .setStartingOffsets(OffsetsInitializer.earliest()) // read full compacted topic
        .setDeserializer(new CategoryMetadataDeserializer())
        .build(),
    WatermarkStrategy.noWatermarks(),
    "Category Metadata"
);

// Define broadcast state descriptor
MapStateDescriptor<String, CategoryMetadata> categoryStateDesc = new MapStateDescriptor<>(
    "category-metadata",
    Types.STRING,
    Types.POJO(CategoryMetadata.class)
);

// Broadcast the metadata stream
BroadcastStream<CategoryMetadata> broadcastMetadata = 
    categoryMetadataStream.broadcast(categoryStateDesc);

// Join: revenue stream + broadcast metadata
DataStream<EnrichedCategoryRevenue> enrichedRevenue = windowedRevenue
    .connect(broadcastMetadata)
    .process(new CategoryEnrichmentFunction(categoryStateDesc))
    .name("Enrich with Category Metadata");
```

### Enrichment Function

```java
public class CategoryEnrichmentFunction 
        extends BroadcastProcessFunction<CategoryRevenue, CategoryMetadata, EnrichedCategoryRevenue> {
    
    private final MapStateDescriptor<String, CategoryMetadata> stateDesc;
    
    public CategoryEnrichmentFunction(MapStateDescriptor<String, CategoryMetadata> stateDesc) {
        this.stateDesc = stateDesc;
    }
    
    @Override
    public void processElement(CategoryRevenue revenue, ReadOnlyContext ctx, 
                              Collector<EnrichedCategoryRevenue> out) throws Exception {
        
        // Look up metadata from broadcast state
        ReadOnlyBroadcastState<String, CategoryMetadata> state = 
            ctx.getBroadcastState(stateDesc);
        
        CategoryMetadata metadata = state.get(revenue.getCategory());
        
        if (metadata != null) {
            out.collect(new EnrichedCategoryRevenue(
                revenue.getCategory(),
                metadata.getDisplayName(),      // "Consumer Electronics"
                metadata.getDepartment(),       // "Technology"
                metadata.getMarginTier(),       // "HIGH"
                revenue.getWindowStart(),
                revenue.getWindowEnd(),
                revenue.getTotalRevenue(),
                revenue.getOrderCount(),
                revenue.getAvgOrderValue(),
                revenue.getTotalRevenue() * metadata.getMarginPercent() // estimated profit
            ));
        } else {
            // Metadata not yet received — emit with defaults
            out.collect(new EnrichedCategoryRevenue(
                revenue.getCategory(),
                revenue.getCategory(), // use category key as display name
                "UNKNOWN",
                "UNKNOWN",
                revenue.getWindowStart(),
                revenue.getWindowEnd(),
                revenue.getTotalRevenue(),
                revenue.getOrderCount(),
                revenue.getAvgOrderValue(),
                0.0
            ));
        }
    }
    
    @Override
    public void processBroadcastElement(CategoryMetadata metadata, Context ctx, 
                                       Collector<EnrichedCategoryRevenue> out) throws Exception {
        // Update broadcast state when new metadata arrives
        BroadcastState<String, CategoryMetadata> state = ctx.getBroadcastState(stateDesc);
        state.put(metadata.getCategoryKey(), metadata);
    }
}
```

### Category Metadata Schema

```java
public class CategoryMetadata {
    String categoryKey;      // "electronics"
    String displayName;      // "Consumer Electronics"
    String department;       // "Technology"
    String marginTier;       // "HIGH", "MEDIUM", "LOW"
    double marginPercent;    // 0.22 (22% margin)
    long updatedAt;          // last update timestamp
}
```

### Alternative: Async I/O for External Lookup

When metadata lives in an external database (Redis, DynamoDB) rather than a Kafka stream:

```java
DataStream<EnrichedCategoryRevenue> enrichedRevenue = AsyncDataStream
    .unorderedWait(
        windowedRevenue,
        new AsyncCategoryLookup(),  // async function
        5000,                       // timeout ms
        TimeUnit.MILLISECONDS,
        100                         // max concurrent requests
    )
    .name("Async Category Enrichment");

public class AsyncCategoryLookup 
        extends RichAsyncFunction<CategoryRevenue, EnrichedCategoryRevenue> {
    
    private transient RedisAsyncClient redisClient;
    
    @Override
    public void open(Configuration parameters) {
        redisClient = RedisClient.create("redis://redis-host:6379")
            .connect().async();
    }
    
    @Override
    public void asyncInvoke(CategoryRevenue revenue, 
                           ResultFuture<EnrichedCategoryRevenue> resultFuture) {
        
        CompletableFuture<String> future = redisClient
            .hgetall("category:" + revenue.getCategory())
            .toCompletableFuture();
        
        future.thenAccept(metadata -> {
            resultFuture.complete(Collections.singleton(
                buildEnrichedRevenue(revenue, parseMetadata(metadata))
            ));
        });
    }
}
```

### Alternative: Interval Join (Two Event Streams)

When enriching with another event stream (e.g., joining orders with shipment events):

```java
// Join orders with shipments that occurred within [-5min, +30min] of the order
DataStream<OrderWithShipment> joined = orders
    .keyBy(OrderEvent::getOrderId)
    .intervalJoin(shipments.keyBy(ShipmentEvent::getOrderId))
    .between(Time.minutes(-5), Time.minutes(30))
    .process(new OrderShipmentJoinFunction());
```

---

## Stage 6: Sink to Apache Pinot

### What Happens

Enriched aggregation results are written to Apache Pinot — a real-time OLAP database
designed for low-latency analytical queries on streaming data.

### Why Apache Pinot

- **Sub-second queries** on aggregated data for dashboards
- **Real-time ingestion** from streaming sources (Kafka, Flink)
- **Columnar storage** optimized for analytical queries (sum, avg, group by)
- **Star-tree indexes** for pre-aggregated multidimensional queries
- **Used by**: LinkedIn, Uber, Stripe, Walmart for real-time analytics

### Pinot Table Schema

```json
{
  "tableName": "category_revenue_REALTIME",
  "tableType": "REALTIME",
  "segmentsConfig": {
    "timeColumnName": "windowStart",
    "timeType": "MILLISECONDS",
    "retentionTimeUnit": "DAYS",
    "retentionTimeValue": "30"
  },
  "tableIndexConfig": {
    "starTreeIndexConfigs": [{
      "dimensionsSplitOrder": ["department", "category", "marginTier"],
      "functionColumnPairs": ["SUM__totalRevenue", "SUM__orderCount", "AVG__avgOrderValue"]
    }]
  },
  "ingestionConfig": {
    "streamIngestionConfig": {
      "streamConfigMaps": [{
        "stream.kafka.topic.name": "enriched-category-revenue",
        "stream.kafka.broker.list": "kafka-broker-1:9092",
        "stream.kafka.consumer.type": "lowLevel"
      }]
    }
  }
}
```

### Approach: Flink → Kafka → Pinot

The most common pattern is Flink writing to an intermediate Kafka topic that Pinot consumes:

```
Flink ──▶ Kafka topic "enriched-category-revenue" ──▶ Pinot REALTIME table
```

### Code: Kafka Sink (Intermediate)

```java
KafkaSink<EnrichedCategoryRevenue> pinotSink = KafkaSink.<EnrichedCategoryRevenue>builder()
    .setBootstrapServers("kafka-broker-1:9092")
    .setRecordSerializer(
        KafkaRecordSerializationSchema.builder()
            .setTopic("enriched-category-revenue")
            .setKeySerializationSchema(new CategoryKeySerializer())
            .setValueSerializationSchema(new EnrichedRevenueJsonSerializer())
            .build()
    )
    .setDeliveryGuarantee(DeliveryGuarantee.EXACTLY_ONCE)
    .setTransactionalIdPrefix("flink-revenue-")
    .setProperty(ProducerConfig.TRANSACTION_TIMEOUT_CONFIG, "600000") // 10 min
    .build();

enrichedRevenue.sinkTo(pinotSink).name("Sink to Kafka → Pinot");
```

### Serializer

```java
public class EnrichedRevenueJsonSerializer 
        implements SerializationSchema<EnrichedCategoryRevenue> {
    
    private transient ObjectMapper mapper;
    
    @Override
    public void open(InitializationContext context) {
        mapper = new ObjectMapper();
    }
    
    @Override
    public byte[] serialize(EnrichedCategoryRevenue revenue) {
        try {
            // Format for Pinot ingestion
            Map<String, Object> record = new LinkedHashMap<>();
            record.put("category", revenue.getCategory());
            record.put("displayName", revenue.getDisplayName());
            record.put("department", revenue.getDepartment());
            record.put("marginTier", revenue.getMarginTier());
            record.put("windowStart", revenue.getWindowStart());
            record.put("windowEnd", revenue.getWindowEnd());
            record.put("totalRevenue", revenue.getTotalRevenue());
            record.put("orderCount", revenue.getOrderCount());
            record.put("avgOrderValue", revenue.getAvgOrderValue());
            record.put("estimatedProfit", revenue.getEstimatedProfit());
            record.put("processingTimestamp", System.currentTimeMillis());
            
            return mapper.writeValueAsBytes(record);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Serialization failed", e);
        }
    }
}
```

### Alternative: Direct JDBC Sink (for Pinot or other OLAP)

```java
// If using Pinot's JDBC interface or another OLAP with JDBC support
JdbcSink.sink(
    "INSERT INTO category_revenue (category, department, window_start, total_revenue, order_count) " +
    "VALUES (?, ?, ?, ?, ?)",
    (statement, revenue) -> {
        statement.setString(1, revenue.getCategory());
        statement.setString(2, revenue.getDepartment());
        statement.setTimestamp(3, new Timestamp(revenue.getWindowStart()));
        statement.setDouble(4, revenue.getTotalRevenue());
        statement.setInt(5, revenue.getOrderCount());
    },
    JdbcExecutionOptions.builder()
        .withBatchSize(500)
        .withBatchIntervalMs(1000)
        .withMaxRetries(3)
        .build(),
    new JdbcConnectionOptions.JdbcConnectionOptionsBuilder()
        .withUrl("jdbc:pinot://pinot-broker:8099")
        .withDriverName("org.apache.pinot.client.PinotDriver")
        .build()
);
```

### What Pinot Sees

```json
{
  "category": "electronics",
  "displayName": "Consumer Electronics",
  "department": "Technology",
  "marginTier": "HIGH",
  "windowStart": 1716900000000,
  "windowEnd": 1716900300000,
  "totalRevenue": 707.98,
  "orderCount": 4,
  "avgOrderValue": 176.995,
  "estimatedProfit": 155.76,
  "processingTimestamp": 1716900305000
}
```

### Querying Pinot (Dashboard Queries)

```sql
-- Real-time revenue by department (last hour)
SELECT department, SUM(totalRevenue) as revenue, SUM(orderCount) as orders
FROM category_revenue
WHERE windowStart > ago('PT1H')
GROUP BY department
ORDER BY revenue DESC

-- Revenue trend for electronics (last 24 hours, 5-min granularity)
SELECT windowStart, totalRevenue, orderCount, avgOrderValue
FROM category_revenue
WHERE category = 'electronics'
  AND windowStart > ago('PT24H')
ORDER BY windowStart
```

---

## Complete Pipeline Assembly

### Full Job Code

```java
public class OrderAnalyticsPipeline {
    
    public static void main(String[] args) throws Exception {
        
        // ─── Environment Setup ───
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(8);
        env.enableCheckpointing(60_000);
        env.getCheckpointConfig().setCheckpointingMode(CheckpointingMode.EXACTLY_ONCE);
        env.getCheckpointConfig().setMinPauseBetweenCheckpoints(30_000);
        env.setStateBackend(new EmbeddedRocksDBStateBackend());
        env.getCheckpointConfig().setCheckpointStorage("s3://flink-checkpoints/order-analytics/");
        
        // ─── Stage 1: Source ───
        KafkaSource<OrderEvent> kafkaSource = KafkaSource.<OrderEvent>builder()
            .setBootstrapServers("kafka-broker-1:9092,kafka-broker-2:9092")
            .setTopics("order-events")
            .setGroupId("flink-order-analytics")
            .setStartingOffsets(OffsetsInitializer.committedOffsets(OffsetResetStrategy.EARLIEST))
            .setDeserializer(new OrderEventDeserializationSchema())
            .build();
        
        // ─── Stage 2: Event-Time + Watermarks ───
        DataStream<OrderEvent> events = env.fromSource(
                kafkaSource,
                WatermarkStrategy.<OrderEvent>forBoundedOutOfOrderness(Duration.ofSeconds(10))
                    .withTimestampAssigner((event, ts) -> event.getEventTimestamp())
                    .withIdleness(Duration.ofMinutes(2)),
                "Order Events Source"
            );
        
        // ─── Stage 3: Deduplication ───
        DataStream<OrderEvent> deduplicated = events
            .keyBy(OrderEvent::getOrderId)
            .process(new DeduplicationFunction())
            .name("Deduplicate");
        
        // ─── Stage 4: Window Aggregation ───
        OutputTag<OrderEvent> lateEventsTag = new OutputTag<>("late-orders") {};
        
        SingleOutputStreamOperator<CategoryRevenue> windowed = deduplicated
            .keyBy(OrderEvent::getCategory)
            .window(TumblingEventTimeWindows.of(Time.minutes(5)))
            .allowedLateness(Time.minutes(1))
            .sideOutputLateData(lateEventsTag)
            .aggregate(new RevenueAggregator(), new RevenueWindowFunction())
            .name("5-min Revenue Windows");
        
        // ─── Stage 5: Enrichment ───
        DataStream<CategoryMetadata> metadataStream = env.fromSource(
            buildMetadataSource(), WatermarkStrategy.noWatermarks(), "Category Metadata"
        );
        
        MapStateDescriptor<String, CategoryMetadata> metadataStateDesc = 
            new MapStateDescriptor<>("category-metadata", Types.STRING, 
                                    Types.POJO(CategoryMetadata.class));
        
        BroadcastStream<CategoryMetadata> broadcastMetadata = 
            metadataStream.broadcast(metadataStateDesc);
        
        DataStream<EnrichedCategoryRevenue> enriched = windowed
            .connect(broadcastMetadata)
            .process(new CategoryEnrichmentFunction(metadataStateDesc))
            .name("Enrich Categories");
        
        // ─── Stage 6: Sink ───
        enriched.sinkTo(buildPinotKafkaSink()).name("Sink → Pinot");
        
        // ─── Late events monitoring ───
        windowed.getSideOutput(lateEventsTag)
            .sinkTo(buildLateDLQSink())
            .name("Late Events → DLQ");
        
        // ─── Execute ───
        env.execute("Order Revenue Analytics Pipeline");
    }
}
```

---

## End-to-End Event Trace

Let's trace a single event through the entire pipeline:

```
╔══════════════════════════════════════════════════════════════════════════╗
║  EVENT: OrderEvent{orderId="ORD-12345", category="electronics",        ║
║         amount=149.99, eventTimestamp=1716900060000}                    ║
║         (May 28, 2024 10:01:00 UTC)                                    ║
╚══════════════════════════════════════════════════════════════════════════╝

Stage 1 — Kafka Source
  ├─ Consumed from partition 3, offset 847291
  ├─ Deserialized from JSON bytes to OrderEvent POJO
  └─ Passed to next operator

Stage 2 — Event-Time + Watermark
  ├─ Timestamp assigned: 1716900060000 (from event.eventTimestamp)
  ├─ Max timestamp seen so far: 1716900065000 (another event was newer)
  ├─ Current watermark: 1716900065000 - 10000 = 1716900055000 (10:00:55)
  └─ This event's time (10:01:00) > watermark (10:00:55) → ON TIME ✓

Stage 3 — Deduplication
  ├─ Key: "ORD-12345"
  ├─ Lookup state: seenState.value() → null (first occurrence)
  ├─ Update state: seenState.update(true)
  └─ Emit downstream ✓

Stage 4 — Window Aggregation
  ├─ Key: "electronics"
  ├─ Window assignment: [10:00:00, 10:05:00) (tumbling 5-min)
  ├─ Event time 10:01:00 falls in this window
  ├─ Accumulator updated: {count: 2, sum: 449.98, min: 149.99, max: 299.99}
  ├─ (window not yet fired — watermark hasn't reached 10:05:00)
  │
  │  ... more events arrive ...
  │
  ├─ Watermark reaches 10:05:00 → WINDOW FIRES
  └─ Emits: CategoryRevenue{category="electronics", revenue=707.98, count=4}

Stage 5 — Enrichment
  ├─ Broadcast state lookup: "electronics" → CategoryMetadata{
  │     displayName="Consumer Electronics", department="Technology", margin=0.22}
  ├─ Enriched: department="Technology", marginTier="HIGH"
  └─ Estimated profit: 707.98 * 0.22 = 155.76

Stage 6 — Sink
  ├─ Serialized to JSON
  ├─ Written to Kafka topic "enriched-category-revenue"
  ├─ Kafka transaction committed on next checkpoint
  └─ Pinot consumes and indexes within ~2 seconds
      → Available for dashboard queries
```

---

## Failure Scenarios and Recovery

### Scenario 1: Task Manager Crashes Mid-Window

```
Before crash:
  Window [10:00, 10:05) accumulator: {count=3, sum=508.98}
  Last successful checkpoint: accumulator at {count=2, sum=448.99}
  Kafka offset at checkpoint: 847290

Recovery:
  1. Flink restores state from checkpoint → accumulator={count=2, sum=448.99}
  2. Kafka source rewinds to offset 847290
  3. Reprocesses events from 847290 onward
  4. Dedup state also restored → correctly drops already-seen events
  5. Window accumulator catches up to correct state
  6. No duplicate output (exactly-once sink via Kafka transactions)
```

### Scenario 2: Kafka Partition Goes Idle

```
Problem:
  Partition 5 stops producing events
  Its watermark stays at 10:02:30 while others advance to 10:08:00
  Downstream watermark = min(all upstream) = 10:02:30
  NO windows fire for 6 minutes!

Solution (already in our code):
  .withIdleness(Duration.ofMinutes(2))
  
  After 2 minutes of no events, partition 5 is marked idle.
  New downstream watermark = min(non-idle partitions) = 10:08:00
  Windows fire normally.
```

### Scenario 3: Burst of Late Events

```
Normal: 0.1% of events arrive after watermark (within allowedLateness)
Burst:  5% of events arrive late due to upstream retry storm

Handling:
  ├─ Events within allowedLateness(1 min): window re-fires with updated result
  ├─ Events beyond allowedLateness: routed to side output (lateEventsTag)
  ├─ Side output → Kafka DLQ → separate batch reconciliation job
  └─ Alert fires if late% > 2% (monitoring on DLQ topic lag)
```

---

## Performance Tuning

### Key Configuration

```java
// Checkpointing
env.enableCheckpointing(60_000);                           // every 60s
env.getCheckpointConfig().setMinPauseBetweenCheckpoints(30_000); // 30s pause
env.getCheckpointConfig().setCheckpointTimeout(120_000);   // 2 min timeout
env.getCheckpointConfig().setMaxConcurrentCheckpoints(1);

// RocksDB state backend (for large state)
env.setStateBackend(new EmbeddedRocksDBStateBackend(true)); // incremental checkpoints
env.getCheckpointConfig().setCheckpointStorage("s3://checkpoints/");

// Network buffers
env.getConfiguration().setInteger("taskmanager.network.memory.buffers-per-channel", 4);
env.getConfiguration().setString("taskmanager.memory.network.fraction", "0.15");

// Parallelism per operator
deduplicatedEvents.setParallelism(16);  // high throughput stage
windowed.setParallelism(8);             // fewer keys after grouping
enriched.setParallelism(8);
```

### Monitoring Metrics

| Metric | Healthy Range | Alert Threshold |
|--------|--------------|-----------------|
| `numRecordsInPerSecond` | 10K-100K/s | < 1K/s (source stalled) |
| `currentInputWatermark` | Within 30s of now | > 5 min behind (lag) |
| `checkpointDuration` | < 10s | > 60s (state too large) |
| `numLateRecordsDropped` | < 0.1% of total | > 2% (clock skew) |
| `busyTimeMsPerSecond` | < 700ms | > 900ms (backpressure) |
| `rocksdb.estimate-num-keys` | Stable | Growing unbounded (state leak) |

---

## Summary: Design Decisions

| Stage | Decision | Rationale |
|-------|----------|-----------|
| Source | Exactly-once checkpointing | Prevents duplicate downstream writes |
| Watermarks | 10s bounded out-of-orderness | Balances latency vs correctness for typical network delays |
| Dedup | TTL-based state cleanup | Prevents unbounded state growth while covering retry window |
| Windows | Tumbling 5-min with 1-min lateness | Fixed intervals for dashboards, tolerance for network jitter |
| Enrichment | Broadcast state (not async I/O) | Metadata is small + changes rarely; avoids external call latency |
| Sink | Kafka (exactly-once) → Pinot | Decouples Flink from Pinot; Pinot reads at its own pace |
