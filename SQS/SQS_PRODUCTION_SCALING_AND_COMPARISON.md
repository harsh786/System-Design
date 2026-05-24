# Amazon SQS Production Scaling and Messaging Comparison

## Purpose

This guide explains how to scale Amazon SQS in production, where SQS is a good fit, where it is a weak fit, and how to choose between SQS, Kafka, and RabbitMQ.

---

## Mental Model

Amazon SQS is a managed task queue.

Use it when producers need to hand off work to consumers asynchronously, and consumers can process each message independently. SQS is not a durable event log like Kafka and not a programmable routing broker like RabbitMQ.

```
Producer -> SQS queue -> Worker fleet / Lambda -> Side effects / database
```

The most important production rule:

> Design every SQS consumer as idempotent because SQS standard queues use at-least-once delivery and a message can be delivered more than once.

---

## SQS Queue Types

| Queue type | Use when | Tradeoff |
|---|---|---|
| Standard queue | You need very high throughput and can tolerate duplicate or out-of-order processing | At-least-once delivery, best-effort ordering |
| FIFO queue | You need ordering and deduplication for a business key such as `orderId`, `accountId`, or `paymentId` | Throughput and concurrency depend on message groups |

### Standard Queue

Use standard queues for most background processing:

- Email, notification, indexing, image processing, report generation.
- Fanout workers where order does not matter.
- High-volume buffering between services.
- Spike absorption before a slower downstream system.

### FIFO Queue

Use FIFO queues when order matters within a specific entity:

- Payment state transitions for one payment.
- Order lifecycle events for one order.
- Inventory updates for one SKU.
- Account-level command sequencing.

Do not use one global FIFO message group for everything. That serializes the workload. Use many message group IDs, usually one per entity key.

FIFO deduplication protects against duplicate messages being added to the queue within the deduplication interval. It does not make your database writes, external API calls, or business side effects exactly once. Consumers should still be idempotent.

### Throughput Planning

Standard queues are the default choice for very high-throughput task processing because AWS scales the queue service automatically.

FIFO queues need more deliberate design:

- Without batching, FIFO throughput is limited by API transaction rates.
- With batching, each API call can carry up to 10 messages.
- High-throughput FIFO mode can raise throughput substantially, but parallelism still depends on distributing work across many message group IDs.
- The practical scaling question is not just "How many messages per second can SQS accept?" It is "How many messages per second can my consumers safely process and acknowledge?"

---

## Production Scaling Checklist

### 1. Pick the Right Queue Type First

If order is not a hard requirement, prefer a standard queue. It gives the simplest scaling model.

If order is required, use FIFO with a high-cardinality `MessageGroupId`. FIFO parallelism comes from the number of active message groups. If all messages use the same group, only one ordered stream can progress at a time.

### 2. Make Consumers Idempotent

SQS can redeliver messages when:

- A consumer crashes after doing the side effect but before deleting the message.
- The visibility timeout expires before processing completes.
- Network or API errors happen during delete.
- Standard queue replicas return a duplicate.

Common idempotency patterns:

- Store `messageId`, `eventId`, or business operation ID in a dedupe table.
- Use conditional writes, unique constraints, or optimistic locking.
- Make external calls with idempotency keys when the downstream API supports it.
- Treat `DeleteMessage` as acknowledgement, not proof that the business action happened exactly once.

### 3. Tune Visibility Timeout

Visibility timeout is the time a message stays hidden after a consumer receives it.

Set it slightly above the normal processing time. If work duration varies, start with a moderate timeout and extend it with `ChangeMessageVisibility` heartbeats while the worker is still alive.

Avoid setting visibility timeout too high by default. A failed message will not be retried until the timeout expires, so high values slow recovery.

Rules of thumb:

- Processing usually takes 10 seconds: use 30-60 seconds.
- Processing usually takes 2 minutes: use 3-5 minutes.
- Processing may take longer unpredictably: use heartbeat extension.
- Processing can exceed 12 hours: do not hold one SQS message that long; split the job or use Step Functions.

### 4. Watch In-Flight Message Limits

An in-flight message has been received but not deleted yet.

For most standard queues, AWS documents an approximate 120,000 in-flight message limit. If consumers receive messages and hold them for a long time, scaling can stall even when the backlog is large.

How to avoid this:

- Delete messages immediately after successful processing.
- Keep visibility timeout close to actual processing time.
- Use batching where safe.
- Increase worker throughput before in-flight count becomes the bottleneck.
- Split traffic across multiple queues if one queue becomes a hard bottleneck.
- Request quota increases where AWS supports it.

