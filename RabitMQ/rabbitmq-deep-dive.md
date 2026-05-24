# RabbitMQ Deep Dive for System Design

## Table of Contents

1. [What RabbitMQ Is](#what-rabbitmq-is)
2. [Core Mental Model](#core-mental-model)
3. [RabbitMQ Building Blocks](#rabbitmq-building-blocks)
4. [Message Lifecycle](#message-lifecycle)
5. [Exchange Types and Routing Patterns](#exchange-types-and-routing-patterns)
6. [Queue Types](#queue-types)
7. [Delivery Guarantees](#delivery-guarantees)
8. [Consumer Design](#consumer-design)
9. [Failure Handling, Retries, and DLQs](#failure-handling-retries-and-dlqs)
10. [Use Cases](#use-cases)
11. [Scaling RabbitMQ for Millions of Records](#scaling-rabbitmq-for-millions-of-records)
12. [Reference Architecture for Millions of Records](#reference-architecture-for-millions-of-records)
13. [Capacity Planning](#capacity-planning)
14. [Operations and Observability](#operations-and-observability)
15. [RabbitMQ vs Kafka](#rabbitmq-vs-kafka)
16. [Design Rules and Interview Takeaways](#design-rules-and-interview-takeaways)
17. [Security, Governance, and Multi-Tenancy](#security-governance-and-multi-tenancy)
18. [Deployment, Upgrades, and Disaster Recovery](#deployment-upgrades-and-disaster-recovery)
19. [Real-World Production Case Study: Marketplace Order Platform](#real-world-production-case-study-marketplace-order-platform)
20. [Production Handling Playbook](#production-handling-playbook)
21. [References](#references)

---

## What RabbitMQ Is

RabbitMQ is a message broker. It sits between producers and consumers so
applications can communicate asynchronously.

Instead of one service calling another service directly:

```text
Order Service -> Payment Service
```

the producer publishes a message to RabbitMQ:

```text
Order Service -> RabbitMQ -> Payment Worker
```

This changes the system behavior:

- The producer does not need the consumer to be online at the same time.
- Work can be buffered during spikes.
- Consumers can scale independently from producers.
- Failed work can be retried or moved to a dead-letter queue.
- Different consumers can receive different copies of the same event.
- Routing can be changed without tightly coupling all services together.

RabbitMQ is commonly used for:

- Background jobs.
- Work queues.
- Async commands between microservices.
- Fanout notifications.
- Retry pipelines.
- Request/reply workflows.
- Routing messages by business type, tenant, priority, or region.
- Multi-protocol messaging through AMQP, MQTT, STOMP, and RabbitMQ Streams.

The most important difference from Kafka is this:

```text
RabbitMQ is primarily a broker and work distribution system.
Kafka is primarily a distributed append-only event log.
```

RabbitMQ can do stream-like workloads with RabbitMQ Streams and super streams,
but its classic strength is routing and task delivery. Kafka can support
queue-like workloads with consumer groups, but its classic strength is durable
event retention, replay, and high-throughput streaming.

---

## Core Mental Model

RabbitMQ has four main runtime concepts:

```text
Producer -> Exchange -> Queue -> Consumer
```

A producer never sends directly to a queue in the usual AMQP model. It sends to
an exchange. The exchange decides which queue or queues should receive the
message.

```text
                   routing key: order.created
Producer -----------------------------------------+
                                                   |
                                                   v
                                             +----------+
                                             | Exchange |
                                             +----------+
                                               |      |
                              binding rule     |      | binding rule
                              order.*          |      | payment.*
                                               v      v
                                           +------+ +------+
                                           | Q1   | | Q2   |
                                           +------+ +------+
                                              |       |
                                              v       v
                                         Consumer  Consumer
```

This split is what makes RabbitMQ powerful:

- Producers know only where to publish.
- Exchanges own routing.
- Queues own buffering and delivery.
- Consumers own processing.

### Broker vs Queue vs Stream

RabbitMQ supports multiple messaging styles:

| Style | RabbitMQ Feature | Best For |
|---|---|---|
| Work queue | Classic or quorum queue | Tasks that should be processed once by one worker |
| Publish/subscribe | Exchange bound to many queues | Notifications and fanout |
| Command routing | Direct or topic exchange | Routing commands by action, tenant, or service |
| Reliable replicated queue | Quorum queue | Durable tasks that survive node failure |
| Append-only stream | Stream queue / super stream | Replayable high-throughput event streams |

---

## RabbitMQ Building Blocks

### Producer

A producer creates and publishes messages.

Producer responsibilities:

- Set the exchange and routing key.
- Use persistent messages when durability is required.
- Use publisher confirms when it must know the broker accepted the message.
- Handle unroutable messages.
- Apply backpressure when RabbitMQ slows down.
- Include idempotency keys and correlation IDs.

### Exchange

An exchange receives messages from producers and routes them to queues.

Important properties:

- Name.
- Type: direct, topic, fanout, headers.
- Durability: whether the exchange survives broker restart.
- Bindings: routing rules from exchange to queues.

### Binding

A binding connects an exchange to a queue.

```text
Exchange: orders.topic
Queue: fraud-check.queue
Binding key: order.created
```

If the exchange receives a message with routing key `order.created`, it routes
that message to `fraud-check.queue`.

### Queue

A queue stores messages until consumers process them.

Queue responsibilities:

- Buffer messages.
- Track ready and unacknowledged messages.
- Deliver messages to consumers.
- Redeliver messages when consumers fail.
- Apply TTL, length limits, dead-lettering, and priority behavior if configured.
- Provide durability and replication depending on queue type.

### Consumer

A consumer receives messages from a queue and acknowledges them after processing.

Consumer responsibilities:

- Set prefetch to limit in-flight work.
- Acknowledge only after the side effect is complete.
- Reject or nack failed messages intentionally.
- Make processing idempotent.
- Export processing latency, error, and retry metrics.

### Connection and Channel

RabbitMQ clients usually open:

- One TCP connection per process or per worker group.
- Multiple channels inside a connection.

Channels are lightweight logical sessions over a connection. They are used for
publishing, consuming, declaring queues, and acknowledgements.

General rule:

- Do not open one connection per message.
- Do not share a channel unsafely across threads if the client library does not
  allow it.
- Use a small pool of long-lived connections and channels.

### Virtual Host

A virtual host is a logical namespace.

Use vhosts to isolate:

- Applications.
- Environments.
- Tenants with strong operational boundaries.
- Permissions.

---

## Message Lifecycle

A reliable RabbitMQ flow looks like this:

```text
1. Producer publishes message to exchange.
2. Exchange evaluates bindings.
3. Message is routed to one or more queues.
4. Broker persists/replicates the message if durability is configured.
5. Broker sends publisher confirm.
6. Consumer receives the message.
7. Message becomes unacknowledged.
8. Consumer performs the business operation.
9. Consumer sends ack.
10. Broker removes the message from the queue.
```

### Happy Path

```text
Producer
   |
   | publish + routing key
   v
Exchange
   |
   | binding matched
   v
Queue
   |
   | deliver
   v
Consumer
   |
   | process success
   v
Ack
   |
   v
Message removed
```

### Consumer Failure Path

```text
Consumer receives message
   |
   v
Consumer crashes before ack
   |
   v
Broker detects closed channel/connection
   |
   v
Message is requeued or redelivered
   |
   v
Another consumer gets the message
```

This is why consumers must be idempotent. A message can be delivered more than
once.

### Publish Failure Path

If the producer publishes without confirms, it may not know whether RabbitMQ
accepted the message. A network failure can leave the producer uncertain.

Use publisher confirms for important messages:

```text
Producer publishes
   |
   v
RabbitMQ accepts and persists/replicates as required
   |
   v
RabbitMQ confirms
   |
   v
Producer marks message as safely published
```

Without confirms, at-least-once publishing is hard to prove.

---

## Exchange Types and Routing Patterns

### Direct Exchange

A direct exchange routes by exact routing key.

```text
Routing key: payment.capture
Binding key: payment.capture
Result: match
```

Use for:

- Command routing.
- Service-specific queues.
- Explicit job types.

Example:

```text
payment.commands exchange
  payment.capture -> payment-capture.queue
  payment.refund  -> payment-refund.queue
```

### Fanout Exchange

A fanout exchange sends every message to every bound queue.

```text
              +------------------+
Producer ---> | fanout exchange  |
              +------------------+
                |       |       |
                v       v       v
               Q1      Q2      Q3
```

Use for:

- Broadcast notifications.
- Cache invalidation.
- Multiple independent services reacting to the same event.

### Topic Exchange

A topic exchange routes using wildcard patterns.

Wildcards:

- `*` matches one word.
- `#` matches zero or more words.

Example:

```text
Routing key: order.eu.created

Binding: order.*.created  -> matches
Binding: order.#          -> matches
Binding: payment.#        -> does not match
```

Use for:

- Domain events.
- Tenant/region/service routing.
- Flexible publish/subscribe.

### Headers Exchange

A headers exchange routes based on message headers instead of routing keys.

Use sparingly. It is useful when routing depends on multiple metadata fields,
but topic exchanges are simpler and more common.

---

## Queue Types

RabbitMQ has several queue models. Choose based on workload.

### Classic Queue

Classic queues are traditional RabbitMQ queues.

Good for:

- Simple transient work queues.
- Non-replicated workloads.
- Local development and lower-criticality jobs.

Tradeoffs:

- A single queue has one logical leader.
- It is not the best default for highly available critical workloads.
- Mirrored classic queues are legacy compared with quorum queues.

### Quorum Queue

Quorum queues are replicated queues built for data safety and predictable
failure recovery. They use a replicated log model and elect a new leader if the
current leader fails.

Good for:

- Critical task queues.
- Payment, order, ledger, notification, and workflow jobs where loss is not
  acceptable.
- At-least-once processing with durability.
- Multi-node high availability.

Tradeoffs:

- Replication costs CPU, disk, and network.
- A queue still has a leader, so one queue does not scale infinitely.
- Throughput must be scaled by partitioning work across multiple queues or by
  using streams/super streams when appropriate.

Typical setup:

```text
3 RabbitMQ nodes
Quorum queue with 3 replicas
Leader on one node, followers on other nodes
Publisher confirm after the write is replicated as required
```

### Stream Queue

RabbitMQ Streams are append-only logs inside RabbitMQ.

Good for:

- High-throughput event ingestion.
- Replayable consumers.
- Time or size based retention.
- Multiple consumers reading at different offsets.
- Workloads that look more like Kafka topics than task queues.

Tradeoffs:

- Different client and operational model than classic AMQP queues.
- Best when consumers read a stream of events, not when each message should be
  removed after one worker handles it.

### Super Stream

A super stream partitions a logical stream across multiple stream partitions.

```text
Super stream: invoices
  invoices-0
  invoices-1
  invoices-2
  invoices-3
```

Good for:

- Scaling stream throughput beyond one stream partition.
- Key-based ordering per partition.
- High-volume event workloads where replay matters.

---

## Delivery Guarantees

### At-Most-Once

The producer publishes and the consumer does not require strong retry behavior.

```text
If something fails, the message may be lost.
```

Use for:

- Non-critical telemetry.
- Best-effort notifications.
- Metrics where loss is acceptable.

### At-Least-Once

The system may deliver a message more than once, but should not lose it once
accepted.

Required pieces:

- Durable queue.
- Persistent message.
- Publisher confirms.
- Manual consumer acknowledgements.
- Idempotent consumer logic.
- Dead-letter handling.

This is the default reliable architecture for RabbitMQ.

### Exactly-Once

RabbitMQ does not magically provide end-to-end exactly-once business processing.

Exactly-once requires coordination between:

- Message broker.
- Consumer side effects.
- Database writes.
- External APIs.
- Retry behavior.

In real systems, design for at-least-once delivery and idempotent processing.

Common patterns:

- Idempotency key per message.
- Unique constraint on business operation ID.
- Inbox table for consumed message IDs.
- Outbox table for produced events.
- Deduplication cache with TTL when full history is not needed.

### Ordering

RabbitMQ preserves useful ordering only within constraints.

Ordering is strongest when:

- One queue receives messages for a key.
- One active consumer processes that queue.
- Messages are acked in order.
- Messages are not requeued to the front in surprising ways.

Ordering weakens when:

- Multiple consumers process the same queue concurrently.
- Messages fail and are redelivered.
- Priorities are enabled.
- Producers publish concurrently without a clear keying strategy.

For strict per-key ordering at scale:

```text
Hash business key -> shard queue
One active consumer per shard or per-key serialization in the worker
```

For high-throughput replayable ordering:

```text
Use RabbitMQ streams/super streams or Kafka partitions.
```

---

## Consumer Design

### Manual Acknowledgement

Use manual acknowledgement for important work.

```text
Receive message
   |
   v
Validate
   |
   v
Perform side effect
   |
   v
Commit result
   |
   v
Ack message
```

Do not ack before the side effect is durable. If the worker crashes after ack
but before the database commit, the message is lost from the broker.

### Prefetch

Prefetch controls how many unacknowledged messages RabbitMQ can deliver to a
consumer.

```text
prefetch = max in-flight messages per consumer
```

If prefetch is too low:

- Consumers may sit idle waiting for the next delivery.
- Throughput suffers.

If prefetch is too high:

- One slow worker can hoard many messages.
- Redelivery after failure becomes bursty.
- Memory usage grows.
- Queue latency becomes uneven.

Starting points:

| Workload | Suggested Prefetch Starting Point |
|---|---:|
| Slow jobs, seconds each | 1 to 10 |
| API calls, 50 ms to 500 ms | 10 to 100 |
| Fast CPU/light IO work | 100 to 1,000 |
| Batch consumers | Tune with benchmark and memory limits |

Always tune with real processing time, payload size, and failure behavior.

### Consumer Concurrency

Required concurrency follows Little's Law:

```text
required_concurrency ~= target_messages_per_second * average_processing_seconds
```

Example:

```text
Target rate: 20,000 messages/sec
Average processing time: 50 ms = 0.05 sec

Required active processing slots:
20,000 * 0.05 = 1,000 concurrent slots
```

If one worker process runs 20 concurrent handlers:

```text
1,000 / 20 = 50 worker processes
```

Then set prefetch around the actual concurrency, or slightly above it:

```text
prefetch ~= 20 to 40 per worker process
```

### Idempotent Consumer

Every consumer should assume duplicate delivery is possible.

Example with an idempotency table:

```text
Message:
  event_id = evt-123
  operation = capture_payment
  order_id = ord-77

Consumer transaction:
  1. Insert event_id into processed_messages.
  2. If insert fails because event_id exists, ack and skip.
  3. Perform payment state transition.
  4. Commit transaction.
  5. Ack message.
```

### Backpressure

Backpressure is a feature, not a failure. It tells producers that consumers or
brokers cannot keep up.

RabbitMQ can apply flow control when memory or disk alarms are triggered.
Applications should also apply business-level backpressure:

- Stop accepting optional work.
- Return `429` or `503` from upstream APIs.
- Slow producers.
- Shed low-priority messages.
- Increase consumers only if downstream dependencies can handle the load.

---

## Failure Handling, Retries, and DLQs

### Why Retries Need Design

If a consumer simply rejects and immediately requeues a failing message, it can
create a hot loop:

```text
fail -> requeue -> redeliver -> fail -> requeue -> redeliver
```

That burns CPU and blocks useful work.

Use delayed retries and a dead-letter queue.

### Dead-Letter Exchange

A queue can be configured to dead-letter messages to an exchange when:

- The consumer rejects/nacks without requeue.
- The message expires.
- The queue exceeds a length limit.
- Delivery limit behavior is reached for supported queue types/configuration.

```text
main.queue
  |
  | failure
  v
retry.exchange
  |
  v
retry.1m.queue -> after TTL -> main.exchange
retry.5m.queue -> after TTL -> main.exchange
retry.30m.queue -> after TTL -> main.exchange
  |
  v
dead-letter.queue
```

### Retry Strategy

Use explicit retry tiers:

```text
Attempt 1: immediate processing
Attempt 2: retry after 1 minute
Attempt 3: retry after 5 minutes
Attempt 4: retry after 30 minutes
Attempt 5: move to DLQ
```

Include retry metadata:

```json
{
  "event_id": "evt-123",
  "attempt": 3,
  "first_seen_at": "2026-05-24T10:00:00Z",
  "last_error": "payment gateway timeout"
}
```

### Poison Messages

A poison message always fails because of bad data or an unrecoverable business
condition.

Examples:

- Invalid schema.
- Missing required business entity.
- Unsupported enum value.
- Payload too large.
- Consumer code bug.

Poison messages should move to DLQ quickly. Do not let them block healthy
messages.

### DLQ Runbook

A production DLQ needs an operating model:

- Who owns the DLQ?
- What alerts fire when messages appear?
- How are messages inspected safely?
- Which failures are replayable?
- Which failures require data correction?
- How do you prevent replay storms?
- How do you track original routing key and failure reason?

---

## Use Cases

### 1. Background Job Processing

Example:

```text
API request -> enqueue image resize job -> return 202
Worker -> resize image -> update database -> ack
```

Why RabbitMQ fits:

- Work distribution is simple.
- Consumers can scale horizontally.
- Failed jobs can retry.
- The API stays low latency.

### 2. Order Workflow Commands

Example:

```text
Order Service publishes:
  routing key: payment.capture
  payload: order_id, amount, payment_method

Payment Worker consumes:
  payment-capture.queue
```

Why RabbitMQ fits:

- Routing commands by action is natural.
- Manual ack protects against worker crash.
- DLQ isolates failed orders.

### 3. Fanout Notifications

Example:

```text
UserRegistered event
  -> email queue
  -> analytics queue
  -> fraud queue
  -> CRM sync queue
```

Why RabbitMQ fits:

- Fanout exchanges broadcast the same message to many queues.
- Each consumer group has independent backlog and failure handling.

### 4. Topic-Based Domain Events

Example routing keys:

```text
order.us.created
order.eu.cancelled
payment.in.captured
shipment.apac.delayed
```

Bindings:

```text
order.*.created    -> onboarding.queue
order.#            -> order-audit.queue
payment.#          -> finance.queue
*.eu.*             -> eu-compliance.queue
```

Why RabbitMQ fits:

- Topic routing is expressive.
- Producers do not need to know every consumer.

### 5. Request/Reply

Example:

```text
Service A -> request queue -> Service B
Service B -> reply_to queue -> Service A
```

Why RabbitMQ fits:

- AMQP supports correlation IDs and reply queues.
- Useful for internal RPC-like workflows when HTTP coupling is undesirable.

Use carefully. Request/reply over a broker can become hidden synchronous
coupling if timeouts and ownership are not clear.

### 6. IoT and Edge Ingestion

RabbitMQ can support protocols such as MQTT through plugins.

Good for:

- Device command routing.
- Gateway buffering.
- Low-latency device notifications.

For massive event retention and analytics replay, Kafka or a dedicated stream
platform may be a better fit.

### 7. High-Throughput Replayable Events

Use RabbitMQ Streams or super streams when you need:

- Append-only storage.
- Multiple consumers with independent offsets.
- Replay from earlier positions.
- Partitioned high throughput.

If the workload is mainly an organization-wide immutable event log, Kafka is
usually the more natural default.

---

## Scaling RabbitMQ for Millions of Records

"Millions of records" is not specific enough for capacity planning. The design
depends on whether you mean:

- Millions per day.
- Millions per hour.
- Millions per minute.
- Millions per second.
- Millions stored in backlog.
- Millions replayed by new consumers.

RabbitMQ can handle high volumes, but scaling is not automatic just because you
add nodes. You must design around queue leaders, routing, consumers, disk, and
downstream capacity.

### Scaling Principle 1: Benchmark the Exact Workload

Throughput depends heavily on:

- Message size.
- Persistent vs transient messages.
- Classic vs quorum vs stream queues.
- Publisher confirm strategy.
- Consumer ack strategy.
- Prefetch.
- Number of queues.
- Number of publishers and consumers.
- Disk latency and fsync behavior.
- Replication factor.
- Network bandwidth.

Use tools such as RabbitMQ PerfTest or Quiver to benchmark:

```text
message size
publish rate
consumer rate
confirm latency
p50/p95/p99 end-to-end latency
queue depth growth
redelivery rate
broker CPU, memory, disk, network
```

Do not size a production RabbitMQ cluster from generic numbers alone.

### Scaling Principle 2: One Queue Is Not Infinite

A single queue has a leader. That leader is a bottleneck for routing, ordering,
state, and disk work.

Adding nodes helps when:

- You distribute many queues across nodes.
- Queue leaders are balanced.
- Consumers are spread across queues.
- Work is partitioned.
- Streams/super streams are partitioned.

Adding nodes does not magically make one hot queue scale linearly.

### Scaling Principle 3: Partition by Business Key

For high volume, shard work across queues.

```text
orders.exchange
  |
  | hash(order_id) % 64
  v
order-events.q00
order-events.q01
order-events.q02
...
order-events.q63
```

Benefits:

- More queue leaders.
- More broker nodes can participate.
- More consumers can process in parallel.
- Per-key ordering can be preserved if the same key always maps to the same
  shard.

Common partition keys:

- `order_id`
- `customer_id`
- `tenant_id`
- `merchant_id`
- `account_id`
- `device_id`

Bad partition keys:

- A constant value.
- A timestamp bucket that creates a single hot bucket.
- A low-cardinality status such as `CREATED`.
- A region if one region dominates traffic.

### Scaling Principle 4: Use the Right Queue Type

| Requirement | Better RabbitMQ Choice |
|---|---|
| Critical task delivery | Quorum queue |
| Low-criticality simple queue | Classic queue |
| Replayable event stream | Stream queue |
| Partitioned replayable event stream | Super stream |
| Global immutable event backbone | Usually Kafka |

For millions of durable task messages, prefer many quorum queues over one
massive quorum queue.

For millions of replayable records, consider RabbitMQ Streams/super streams or
Kafka.

### Scaling Principle 5: Keep Messages Small

RabbitMQ is a broker, not object storage.

Prefer:

```json
{
  "event_id": "evt-123",
  "object_uri": "s3://bucket/path/object.json",
  "checksum": "sha256:...",
  "metadata": {}
}
```

over putting a multi-megabyte payload directly in the message.

Large messages cause:

- Higher memory pressure.
- Higher disk pressure.
- Slower replication.
- Longer redelivery time.
- Worse p99 latency.
- More painful DLQ inspection.

### Scaling Principle 6: Tune Publisher Confirms

Publisher confirms are required for reliable publishing, but waiting after every
single message is slow.

Bad high-throughput pattern:

```text
publish one message
wait for confirm
publish next message
wait for confirm
```

Better pattern:

```text
publish many messages with an in-flight window
receive confirms asynchronously
retry unconfirmed messages when needed
```

Tune:

- Confirm batch/window size.
- Number of publisher channels.
- Number of producer instances.
- Message persistence.
- Routing distribution.

### Scaling Principle 7: Tune Consumers and Prefetch

Consumer throughput is usually the real bottleneck.

Measure:

```text
consumer_rate = messages processed per second
average_processing_time
p95_processing_time
downstream dependency latency
error rate
redelivery rate
```

Scale consumers until one of these becomes limiting:

- RabbitMQ delivery throughput.
- Database write capacity.
- External API rate limit.
- CPU.
- Memory.
- Network.
- Lock contention or ordering constraint.

### Scaling Principle 8: Control Backlog Growth

RabbitMQ can buffer messages, but an unbounded queue is a production incident.

Set policies:

- Maximum queue length where appropriate.
- Message TTL where stale messages should expire.
- Dead-letter exchange.
- Alert on queue depth and age of oldest message.
- Producer throttling.
- Autoscaling consumers from queue lag.

Important metric:

```text
backlog_seconds = queue_ready_messages / current_consume_rate_per_second
```

Example:

```text
queue_ready_messages = 3,000,000
consume_rate = 50,000/sec

backlog_seconds = 60 seconds
```

A queue with 3 million messages may be fine if consumers drain it in 60 seconds.
It is not fine if consumers drain it in 12 hours and the business SLA is 5
minutes.

### Scaling Principle 9: Balance Queue Leaders

For quorum queues and streams, leaders do most of the coordination work.

Operational goals:

- Spread queue leaders across broker nodes.
- Avoid all hot queues landing on one node.
- Monitor per-node publish, deliver, disk, and CPU.
- Move/rebalance workloads when traffic shifts.

### Scaling Principle 10: Separate Workloads

Do not put every workload on one RabbitMQ cluster.

Separate clusters when workloads have different:

- Criticality.
- Message size.
- Retention.
- Latency SLA.
- Traffic pattern.
- Tenant boundary.
- Operational owner.

Example:

```text
Cluster A: payment/order critical quorum queues
Cluster B: notification fanout queues
Cluster C: analytics streams
Cluster D: development/test
```

This prevents a noisy analytics workload from hurting payment processing.

---

## Reference Architecture for Millions of Records

Assume a workload:

```text
Traffic: 50,000 records/sec peak
Message size: 2 KB average
Durability: required
Processing SLA: p95 under 2 minutes
Ordering: per order_id
Failure handling: retries + DLQ
```

### High-Level Architecture

```text
                         +------------------+
                         | Producer Fleet   |
                         | API / Services   |
                         +--------+---------+
                                  |
                                  | publisher confirms
                                  v
                         +------------------+
                         | orders.exchange  |
                         | topic/direct     |
                         +--------+---------+
                                  |
                                  | hash(order_id) -> shard
                                  v
        +-------------------------+--------------------------+
        |                         |                          |
        v                         v                          v
+---------------+         +---------------+          +---------------+
| orders.q000   |  ...    | orders.q031   |   ...    | orders.q063   |
| quorum queue  |         | quorum queue  |          | quorum queue  |
+-------+-------+         +-------+-------+          +-------+-------+
        |                         |                          |
        v                         v                          v
+---------------+         +---------------+          +---------------+
| Worker group  |         | Worker group  |          | Worker group  |
| shard 000     |         | shard 031     |          | shard 063     |
+-------+-------+         +-------+-------+          +-------+-------+
        |                         |                          |
        +------------+------------+-------------+------------+
                     |                          |
                     v                          v
             +---------------+          +---------------+
             | Database /    |          | Retry + DLQ   |
             | Side Effects  |          | Exchanges     |
             +---------------+          +---------------+
```

### Design Choices

Use a sharded exchange/queue layout:

```text
64 quorum queues
3 or 5 RabbitMQ nodes
3 replicas per quorum queue
Queue leaders balanced across nodes
Consumers scaled per shard
```

Use per-key routing:

```text
shard = hash(order_id) % 64
```

This preserves per-order ordering while allowing different orders to process in
parallel.

Use publisher confirms:

```text
Producer maintains in-flight publish window.
Confirmed messages are marked published.
Unconfirmed messages are retried with same event_id.
```

Use idempotent consumers:

```text
processed_messages(event_id primary key)
business update in same transaction when possible
ack only after commit
```

Use retry tiers:

```text
orders.retry.1m
orders.retry.5m
orders.retry.30m
orders.dlq
```

Use autoscaling:

```text
scale workers by:
  queue depth
  age of oldest message
  consume rate
  downstream saturation
```

### Data Flow

```text
1. Producer validates event and assigns event_id.
2. Producer publishes to orders.exchange with routing key based on order_id.
3. Exchange routes to one shard queue.
4. RabbitMQ writes to quorum queue and confirms publish.
5. Consumer receives message with bounded prefetch.
6. Consumer inserts event_id into idempotency table.
7. Consumer performs business side effect.
8. Consumer commits transaction.
9. Consumer acknowledges message.
10. Failure routes to retry queue or DLQ depending on attempt count.
```

### Scaling From 1M/Day to 1M/Minute

| Scale | Approx Rate | Practical Design |
|---|---:|---|
| 1M/day | 12 msg/sec average | A few quorum queues may be enough |
| 1M/hour | 278 msg/sec average | Multiple consumers, benchmark durability |
| 1M/minute | 16,667 msg/sec average | Sharded queues, balanced leaders, tuned confirms |
| 10M/minute | 166,667 msg/sec average | Streams/super streams or Kafka likely needed |

The exact threshold depends on message size, durability, replication, and
consumer work. The design should be benchmark-driven.

### When to Use RabbitMQ Streams Instead

Use streams/super streams if:

- You need replay.
- You need many independent consumers reading the same history.
- Records are event facts, not commands.
- Retention is time/size based.
- Throughput is more important than task-style deletion after ack.

Architecture:

```text
Producer -> super stream invoices
              |
              +-> stream partition 0
              +-> stream partition 1
              +-> stream partition 2
              +-> stream partition 3

Consumer group A reads offsets independently.
Consumer group B reads offsets independently.
```

At this point, compare seriously with Kafka because the workload has become a
streaming/log workload.

---

## Capacity Planning

### Step 1: Define the SLA

Write this down before choosing topology:

```text
Peak publish rate:
Average message size:
Maximum message size:
Durability requirement:
Replication requirement:
Ordering requirement:
Replay requirement:
Retention requirement:
Maximum acceptable backlog age:
Consumer p95 processing time:
Downstream capacity:
Failure/retry policy:
```

### Step 2: Estimate Broker Write Load

Approximate ingress bandwidth:

```text
ingress_MBps = messages_per_second * average_message_size_bytes / 1,048,576
```

Example:

```text
50,000 msg/sec * 2 KB = about 100 MB/sec ingress payload
```

With quorum replication, network and disk work are higher than payload ingress:

```text
effective_write_load ~= ingress * replication_factor * protocol_overhead
```

This is not an exact formula. Use it to understand magnitude, then benchmark.

### Step 3: Estimate Consumer Concurrency

```text
required_concurrency = target_rate * average_processing_seconds
```

Example:

```text
target_rate = 50,000/sec
average_processing = 20 ms = 0.02 sec

required_concurrency = 1,000 active handlers
```

If each pod runs 50 handlers:

```text
worker_pods = 1,000 / 50 = 20 pods
```

Add headroom:

```text
production_pods = 20 * 1.5 = 30 pods
```

### Step 4: Estimate Queue Shards

Benchmark one shard first:

```text
single_shard_safe_rate = measured_rate_at_target_p99_latency
```

Then:

```text
required_shards = ceil(peak_rate / single_shard_safe_rate * safety_factor)
```

Example:

```text
peak_rate = 50,000/sec
single_shard_safe_rate = 1,500/sec
safety_factor = 1.5

required_shards = ceil(50,000 / 1,500 * 1.5)
required_shards = 50
```

Choose a round number with growth room:

```text
64 shards
```

### Step 5: Validate Hot Key Risk

Hash partitioning assumes keys are distributed.

Check:

- Top 1 percent of keys by volume.
- Tenant skew.
- Regional skew.
- Batch jobs that publish with the same key.
- Retry storms from one customer or merchant.

If a single key can dominate traffic, per-key ordering may be expensive. You may
need:

- Key salting.
- Per-entity rate limits.
- A special hot-key lane.
- Relaxed ordering for that workload.

### Step 6: Define Backlog Budget

If the SLA says p95 processing under 2 minutes:

```text
max_backlog_messages = consume_rate_per_sec * 120 sec
```

At 50,000/sec:

```text
max_backlog = 6,000,000 messages
```

Alert before this:

```text
warning at 50 percent = 3,000,000
critical at 80 percent = 4,800,000
```

Also alert on oldest message age, because queue depth alone can be misleading.

---

## Operations and Observability

### Metrics to Monitor

Broker:

- CPU.
- Memory.
- Disk free.
- Disk IOPS and latency.
- Network throughput.
- File descriptors.
- Connection and channel count.
- Flow control events.
- Memory and disk alarms.

Queue:

- Ready messages.
- Unacknowledged messages.
- Publish rate.
- Deliver rate.
- Ack rate.
- Redelivery rate.
- Consumer count.
- Consumer utilization.
- Age of oldest message.
- Dead-letter rate.

Quorum queue / stream:

- Leader distribution.
- Replica health.
- Raft or replication lag indicators.
- Leader changes.
- Member availability.

Application:

- Publish confirm latency.
- Publish failures.
- Unroutable messages.
- Consumer processing latency.
- Consumer error rate.
- Retry attempt distribution.
- DLQ count by reason.
- Idempotency conflicts.
- Downstream dependency latency.

### Alert Examples

```text
Queue oldest message age > SLA threshold
DLQ count > 0 for critical queues
Publish confirm p99 latency > normal baseline
Consumer ack rate < publish rate for 10 minutes
Redelivery rate suddenly increases
One node owns too many hot queue leaders
Disk free below safety threshold
Memory alarm active
Flow control active for sustained period
```

### Production Hardening Checklist

- Durable exchanges and queues for important workloads.
- Persistent messages for important workloads.
- Publisher confirms enabled.
- Manual acknowledgements enabled.
- Idempotency key present in every message.
- Retry and DLQ policy defined.
- Queue length/TTL policy reviewed.
- Prefetch tuned.
- Consumers autoscale from backlog and latency.
- Large payloads stored outside the broker.
- Queue leaders balanced.
- Broker nodes spread across failure domains.
- Client reconnect logic tested.
- Disaster recovery runbook written.
- DLQ replay tooling rate-limited.

### Common Production Incidents

#### Incident: Queue Depth Keeps Growing

Likely causes:

- Consumers are too slow.
- Downstream database/API is saturated.
- Prefetch is too low.
- A hot shard is overloaded.
- Consumers are crashing and redelivering.
- Broker is under disk or memory pressure.

Fix path:

```text
Check publish vs ack rate.
Check oldest message age.
Check consumer error rate.
Check downstream latency.
Scale consumers only if downstream can handle it.
Shard hot queues if one leader is saturated.
Throttle producers if the system is beyond capacity.
```

#### Incident: Duplicate Processing

Likely causes:

- Consumer crashed after side effect before ack.
- Consumer timed out and message was redelivered.
- Producer retried after uncertain publish.
- DLQ replay duplicated old messages.

Fix path:

```text
Add idempotency key.
Use unique constraints or inbox table.
Ack only after durable commit.
Make publisher retry preserve event_id.
```

#### Incident: DLQ Explodes

Likely causes:

- Bad deployment.
- Schema mismatch.
- Downstream outage.
- Poison data.
- Retry delay too aggressive.

Fix path:

```text
Pause replay.
Group DLQ by error reason.
Roll back or fix consumer.
Validate schema compatibility.
Replay gradually with rate limits.
```

---

## RabbitMQ vs Kafka

### Short Version

Use RabbitMQ when you need a broker that routes work to consumers.

Use Kafka when you need a durable event log that many consumers can replay.

### Detailed Comparison

| Dimension | RabbitMQ | Kafka |
|---|---|---|
| Core model | Broker with exchanges, queues, bindings, consumers | Distributed append-only log with topics and partitions |
| Primary abstraction | Queue | Topic partition |
| Message lifecycle | Message is usually removed after consumer ack | Record stays until retention deletes it |
| Routing | Rich broker-side routing: direct, topic, fanout, headers | Producer chooses topic and partition; routing is simpler |
| Consumer model | Broker pushes messages to consumers with prefetch | Consumers pull records and commit offsets |
| Ack model | Per-message ack/nack | Offset commits per consumer group |
| Replay | Not natural for normal queues; possible with streams | First-class feature |
| Retention | Queue backlog until ack/expiry/limit; streams support retention | Time/size retention by design |
| Ordering | Per queue under constraints | Per partition |
| Scaling unit | More queues, more consumers, streams/super streams | More partitions and brokers |
| Best for commands/tasks | Excellent | Possible but less natural |
| Best for event history | Possible with streams | Excellent |
| Backpressure | Broker flow control and queue growth | Consumer lag and quotas |
| Message routing patterns | Very strong | Limited compared with exchanges |
| Latency | Very low for brokered task delivery | Low, often optimized for throughput and batching |
| Throughput | High, workload-dependent | Very high for log workloads |
| Exactly-once | Use idempotency; no general end-to-end exactly-once | Kafka transactions support exactly-once within Kafka constraints |
| Multi-consumer fanout | Bind many queues to exchange | Multiple consumer groups read same topic |
| Delayed/retry workflows | Natural with DLX/TTL/retry queues | Usually retry topics and app logic |
| Operational risk | Hot queues, flow control, unbounded backlog | Partition skew, consumer lag, broker disk pressure |

### Architectural Difference

RabbitMQ:

```text
Producer -> Exchange -> Queue -> Consumer

Message belongs to a queue.
Consumer ack removes it.
Routing is broker-side.
```

Kafka:

```text
Producer -> Topic Partition -> Consumer Group

Record belongs to a partition log.
Consumers track offsets.
Retention removes it later.
Routing is mostly topic/partition choice.
```

### Example: OrderCreated Event

RabbitMQ design:

```text
order.events exchange
  order.created -> email.queue
  order.created -> fraud.queue
  order.created -> analytics.queue

Each queue gets its own copy.
Each service acks independently.
If email fails, fraud is unaffected.
```

Kafka design:

```text
Topic: order-events
Partition key: order_id

Consumer group: email-service
Consumer group: fraud-service
Consumer group: analytics-service

Each group tracks its own offsets.
New consumers can replay old events if retention allows.
```

### When RabbitMQ Is Better

Choose RabbitMQ when:

- You need complex routing.
- You need work queues.
- Messages represent commands more than facts.
- Each task should be processed by one worker.
- You need natural retry/DLQ workflows.
- You want low-latency task delivery.
- You need request/reply patterns.
- You have multiple routing rules per message.
- Replay is not a central requirement.

Examples:

- Send email.
- Generate invoice PDF.
- Capture payment.
- Resize image.
- Update search index.
- Trigger warehouse sync.
- Fan out cache invalidation.

### When Kafka Is Better

Choose Kafka when:

- You need long retention and replay.
- Many teams need to consume the same event history.
- You are building an event backbone.
- You need high-throughput append-only ingestion.
- Consumers may come online later and read historical data.
- Stream processing is central.
- You need compacted topics for latest state by key.
- You need integration with Kafka Streams, Flink, Connect, lakehouse, or OLAP.

Examples:

- Clickstream ingestion.
- Audit log.
- Transaction event journal.
- CDC pipeline.
- Product analytics.
- ML feature/event pipeline.
- Lakehouse ingestion.
- Real-time stream processing.

### When Both Are Used Together

Many systems use both:

```text
User action
   |
   +-> RabbitMQ command queue for immediate task execution
   |
   +-> Kafka topic for durable event history and analytics
```

Example:

```text
OrderCreated
   |
   +-> RabbitMQ: capture payment, send confirmation email
   |
   +-> Kafka: analytics, audit, data lake, fraud model features
```

This avoids forcing one tool to serve every messaging need.

---

## Design Rules and Interview Takeaways

### RabbitMQ Rules

- Use RabbitMQ for commands, tasks, routing, and async work distribution.
- Use quorum queues for critical durable queues.
- Use streams/super streams when you need replayable high-throughput streams.
- Use publisher confirms for reliable publishing.
- Use manual acknowledgements for reliable consuming.
- Make every consumer idempotent.
- Do not put huge payloads in messages.
- Do not rely on one queue for unlimited throughput.
- Partition high-volume workloads across queues or streams.
- Tune prefetch based on processing time and memory.
- Treat DLQ as a production workflow, not a trash can.
- Monitor oldest message age, not only queue depth.
- Benchmark with the same message size, durability, and replication you will
  use in production.

### Kafka Rules

- Use Kafka for durable event history, replay, stream processing, and analytics.
- Partition by the key that needs ordering.
- Design retention and compaction intentionally.
- Monitor consumer lag.
- Keep consumers idempotent even with Kafka.
- Avoid global ordering requirements.

### Interview Answer Template

If asked "How would you scale RabbitMQ for millions of records?", answer:

```text
1. First I would clarify the rate: millions per day, hour, minute, or second.
2. I would classify the workload: task queue, pub/sub routing, or replayable stream.
3. For critical task queues, I would use durable quorum queues with publisher
   confirms and manual consumer acknowledgements.
4. I would not depend on one huge queue. I would shard by business key across
   many queues and balance queue leaders across broker nodes.
5. I would tune producers with async publisher confirms and tune consumers with
   bounded prefetch.
6. I would make consumers idempotent and use retry queues plus DLQ.
7. I would autoscale consumers from queue age, depth, and consume rate, while
   respecting downstream capacity.
8. If the requirement includes replay, long retention, or very high append-only
   throughput, I would evaluate RabbitMQ Streams/super streams or Kafka.
9. I would benchmark the exact workload with production-like message size,
   persistence, replication, and consumer behavior.
```

### Quick Decision Matrix

| Requirement | Pick |
|---|---|
| Work queue for async jobs | RabbitMQ |
| Complex routing by topic patterns | RabbitMQ |
| Retry and DLQ heavy workflow | RabbitMQ |
| Request/reply over messaging | RabbitMQ |
| Durable event log | Kafka |
| Replay events for new consumers | Kafka |
| Stream processing backbone | Kafka |
| Append millions/sec with retention | Kafka, or evaluate RabbitMQ super streams |
| Critical replicated task queue | RabbitMQ quorum queue |
| High-throughput replay inside RabbitMQ ecosystem | RabbitMQ streams/super streams |

---

## Security, Governance, and Multi-Tenancy

RabbitMQ is often placed in the middle of critical production workflows. Treat
it like a stateful data system, not just a convenience library.

### Authentication

Production authentication options commonly include:

- Internal RabbitMQ users for simple environments.
- TLS client certificates for strong workload identity.
- LDAP/OAuth2 integration in enterprise environments.
- Separate users per application, not one shared application account.

Do not use default guest credentials in production. The default `guest` user is
for local development style usage only.

### Authorization

RabbitMQ permissions are scoped by virtual host and resource regexes:

```text
configure: which exchanges/queues a user can declare or modify
write:     which exchanges a user can publish to
read:      which queues a user can consume from
```

Use least privilege:

```text
order-api publisher:
  configure: none in strict production
  write:     ^orders\.exchange$
  read:      none

payment-worker consumer:
  configure: none in strict production
  write:     ^orders\.retry\.exchange$|^orders\.dlx$
  read:      ^payment\..*\.queue$
```

The strictest production model is:

- Platform/IaC owns topology declaration.
- Applications publish and consume only.
- Emergency operators can inspect and drain queues through audited access.

### TLS and Network Security

Use TLS for client-to-broker traffic when traffic crosses host, subnet, cluster,
or trust boundaries.

Production controls:

- TLS on AMQP listener.
- Separate management UI/API listener from data listener.
- Private network exposure only.
- Security groups or firewall rules per producer/consumer group.
- No public broker access unless there is a deliberate edge messaging design.
- mTLS for high-sensitivity systems.

### Virtual Hosts

Virtual hosts are logical namespaces. Use them for isolation, but do not confuse
them with hard resource isolation.

Good vhost boundaries:

- `prod-orders`
- `prod-notifications`
- `stage-orders`
- `tenant-a-critical` when tenant separation is required

Avoid putting unrelated workloads in one vhost just because they belong to the
same company.

### Topology Ownership

For critical systems, declare exchanges, queues, bindings, policies, and limits
through infrastructure automation:

```text
Terraform / Ansible / Helm / RabbitMQ definitions
   |
   v
RabbitMQ topology
   |
   v
Applications only publish/consume
```

This prevents a bad deployment from accidentally changing queue durability,
dead-lettering, or routing behavior at runtime.

### Message Privacy

RabbitMQ stores messages in broker memory/disk while they are waiting to be
delivered. If messages contain sensitive information:

- Encrypt connections with TLS.
- Consider payload-level encryption for high-sensitivity data.
- Keep PII out of messages when an ID reference is enough.
- Set retention/TTL on non-critical queues.
- Protect management UI access because it can expose message bodies.
- Avoid dumping message payloads in application logs.

### Schema Governance

RabbitMQ does not enforce schema compatibility by itself. Teams must govern
message contracts.

Recommended message envelope:

```json
{
  "event_id": "01J9...",
  "event_type": "order.created",
  "schema_version": 3,
  "occurred_at": "2026-05-24T09:30:00Z",
  "producer": "order-service",
  "correlation_id": "req-...",
  "idempotency_key": "order-123:created:v3",
  "tenant_id": "merchant-91",
  "payload": {}
}
```

Compatibility rules:

- Add optional fields safely.
- Never change field meaning without a new version.
- Do not remove fields until all consumers are upgraded.
- Include event type and schema version in every message.
- Keep consumers tolerant of unknown fields.

### Auditability

For critical workflows, audit both topology and message processing:

- Who changed exchange/queue/policy definitions?
- Who replayed a DLQ?
- Which deployment version produced poison messages?
- Which consumer acknowledged a high-value payment command?
- Which correlation ID connects API request, message, consumer, and database
  write?

RabbitMQ alone will not give complete business audit trails. Store business
state transitions in application databases or an audit/event store.

---

## Deployment, Upgrades, and Disaster Recovery

### Cluster Shape

Common production cluster shape:

```text
3 nodes minimum for HA quorum workloads
5 nodes for larger critical clusters or more failure tolerance
Nodes spread across availability zones when latency permits
Fast persistent disks
Dedicated broker hosts or reserved Kubernetes resources
```

Do not scale a RabbitMQ cluster by simply adding nodes and expecting one hot
queue to become faster. A single normal queue has a leader. Scale throughput by
adding queues, streams, partitions, and consumer groups around the workload.

### Kubernetes Deployment Notes

RabbitMQ can run well on Kubernetes, but it is stateful infrastructure.

Production requirements:

- Use StatefulSets or a proven RabbitMQ operator.
- Use persistent volumes with predictable IOPS and latency.
- Avoid aggressive pod eviction.
- Set CPU and memory requests realistically.
- Use anti-affinity so replicas do not land on one worker node.
- Use PodDisruptionBudgets for controlled maintenance.
- Backup definitions and critical metadata.
- Test node loss, volume loss, and rolling restart behavior before production.

Do not run critical queues on cheap, slow, burst-limited disks and then expect
stable publisher confirm latency during spikes.

### Rolling Upgrades

Upgrade strategy:

```text
1. Read release notes and compatibility rules.
2. Test on staging with production-like queues and traffic.
3. Confirm clients are compatible.
4. Disable risky topology auto-declarations from old app versions.
5. Drain or reduce non-critical traffic if needed.
6. Upgrade one broker node at a time.
7. Verify cluster health, queue leaders, confirms, and consumer recovery.
8. Continue only when metrics return to baseline.
```

Key checks after every node:

- Cluster membership healthy.
- No unexpected leader churn.
- Publish confirms still flowing.
- Consumers reconnected.
- No sustained flow control.
- Queue depth and oldest message age stable.

### Backup Strategy

Back up:

- Broker definitions: users, vhosts, exchanges, queues, bindings, policies.
- Infrastructure configuration.
- TLS certificates and secret rotation process.
- Application message schemas.
- DLQ replay tools and runbooks.

Do not assume queue message backup is your recovery strategy. Long-lived
business truth should live in application databases, event stores, object
storage, or analytics systems. Queues are for delivery and buffering.

### Disaster Recovery

RabbitMQ DR depends on workload type:

| Workload | DR Strategy |
|---|---|
| Reconstructable background jobs | Rebuild from source database/outbox |
| Critical commands | Use transactional outbox before publish |
| Fanout notifications | Recompute missing notifications where possible |
| Replayable history | Use streams with retention or Kafka/event store |
| Cross-region command delivery | Prefer active/passive with explicit failover |

For a critical order system, the durable source of truth is usually:

```text
Orders DB + transactional outbox
```

RabbitMQ is the transport. If a cluster is lost, the system can republish
unpublished or unprocessed work from the outbox instead of depending on a queue
snapshot.

### Multi-Region Patterns

RabbitMQ is not a magic global queue. Cross-region messaging requires explicit
latency and failure trade-offs.

Common models:

| Pattern | How It Works | Tradeoff |
|---|---|---|
| Regional clusters | Each region has its own broker and local consumers | Best latency, more application routing |
| Active/passive | One primary broker cluster, standby region ready | Simpler consistency, failover complexity |
| Federation/shovel | Broker-to-broker movement for selected routes | Extra operational complexity |
| Outbox replication | Database/outbox replicates, publishers run per region | More reliable recovery model |
| Event log backbone | Kafka/event store bridges regions, RabbitMQ handles local work | More moving parts, clearer responsibilities |

Avoid synchronous cross-region quorum queues for latency-sensitive workloads
unless you have verified the write latency and failure behavior.

---

## Real-World Production Case Study: Marketplace Order Platform

### Business Context

Assume a marketplace processes orders from web, mobile, and partner APIs.

Peak target:

```text
Normal traffic:       5,000 orders/minute
Campaign peak:       1,000,000 order-related messages/minute
Message size:        1 KB to 4 KB
Ordering need:       Per order_id, not global
Reliability:         No accepted order command should be lost
Consumer behavior:   Payment, inventory, invoice, email, search, fraud
SLA:                 p95 critical processing under 2 minutes
```

RabbitMQ is a good fit for the command/task side:

- Capture payment.
- Reserve inventory.
- Generate invoice.
- Send confirmation email.
- Update search index.
- Trigger fraud review.
- Notify warehouse system.

For long-term event analytics, the same platform may also publish to Kafka or a
lakehouse. RabbitMQ should not become the only event history.

### System Goals

Functional goals:

- Accept orders quickly.
- Process downstream tasks asynchronously.
- Retry transient failures.
- Isolate poison messages.
- Keep per-order operations ordered where required.
- Allow independent scaling of payment, inventory, and notification workers.

Non-functional goals:

- At-least-once delivery.
- No silent loss after order accepted.
- Bounded backlog age.
- Controlled replay from DLQ.
- Full traceability by `correlation_id` and `order_id`.
- Safe degradation during downstream outages.

### High-Level Architecture

```text
                 +------------------+
                 | Client/API       |
                 +--------+---------+
                          |
                          v
                 +------------------+
                 | Order Service    |
                 | DB transaction   |
                 | + outbox row     |
                 +--------+---------+
                          |
                          v
                 +------------------+
                 | Outbox Publisher |
                 | confirms enabled |
                 +--------+---------+
                          |
                          v
                 +------------------+
                 | orders.exchange  |
                 | topic exchange   |
                 +---+------+---+---+
                     |      |   |
        +------------+      |   +----------------+
        v                   v                    v
+----------------+  +----------------+   +----------------+
| payment shard  |  | inventory shard|   | notification   |
| quorum queues  |  | quorum queues  |   | queues         |
+-------+--------+  +-------+--------+   +-------+--------+
        |                   |                    |
        v                   v                    v
+---------------+   +---------------+    +---------------+
| Payment       |   | Inventory     |    | Email/SMS     |
| Workers       |   | Workers       |    | Workers       |
+-------+-------+   +-------+-------+    +-------+-------+
        |                   |                    |
        +---------+---------+---------+----------+
                  |
                  v
          +---------------+
          | Retry + DLQ   |
          | per workflow  |
          +---------------+
```

### Why Use the Transactional Outbox

Without an outbox:

```text
1. Order Service writes order to DB.
2. Service publishes message to RabbitMQ.
3. Service crashes between these steps.
```

Now the order exists but no downstream task was published.

With an outbox:

```text
1. In one DB transaction:
   - insert order
   - insert outbox event
2. Background publisher reads unsent outbox rows.
3. Publisher sends to RabbitMQ with publisher confirms.
4. Publisher marks outbox row as published only after confirm.
```

This is the core production pattern for reliable publishing from a database
owned service.

### Exchange and Routing Design

Use topic exchanges for domain events and direct exchanges for command lanes.

```text
orders.events exchange
  order.created
  order.cancelled
  order.payment_authorized
  order.inventory_reserved

orders.commands exchange
  payment.capture
  inventory.reserve
  invoice.generate
  notification.send
```

Example bindings:

```text
payment.capture      -> payment.capture.q00 ... payment.capture.q63
inventory.reserve    -> inventory.reserve.q00 ... inventory.reserve.q63
invoice.generate     -> invoice.generate.q00 ... invoice.generate.q31
notification.send    -> notification.email.q00 ... notification.email.q15
order.*              -> audit.order-events.stream
```

Use explicit naming:

```text
<domain>.<workflow>.<shard>.queue
<domain>.<workflow>.retry.<delay>.queue
<domain>.<workflow>.dlq
```

Example:

```text
payment.capture.q17
payment.capture.retry.1m
payment.capture.retry.10m
payment.capture.dlq
```

### Queue Selection

Use quorum queues for critical command processing:

```text
payment.capture.q00..q63: quorum queues
inventory.reserve.q00..q63: quorum queues
invoice.generate.q00..q31: quorum queues
notification.email.q00..q15: quorum queues or classic queues depending on SLA
```

Use streams/super streams for replayable event history inside RabbitMQ:

```text
order-audit.super-stream
payment-status.super-stream
```

Decision:

| Workload | Queue Type | Reason |
|---|---|---|
| Capture payment | Quorum | Critical, replicated, ack after side effect |
| Reserve inventory | Quorum | Critical, needs retry and ordering by SKU/order |
| Send email | Quorum or classic | Depends on loss tolerance and volume |
| Audit trail | Stream/super stream | Replay, retention, many readers |
| Analytics firehose | Stream/super stream or Kafka | Append-only, high throughput |

### Partitioning and Ordering

Global ordering is not required and would destroy throughput. Per-order ordering
is enough.

Partition:

```text
shard = hash(order_id) % shard_count
```

Benefits:

- All commands for one order go to the same shard.
- Different orders process in parallel.
- Hot queues can be observed independently.
- Workers can scale per workflow.

For inventory, the ordering key may be different:

```text
inventory shard = hash(sku_id) % shard_count
```

This avoids two workers racing on the same stock keeping unit.

### Producer Design

Producer rules:

- Use persistent messages for critical tasks.
- Use publisher confirms.
- Keep an in-flight publish window.
- Retry unconfirmed publishes with the same `event_id`.
- Mark outbox row published only after confirm.
- Handle unroutable messages with mandatory publishing or return handling where
  supported by the client.
- Do not publish huge payloads.

Producer pseudocode:

```text
while true:
  rows = load_unpublished_outbox(limit=1000)
  for row in rows:
    publish(row.exchange, row.routing_key, row.payload, persistent=true)
    track publish_seq_no -> row.id

  on publisher_confirm(seq_no):
    mark outbox row as published

  on publisher_nack_or_timeout(seq_no):
    retry later with same event_id
```

The same message may be published twice during uncertainty. Consumers must be
idempotent.

### Consumer Design

Consumer rules:

- Use manual acknowledgements.
- Set prefetch based on processing time and memory.
- Ack only after durable side effect succeeds.
- Nack/reject intentionally.
- Make side effects idempotent.
- Emit business and infrastructure metrics.
- Stop consuming when downstream dependency is unhealthy.

Consumer pseudocode:

```text
on message:
  parse envelope
  validate schema_version

  begin transaction
    if event_id already processed:
      commit
      ack
      return

    apply business change
    insert processed_message(event_id)
  commit

  ack
```

If the consumer crashes after the database commit but before the ack, RabbitMQ
will redeliver. The `processed_message` check makes the second attempt safe.

### Retry Design

Separate retries by error class.

Transient errors:

- Downstream timeout.
- HTTP 503.
- Temporary database lock.
- Rate limit from third-party service.

Permanent errors:

- Invalid schema.
- Missing required business entity.
- Unsupported event type.
- Data violates business invariant.

Retry policy:

```text
Attempt 1: immediate processing
Attempt 2: retry after 30 seconds
Attempt 3: retry after 2 minutes
Attempt 4: retry after 10 minutes
Attempt 5: retry after 1 hour
Attempt 6: DLQ
```

Implementation with DLX/TTL queues:

```text
payment.capture.q17
   |
   | failure attempt=1
   v
payment.capture.retry.30s
   |
   | TTL expires, dead-letter back
   v
payment.capture.q17
```

Message headers:

```json
{
  "x-attempt": 3,
  "x-first-failure-at": "2026-05-24T09:31:00Z",
  "x-last-error-type": "PAYMENT_GATEWAY_TIMEOUT",
  "x-last-error-message": "gateway timeout after 2s"
}
```

Do not retry poison messages forever. Permanent failures should go to DLQ
quickly.

### DLQ Operating Model

Every critical DLQ needs an owner and a runbook.

DLQ fields to preserve:

- Original exchange.
- Original routing key.
- Original queue.
- Event ID.
- Correlation ID.
- Attempt count.
- Error class.
- Last error.
- Consumer version.
- Timestamp of first and last failure.

DLQ workflow:

```text
1. Alert owner.
2. Classify by error reason.
3. Stop bad consumer rollout if needed.
4. Fix schema, data, or downstream dependency.
5. Replay a tiny sample.
6. Watch idempotency, duplicate rate, and downstream load.
7. Replay gradually with a rate limit.
8. Produce incident notes and prevention action.
```

Never build a replay tool that republishes one million DLQ messages instantly
into the same broken path.

### Backpressure and Flow Control

RabbitMQ uses multiple mechanisms to prevent unbounded overload, including
credit-based flow control, memory/disk alarms, publisher confirms, and consumer
acknowledgements with prefetch.

Application-level backpressure should also exist:

```text
If publish confirm p99 rises:
  reduce producer publish window

If queue oldest age rises:
  scale consumers if downstream is healthy

If downstream p99 rises:
  pause or slow consumers

If broker memory/disk alarm fires:
  throttle producers and investigate backlog
```

Scaling consumers is only correct when the downstream system can absorb more
load. If the payment gateway is rate-limiting, more consumers make the incident
worse.

### Autoscaling Workers

Do not autoscale only on queue depth. Use a compound signal:

```text
desired_workers = f(
  oldest_message_age,
  ready_messages,
  ack_rate,
  processing_latency,
  downstream_error_rate,
  downstream_latency
)
```

Example policy:

```text
Scale out if:
  oldest_message_age > 60 seconds
  and ack_rate < publish_rate
  and downstream_error_rate < 2 percent
  and CPU < 70 percent

Scale in if:
  oldest_message_age < 10 seconds for 15 minutes
  and ready_messages near zero
```

### Capacity Example

Campaign peak:

```text
1,000,000 messages/minute = 16,667 messages/second
Average payload = 2 KB
Payload ingress = about 33 MB/second
Quorum replication factor = 3
Effective broker write/network work is much higher than payload ingress
```

If one queue shard safely handles 1,000 messages/second at required p99:

```text
required_shards = 16,667 / 1,000 = 17
with 2x headroom = 34
choose 64 shards
```

Worker estimate:

```text
consumer processing time = 40 ms average
required_concurrency = 16,667 * 0.040 = 667 active handlers
if one pod runs 40 handlers:
  minimum pods = 17
with headroom:
  production pods = 25 to 35
```

This is a starting estimate. The final number must come from a benchmark using
real message size, quorum replication, confirms, prefetch, and downstream
latency.

### Observability for the Case Study

Dashboards:

- Broker health: CPU, memory, disk, network, file descriptors.
- Cluster health: node up/down, partitions, leader distribution.
- Queue health: ready, unacked, publish rate, ack rate, redelivery rate.
- SLA health: oldest message age, p95/p99 end-to-end latency.
- Producer health: confirm latency, nacks, returns, outbox lag.
- Consumer health: processing latency, error rate, retry rate, idempotency hits.
- DLQ health: count by workflow, reason, consumer version.
- Downstream health: DB/API latency, timeout, rate limit, saturation.

Critical alerts:

```text
payment.capture oldest message age > 120 seconds
payment.capture.dlq count > 0
publish confirm p99 > 500 ms for 10 minutes
redelivery rate > baseline * 5
outbox unpublished rows older than 60 seconds
consumer ack rate < publish rate for 15 minutes
memory alarm active
disk alarm active
one node owns > 50 percent of hot queue leaders
```

### Failure Scenarios

#### Payment Gateway Down

Expected behavior:

```text
Payment workers see gateway failures.
Workers classify errors as transient.
Messages move to retry queues with increasing delay.
Consumers slow down when gateway rate limits.
DLQ receives only messages that exceed max attempts.
Order state remains PAYMENT_PENDING.
Customer receives delayed payment status, not duplicate charges.
```

Key controls:

- External payment API idempotency key.
- Circuit breaker in workers.
- Retry budget.
- DLQ after max attempts.
- Alert on pending payment age.

#### Consumer Bug Introduced

Expected behavior:

```text
New consumer version fails schema parsing.
DLQ rises by error reason and version.
Deployment is rolled back.
DLQ sample is inspected.
Replay is rate-limited after fix.
```

Key controls:

- Canary deployment.
- Schema compatibility tests.
- DLQ includes consumer version.
- Replay tool supports filtering by error reason.

#### RabbitMQ Node Fails

Expected behavior for quorum queues:

```text
Cluster detects node failure.
Queue leaders on failed node are unavailable briefly.
New leaders are elected where quorum exists.
Clients reconnect.
Publishers retry unconfirmed messages.
Consumers continue after reconnect.
```

Key controls:

- 3 or 5 node cluster.
- Quorum queue replicas across nodes.
- Client reconnect with jitter.
- Publisher retry with same event ID.
- Idempotent consumers.

#### Broker Flow Control

Expected behavior:

```text
Publisher confirms slow down.
Application publish window shrinks.
Producers stop unbounded retry loops.
Operators inspect memory, disk, and queue backlog.
Consumers drain backlog if downstream is healthy.
```

Key controls:

- Publish timeout and circuit breaker.
- Outbox lag alert.
- Oldest message age alert.
- Disk/memory capacity headroom.

### Security Design for the Case Study

```text
vhost: prod-orders

users:
  order-api-publisher
  outbox-publisher
  payment-worker
  inventory-worker
  notification-worker
  platform-operator
```

Permissions:

- Publishers can write only to approved exchanges.
- Consumers can read only their queues.
- Applications cannot change topology in production.
- Operators need audited break-glass access.

Network:

- AMQP over TLS.
- Management UI only on private admin network.
- Broker access restricted by Kubernetes NetworkPolicies or cloud security
  groups.
- Secrets rotated through the platform secret manager.

### Cost and Resource Controls

Control cost by controlling:

- Message size.
- Queue count and replication factor.
- Backlog retention.
- Retry storm amplification.
- Disk IOPS.
- Consumer over-scaling into saturated downstream systems.

Resource rules:

- Store large documents/images in object storage and pass a reference.
- Set queue length/TTL policies where loss is acceptable.
- Separate analytics streams from critical payment queues.
- Benchmark quorum queue disk requirements with fsync behavior.
- Do not use RabbitMQ as a permanent database.

### What This Architecture Guarantees

It can guarantee:

- Accepted outbox rows are eventually published unless the source DB is lost.
- Broker-accepted durable messages survive normal broker restarts and tolerated
  node failures.
- Consumers process at least once.
- Duplicate messages are harmless when idempotency is correct.
- Poison messages are isolated in DLQ.

It does not guarantee:

- Global ordering.
- End-to-end exactly-once side effects.
- Infinite backlog.
- Infinite throughput from one queue.
- Cross-region zero-data-loss failover without a broader data replication
  strategy.

---

## Production Handling Playbook

This section is a direct checklist of how to handle common RabbitMQ production
requirements.

### Reliable Publish Handling

Use when a message must not be silently lost after the service accepts work.

Required:

- Transactional outbox when publishing after a database write.
- Durable exchange and queue.
- Persistent messages.
- Publisher confirms.
- Retry on nack/timeout with the same event ID.
- Idempotent consumers.

Avoid:

- Fire-and-forget publish for critical workflows.
- Marking business work complete before the publish is confirmed or recorded in
  an outbox.

### Reliable Consumer Handling

Required:

- Manual ack.
- Ack after side effect, not before.
- Prefetch limit.
- Idempotency table or idempotent business operation.
- Retry classification.
- DLQ after max attempts.

Decision:

```text
success -> ack
transient failure -> reject/nack without immediate hot loop; route to retry
permanent failure -> reject/nack to DLQ
process crash -> broker redelivers after connection/channel closes
```

### Duplicate Handling

Duplicates can come from:

- Producer retry after uncertain publish.
- Consumer crash after side effect before ack.
- Broker redelivery.
- DLQ replay.
- Network timeout.

Patterns:

- `processed_messages(event_id primary key)`.
- Unique business operation key.
- External API idempotency keys.
- Conditional updates.
- Upserts with version checks.

### Ordering Handling

Do:

- Define the ordering key explicitly.
- Route all messages for that key to one shard queue or stream partition.
- Process with concurrency that does not violate that key's order.

Do not:

- Demand global ordering for an entire marketplace.
- Mix unrelated ordering domains in one queue.
- Replay old DLQ messages without considering current entity version.

### Backlog Handling

Backlog is acceptable only when it is within the business delay budget.

Watch:

- Oldest message age.
- Ready messages.
- Ack rate vs publish rate.
- Consumer utilization.
- Downstream latency.

Actions:

```text
consumer healthy, downstream healthy -> scale consumers
consumer healthy, downstream saturated -> slow consumers/producers
broker saturated -> shard, move leaders, add capacity, reduce payload
single hot key -> split or isolate hot key
poison messages -> DLQ quickly
```

### Retry Storm Handling

Retry storms happen when failed messages return too quickly and overwhelm the
same broken dependency.

Controls:

- Exponential backoff.
- Max attempts.
- Jitter.
- Circuit breakers.
- Rate-limited DLQ replay.
- Separate retry queues per delay.
- Bulkhead different workflows into separate queues/clusters.

### Large Payload Handling

Do not put large files in RabbitMQ messages.

Use:

```text
1. Store file/blob in S3/GCS/Azure Blob/internal object store.
2. Publish message with object URI, checksum, size, and metadata.
3. Consumer fetches object.
4. Consumer validates checksum.
```

This keeps broker memory, disk, network, DLQ inspection, and retries
manageable.

### Slow Consumer Handling

Symptoms:

- Unacked messages high.
- Consumer memory high.
- Processing latency high.
- Ack rate below publish rate.

Fixes:

- Reduce prefetch if workers hold too many messages.
- Increase workers if downstream is healthy.
- Optimize handler logic.
- Batch downstream writes when safe.
- Split queues by workload.
- Move long-running work to job state machine rather than holding a message for
  hours.

### Unroutable Message Handling

Unroutable messages happen when no binding matches.

Controls:

- Use mandatory publish/return handling where supported.
- Alert on returned messages.
- Test topology before deployment.
- Keep topology definitions in IaC.
- Add a parking exchange only when it has an owner and runbook.

### Poison Message Handling

Poison messages fail every time.

Controls:

- Validate schema at the edge.
- Send permanent failures to DLQ quickly.
- Include error reason and consumer version.
- Do not let one poison message block a queue.
- Build replay tooling that can edit, skip, or quarantine messages.

### Replay Handling

Before replaying:

- Confirm the consumer bug or data issue is fixed.
- Confirm idempotency is in place.
- Replay a sample first.
- Rate limit replay.
- Preserve original correlation IDs.
- Track replay operator and reason.

Replay command should support:

```text
filter by queue
filter by error reason
filter by event type
filter by time range
limit N messages
dry run
rate per second
new routing key override
```

### Stream Replay Handling

For RabbitMQ Streams, replay is offset based.

Use streams when:

- Consumers need to reread history.
- Many independent consumers need the same messages.
- Large backlog and retention are normal.
- Events are facts, not one-time commands.

Use offset tracking:

```text
consumer reads from offset
consumer processes message
consumer stores offset after successful processing
consumer resumes from stored offset + 1
```

Super streams add partitioning, usually by a routing key, so a logical stream
can scale beyond one stream partition.

### Schema Change Handling

Deployment sequence:

```text
1. Add optional field to producer.
2. Deploy consumers that tolerate old and new schema.
3. Start producing new field.
4. Wait until old messages drain or expire.
5. Remove old field only after all consumers no longer need it.
```

Never deploy a consumer that only understands a new schema while old messages
are still in the queue.

### Incident Review Template

```text
Incident:
Start time:
End time:
Affected queues:
Affected workflows:
Business impact:
Peak queue depth:
Peak oldest message age:
DLQ count:
Root cause:
Why alerts did/did not catch it:
What prevented data loss:
What duplicated:
Replay performed:
Follow-up actions:
Owner:
Due date:
```

### Architect-Level Summary

RabbitMQ at million scale is not one setting. It is the combination of:

- Correct workload fit.
- Right queue type.
- Durable topology.
- Publisher confirms.
- Manual acks.
- Idempotent consumers.
- Sharding by business key.
- Bounded prefetch.
- Retry and DLQ design.
- Flow-control-aware producers.
- Oldest-message-age monitoring.
- Operational runbooks.
- Benchmarking with production-like data.

If the workload is a command/task pipeline, RabbitMQ can be a strong production
choice. If the workload is long-retention event history with many replaying
consumers, use RabbitMQ Streams/super streams or evaluate Kafka.

---

## References

The current RabbitMQ documentation was checked through Context7 using the
official `/rabbitmq/rabbitmq-website` documentation source.

Relevant RabbitMQ documentation areas:

- RabbitMQ reliability guide: clustering, replicated structures, quorum queues,
  streams, and leader failover:
  https://github.com/rabbitmq/rabbitmq-website/blob/main/versioned_docs/version-4.3/reliability.md
- RabbitMQ worker tutorial: quorum queue declaration, manual acknowledgements,
  and prefetch/QoS:
  https://github.com/rabbitmq/rabbitmq-website/blob/main/tutorials/tutorial-two-go.md
- RabbitMQ durable queue tutorial:
  https://github.com/rabbitmq/rabbitmq-website/blob/main/tutorials/tutorial-one-python.md
- RabbitMQ performance benchmark material with PerfTest:
  https://github.com/rabbitmq/rabbitmq-website/blob/main/blog/2022-05-16-rabbitmq-3.10-performance-improvements/index.md
- RabbitMQ AMQP benchmark material with Quiver:
  https://github.com/rabbitmq/rabbitmq-website/blob/main/blog/2024-08-21-amqp-benchmarks/index.md
- RabbitMQ super streams material:
  https://github.com/rabbitmq/rabbitmq-website/blob/main/blog/2022-07-13-rabbitmq-3-11-feature-preview-super-streams/index.md
- RabbitMQ dead-lettering material:
  https://github.com/rabbitmq/rabbitmq-website/blob/main/blog/2022-03-29-at-least-once-dead-lettering/index.md