### 5. Use Long Polling

Enable long polling with `ReceiveMessageWaitTimeSeconds` up to 20 seconds.

Benefits:

- Fewer empty receives.
- Lower SQS API cost.
- Better behavior during low traffic.
- Less noisy consumer loops.

Short polling is rarely the right default for production consumers.

### 6. Use Batching Carefully

SQS supports batching for send, receive, and delete operations. Batch size is up to 10 messages per API call for common SQS batch APIs.

Use batching to improve throughput and reduce cost, but keep these constraints in mind:

- Batch processing should still report per-message success/failure.
- One bad message should not repeatedly fail the whole batch.
- With Lambda, enable partial batch responses using `ReportBatchItemFailures` so successfully processed records are not retried unnecessarily.

### 7. Control Consumer Concurrency

Scaling SQS usually means scaling consumers, not the queue.

For ECS, EC2, or Kubernetes workers:

- Scale on queue depth and age of oldest message.
- Limit concurrency to protect databases and downstream APIs.
- Use per-tenant or per-priority queues if one workload can starve another.
- Use worker-level rate limits for fragile dependencies.

For Lambda consumers:

- Tune `BatchSize`.
- Use `MaximumBatchingWindowInSeconds` for standard queues when batching latency is acceptable.
- Configure maximum concurrency on the SQS event source mapping to protect downstream systems.
- Ensure Lambda reserved concurrency is at least the sum of event source maximum concurrency values.
- For FIFO, concurrency is capped by active message groups or the configured maximum concurrency, whichever is lower.

### 8. Design Retry and DLQ Policy

Every production queue should have a dead-letter queue unless there is a deliberate reason not to.

Decide:

- `maxReceiveCount`: how many times a message can fail before DLQ.
- Whether retries should be immediate, delayed, exponential, or state-machine driven.
- Who owns DLQ inspection and replay.
- How poison messages are fixed before redrive.

Bad DLQ practice:

- Redrive everything blindly into the source queue.
- Keep retrying permanent validation errors.
- Alert only on queue depth, not on message age or DLQ growth.

Better DLQ practice:

- Include error type, failure reason, attempt count, and correlation ID in logs.
- Separate transient failures from permanent bad payloads.
- Replay small batches after fixing the root cause.
- Build a manual or automated quarantine process for unsafe messages.

### 9. Monitor the Right Metrics

Key CloudWatch metrics:

- `ApproximateNumberOfMessagesVisible`: backlog waiting to be processed.
- `ApproximateNumberOfMessagesNotVisible`: in-flight messages.
- `ApproximateAgeOfOldestMessage`: backlog latency and strongest signal of user impact.
- `NumberOfMessagesSent`: producer rate.
- `NumberOfMessagesReceived`: consumer receive rate.
- `NumberOfMessagesDeleted`: successful acknowledgement rate.
- DLQ visible message count and oldest message age.

Useful derived signals:

- Backlog drain rate = deletes per minute minus sends per minute.
- Estimated time to drain = visible backlog / delete rate.
- Duplicate rate = processed events already present in idempotency store.
- Poison message signal = DLQ growth or same message failing repeatedly.

### 10. Protect Downstream Systems

SQS can absorb traffic spikes, but the database or API behind your worker may not.

Use:

- Worker concurrency limits.
- Lambda maximum concurrency.
- Token bucket or leaky bucket rate limiting.
- Circuit breakers for failing dependencies.
- Separate queues for expensive work.
- Priority queues when urgent work must bypass bulk jobs.

Backpressure should be explicit. Without it, scaling consumers can turn an SQS backlog into a database incident.

### 11. Handle Payload Size and Retention

Important limits:

- Message size is up to 1 MiB.
- Message retention is up to 14 days.
- Delay queues and message timers are up to 15 minutes.
- Visibility timeout can be up to 12 hours.

For larger payloads:

- Store the large body in S3.
- Put only a pointer, checksum, object version, and metadata in SQS.
- Make sure S3 object lifecycle is longer than the SQS retention and retry window.

For schedules longer than 15 minutes:

- Prefer EventBridge Scheduler for precise future delivery.
- Use Step Functions for long-running workflows.
- Use a database state table plus poller if scheduling is business-specific.

### 12. Secure the Queue

Production queues should include:

- IAM least privilege for producers and consumers.
- Server-side encryption where required.
- Resource policies only when cross-account access is needed.
- VPC endpoints for private access from VPC workloads.
- No sensitive payloads unless encryption, access control, and retention policies are acceptable.
- Correlation IDs for traceability.

### 13. Plan for Multi-Region Explicitly

SQS is highly available within an AWS Region, but it is not a cross-region replicated event log.

If your system needs regional disaster recovery:

- Decide whether messages can be regenerated from source-of-truth data.
- Replicate the business event before or while sending to SQS.
- Consider Kafka, Kinesis, DynamoDB streams, or application-level outbox replication for replay needs.
- Document what happens to in-flight messages during failover.

---

## Common SQS Use Cases

### Background Job Processing

Use SQS to move slow work out of request-response paths.

Examples:

- Image resizing.
- PDF generation.
- Email delivery.
- Search indexing.
- Data enrichment.
- Webhook delivery.

### Microservice Decoupling

One service can publish work without waiting for another service to be available.

This is useful when:

- The consumer has variable latency.
- The producer should not fail just because the consumer is down.
- You need retry and buffering between services.

### Traffic Spike Buffering

SQS can smooth bursty producer traffic before a constrained consumer.

Example:

```
API -> SQS -> Worker fleet -> third-party API with rate limit
```

The queue protects the API path, while worker concurrency protects the third-party dependency.

### Lambda Event Processing

SQS is a strong fit for Lambda when:

- Work is independent per message.
- Retry behavior is acceptable.
- You need a buffer between events and Lambda concurrency.
- You want to cap concurrency to protect a database.

### Fanout with SNS + SQS

Use SNS to publish one event to many SQS queues.

```
Producer -> SNS topic
             |-> SQS queue for billing
             |-> SQS queue for email
             |-> SQS queue for analytics
```

Each consumer gets its own queue, retry policy, DLQ, and scaling behavior.

### Transactional Outbox Worker

A service writes business state and an outbox record in the same database transaction. A relay reads the outbox and sends SQS messages.

This reduces the risk of:

- Database update succeeds but message publish fails.
- Message publish succeeds but database update rolls back.

### Delayed Retry and Deferred Work

Use SQS delay queues or message timers for short delays up to 15 minutes.

For longer delays, use EventBridge Scheduler, Step Functions, or a state table based scheduler.

---

## When SQS Is a Weak Fit

SQS is usually not the best choice when:

- You need replayable event history for days, months, or years.
- Many independent consumer groups need to read the same historical stream.
- You need stream processing, joins, windowing, or event-time analytics.
- You need strict global ordering at high throughput.
- You need advanced routing with exchanges, topics, headers, and request-reply semantics.
- You need protocol-level interoperability such as AMQP clients.
- You need on-premise broker control.
- Message processing is one very long-running job instead of small units of work.

---

## SQS vs Kafka vs RabbitMQ

| Dimension | Amazon SQS | Apache Kafka | RabbitMQ |
|---|---|---|---|
| Primary model | Managed queue for tasks | Distributed event log and streaming platform | Message broker with queues, exchanges, bindings |
| Best for | Background jobs, async commands, buffering, retries | Event streams, replay, analytics pipelines, event sourcing, CDC | Complex routing, AMQP workflows, low-latency brokered messaging |
| Operations | AWS fully manages brokers and storage | Self-managed or managed service, still more operational design | Self-managed or managed broker, cluster and queue design matter |
| Retention | Up to 14 days | Configurable by time, size, or compaction | Queue-oriented; messages usually removed after acknowledgement |
| Replay | Limited; not designed as a replay log | Core feature; consumers can rewind offsets | Not the default queue model; streams can support replay use cases |
| Delivery | Standard: at-least-once. FIFO: deduplication within dedupe window | At-least-once by default; exactly-once processing possible with transactions and correct design | At-least-once with acknowledgements and publisher confirms |
| Ordering | Standard: best effort. FIFO: ordered within message group | Ordered within a partition | Queue order can hold, but routing, redelivery, priority, and multiple consumers affect behavior |
| Fanout | Use SNS -> multiple SQS queues | Multiple consumer groups read same topic independently | Exchanges route messages to one or more queues |
| Consumer state | Broker hides messages until delete or timeout | Consumers track offsets | Broker tracks delivery and acknowledgement |
| Scaling unit | Consumers, queues, FIFO message groups | Partitions, brokers, consumer groups | Queues, exchange topology, consumers, cluster nodes |
| Routing | Simple queue target; filtering usually external or SNS/EventBridge | Topic and partition based | Strong routing model: direct, fanout, topic, headers exchanges |
| Large backlog behavior | Good for temporary backlog, limited by retention and in-flight constraints | Designed for durable retained streams | Queues are usually optimized to drain; huge queues require careful design |
| Cloud fit | Excellent inside AWS serverless and microservice systems | Best when stream history is a platform requirement | Best when broker semantics and routing flexibility matter |

---

## Decision Guide

### Choose SQS When

- You want the simplest managed queue on AWS.
- Producers and consumers are in AWS.
- Each message represents one unit of work.
- Processing can be idempotent.
- Backlog retention of up to 14 days is enough.
- You do not need every consumer to replay all historical messages.
- You value low operational burden over broker-level control.

### Choose Kafka When

- Events are a durable product, not just work requests.
- Multiple teams or systems need independent consumption.
- Consumers need to replay from old offsets.
- You need stream processing, event sourcing, CDC, or analytics pipelines.
- Ordering by key and high throughput are core requirements.
- You can operate Kafka correctly or use a managed Kafka service.

### Choose RabbitMQ When

- You need AMQP broker semantics.
- Routing rules are complex and business-specific.
- You need direct, topic, fanout, or headers exchange routing.
- You need request-reply or RPC-style messaging.
- You want fine-grained control over queues, acknowledgements, dead lettering, TTL, priorities, and broker topology.
- You can operate the broker or use a managed RabbitMQ service.

---

## Practical Architecture Patterns

### Pattern 1: Simple Async Worker

```
API service -> SQS standard queue -> worker autoscaling group -> database
```

Use for most background jobs.

Production details:

- Idempotency key in every message.
- DLQ configured.
- Long polling enabled.
- Autoscale workers on oldest message age and backlog.
- Worker concurrency capped to protect the database.

### Pattern 2: Ordered Entity Processing

```
Producer -> SQS FIFO queue -> workers
MessageGroupId = orderId
```

Use when events for the same entity must be processed in order.

Production details:

- Use many message groups.
- Avoid a single global group.
- Keep processing fast so one blocked entity does not build up too much.
- Use DLQ carefully because one poison message can block later messages in the same group until it is resolved or moved.

### Pattern 3: SNS Fanout to SQS

```
Order service -> SNS topic
                 |-> SQS billing queue
                 |-> SQS fulfillment queue
                 |-> SQS notification queue
```

Use when multiple services react to the same event but need independent retry and failure handling.

Production details:

- Each queue has its own DLQ.
- Consumers scale independently.
- Message schema must be versioned.
- Filtering can be done with SNS subscription filters when appropriate.

### Pattern 4: Queue as Downstream Rate Buffer

```
High-volume producer -> SQS -> rate-limited workers -> external API
```

Use when the producer can spike but the dependency has a fixed rate limit.

Production details:

- Worker rate limit is the source of truth.
- Alert on age of oldest message.
- Consider priority queues for urgent work.
- Decide what to do when backlog age approaches business SLA.

---

## Production Interview Answer

If asked "How would you scale SQS in production?", answer like this:

1. Start with the queue type: standard for throughput, FIFO only when ordering is required.
2. Make consumers idempotent because delivery can be at least once.
3. Scale consumers based on queue depth and age of oldest message.
4. Use long polling and batching to reduce cost and improve throughput.
5. Tune visibility timeout to processing time and extend it with heartbeats for long jobs.
6. Watch in-flight messages, DLQ count, oldest message age, receive/delete rates, and downstream saturation.
7. Protect dependencies with maximum concurrency, rate limits, and circuit breakers.
8. Use DLQs and controlled redrive for poison messages.
9. Split queues by workload, priority, tenant, or hot path when isolation is needed.
10. Choose Kafka instead if you need replayable event streams; choose RabbitMQ instead if you need advanced broker routing.

---

## References

- Amazon SQS queue types: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-queue-types.html
- Amazon SQS message quotas: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/quotas-messages.html
- Amazon SQS standard queue quotas: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/quotas-queues.html
- Amazon SQS visibility timeout: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html
- AWS Lambda SQS scaling: https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-scaling.html
- AWS Lambda SQS event source parameters: https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-parameters.html
- Apache Kafka introduction: https://kafka.apache.org/intro/
- Apache Kafka design: https://kafka.apache.org/41/design/design/
- RabbitMQ queues: https://www.rabbitmq.com/docs/queues
- RabbitMQ AMQP concepts: https://www.rabbitmq.com/tutorials/amqp-concepts
- RabbitMQ reliability guide: https://www.rabbitmq.com/docs/reliability
