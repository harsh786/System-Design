# SQS Scalability and Parallel Processing

## Core Idea

SQS scalability is achieved by separating two concerns:

1. SQS stores the backlog.
2. Your consumers provide the processing capacity.

If there are millions of messages in an SQS queue, the queue itself is usually not the first scaling bottleneck. The real question is:

> How many messages per second can the consumer fleet process, safely acknowledge, and commit to downstream systems?

SQS is a pull-based queue. Consumers poll the queue, receive messages, process them, and delete them after success.

```
Millions of messages in SQS
        |
        v
Many consumers polling in parallel
        |
        v
Batch processing + delete after success
        |
        v
Database / API / storage / side effect
```

---

## What Happens If Millions of Messages Are in the Queue?

SQS can store a very large backlog. The number of messages stored in a queue is not the main production concern. The important limits and signals are:

- Message retention: messages expire after the configured retention period, up to 14 days.
- In-flight messages: messages already received by consumers but not yet deleted.
- Visibility timeout: how long a received message is hidden from other consumers.
- Consumer throughput: how fast workers can process and delete messages.
- Downstream capacity: how much traffic your database, cache, or external API can handle.

For a queue with millions of visible messages, SQS does not automatically process them. Processing speed depends on how many workers or Lambda invocations are consuming from the queue.

---

## Standard Queue Parallelism

For a standard queue, parallelism is simple:

```
More consumers = more parallel processing
```

Many workers can call `ReceiveMessage` at the same time. Each worker receives different available messages, processes them, and deletes them.

Example:

```
SQS standard queue with 5,000,000 messages

Worker 1  -> receives batch of 10
Worker 2  -> receives batch of 10
Worker 3  -> receives batch of 10
...
Worker N  -> receives batch of 10
```

If each worker can process 20 messages per second:

```
100 workers  * 20 msg/sec = 2,000 msg/sec
500 workers  * 20 msg/sec = 10,000 msg/sec
1000 workers * 20 msg/sec = 20,000 msg/sec
```

But this is only safe if downstream systems can handle that rate.

---

## FIFO Queue Parallelism

FIFO queues scale differently.

In FIFO, messages with the same `MessageGroupId` are processed in order. SQS will not deliver the next message in the same message group until the current in-flight message is deleted or its visibility timeout expires.

That means:

```
Parallelism in FIFO = number of active message groups
```

Bad design:

```
MessageGroupId = "global"
```

This creates one ordered stream. Even if you run 1,000 workers, only one message group can progress in order.

Better design:

```
MessageGroupId = orderId
MessageGroupId = customerId
MessageGroupId = accountId
MessageGroupId = tenantId
```

Example:

```
Queue has 1,000 active order IDs
Each order ID is one message group
SQS can process many order groups in parallel
Ordering is preserved inside each order ID
```

Use FIFO only when ordering is a hard requirement. If ordering is not required, use a standard queue.

---

## Consumer Scaling Options

### Option 1: Lambda Consumers

With Lambda, SQS is configured as an event source.

For standard queues:

- Lambda polls the queue.
- Lambda starts with a small number of concurrent batches.
- If backlog remains, Lambda increases concurrency.
- AWS documents that an SQS event source mapping can scale up to 1,250 concurrent function invocations by default.
- You can configure maximum concurrency to protect downstream systems.

For FIFO queues:

- Lambda preserves order inside each message group.
- Concurrency is capped by the number of active `MessageGroupId` values or by the configured maximum concurrency, whichever is lower.

Use Lambda when:

- Message processing is short-lived.
- You want serverless scaling.
- You can control downstream pressure with maximum concurrency.
- Processing fits Lambda timeout and memory limits.

### Option 2: ECS, EC2, or Kubernetes Workers

With long-running workers, you control the worker pool.

Typical design:

```
SQS queue -> worker service -> autoscaling policy
```

Scale workers based on:

- `ApproximateNumberOfMessagesVisible`
- `ApproximateAgeOfOldestMessage`
- CPU and memory
- downstream error rate
- processing latency

Use container or VM workers when:

- Processing is long-running.
- You need custom concurrency controls.
- You need stable connections or large local resources.
- You want precise control over batching, backoff, and rate limits.

---

## How to Process Millions of Messages Faster

### 1. Use Horizontal Consumer Scaling

Run many consumers in parallel.

```
1 queue -> 10 workers
1 queue -> 100 workers
1 queue -> 1000 workers
```

The queue can feed many consumers. The hard part is making sure workers do not overload the database or external APIs.

### 2. Use Batch Receive and Batch Delete

SQS receive calls can return up to 10 messages.

Instead of:

```
receive 1 -> process 1 -> delete 1
```

Use:

```
receive 10 -> process 10 -> delete successful messages in batch
```

Benefits:

- Fewer API calls.
- Better worker efficiency.
- Higher throughput per worker.
- Lower cost.

Important: handle partial failures. If 8 messages succeed and 2 fail, delete only the 8 successful messages.

### 3. Use Long Polling

Enable long polling with `WaitTimeSeconds` up to 20 seconds.

Long polling helps because:

- Consumers waste fewer calls on empty responses.
- Cost is lower.
- Workers behave better when the queue is temporarily empty.
- SQS checks more broadly for available messages than short polling.

### 4. Tune Visibility Timeout

Visibility timeout should be longer than normal processing time.

If visibility timeout is too short:

- The same message can become visible before the first worker finishes.
- Another worker can process it again.
- Duplicate processing increases.

If visibility timeout is too long:

- Failed messages take too long to retry.
- In-flight messages stay stuck longer.

For variable processing time, use `ChangeMessageVisibility` as a heartbeat while the worker is still processing.

### 5. Keep In-Flight Messages Under Control

An in-flight message has been received but not deleted.

AWS documents an approximate 120,000 in-flight message limit for standard queues. FIFO queues also have an in-flight quota. If consumers receive too many messages and process them slowly, they can hit this limit.

Ways to avoid in-flight bottlenecks:

- Delete messages immediately after successful processing.
- Keep visibility timeout close to actual processing time.
- Avoid huge local prefetch buffers in workers.
- Scale workers only as far as they can actually finish work.
- Split workloads across queues when isolation is needed.
- Request quota increases if the workload truly needs them.

### 6. Protect Downstream Systems

More SQS consumers can increase throughput, but they can also break dependencies.

Example:

```
SQS can feed 20,000 msg/sec
Database can safely handle 5,000 writes/sec
```

In this case, consumer concurrency must be capped around the database limit. Otherwise, SQS scaling causes a database incident.

Use:

- Lambda maximum concurrency.
- ECS/Kubernetes autoscaling limits.
- worker-level semaphores.
- rate limiters.
- circuit breakers.
- retries with backoff.
- separate queues for slow or expensive work.

---

## Autoscaling Formula

Use backlog and processing rate to estimate worker count.

Definitions:

```
backlog = visible messages in queue
target_drain_time_seconds = how fast you want to clear the backlog
worker_rate = messages processed per worker per second
required_workers = backlog / target_drain_time_seconds / worker_rate
```

Example:

```
backlog = 5,000,000 messages
target drain time = 1 hour = 3,600 seconds
worker rate = 20 msg/sec

required_workers = 5,000,000 / 3,600 / 20
required_workers = 69.4
```

So you need roughly 70 workers, assuming downstream systems can support:

```
70 * 20 = 1,400 msg/sec
```

If the database can support only 700 writes/sec, then the real worker count is closer to:

```
700 / 20 = 35 workers
```

In production, downstream capacity is often the real limit.

---

## Scaling Architecture for Millions of Messages

### Standard Queue Architecture

```
                    +------------------+
Producers --------> | SQS Standard     |
                    | millions backlog |
                    +--------+---------+
                             |
          +------------------+------------------+
          |                  |                  |
          v                  v                  v
    Worker pool A      Worker pool B      Worker pool C
          |                  |                  |
          +------------------+------------------+
                             v
                    Downstream systems
```

Use when:

- Maximum throughput matters.
- Ordering is not required.
- Idempotency is implemented.
- Occasional duplicate delivery is acceptable.

### FIFO Queue Architecture

```
                    +------------------+
Producers --------> | SQS FIFO         |
                    +--------+---------+
                             |
          +------------------+------------------+
          |                  |                  |
          v                  v                  v
    group: order-1     group: order-2     group: order-3
    processed in       processed in       processed in
    order              order              order
```

Use when:

- Ordering is required per entity.
- You can choose high-cardinality message group IDs.
- You understand that one hot message group can become a bottleneck.

---

## Important Metrics

For production scaling, monitor:

| Metric | Why it matters |
|---|---|
| `ApproximateNumberOfMessagesVisible` | Current backlog |
| `ApproximateAgeOfOldestMessage` | How delayed processing has become |
| `ApproximateNumberOfMessagesNotVisible` | In-flight messages being processed |
| `NumberOfMessagesReceived` | Consumer receive rate |
| `NumberOfMessagesDeleted` | Successful processing rate |
| DLQ message count | Poison messages or repeated failures |
| Consumer error rate | Processing quality |
| Downstream latency | Whether dependencies are saturated |

The most important user-impact metric is usually:

```
ApproximateAgeOfOldestMessage
```

A queue depth of 5 million can be fine if the queue is draining within SLA. A queue depth of 50,000 can be bad if the oldest message is already hours late.

---

## Common Bottlenecks

### Bottleneck 1: Too Few Consumers

Symptom:

- Visible messages keep growing.
- Age of oldest message keeps increasing.
- CPU on workers is high or worker count is low.

Fix:

- Add more workers.
- Increase Lambda maximum concurrency.
- Increase worker threads carefully.
- Use batch receives.

### Bottleneck 2: Downstream Is Saturated

Symptom:

- Worker count is high.
- Database/API latency increases.
- Errors and retries increase.
- Queue does not drain despite high concurrency.

Fix:

- Cap consumer concurrency.
- Add rate limiting.
- Scale downstream system.
- Split heavy work into separate queue.

### Bottleneck 3: Visibility Timeout Too Low

Symptom:

- Duplicate processing increases.
- Same messages are processed repeatedly.
- Receive count grows.

Fix:

- Increase visibility timeout.
- Add heartbeat visibility extensions.
- Make processing idempotent.

### Bottleneck 4: FIFO Message Group Is Too Hot

Symptom:

- FIFO queue has many messages.
- Only a small number of consumers are active.
- One message group has most of the backlog.

Fix:

- Increase `MessageGroupId` cardinality.
- Partition the entity key when business ordering allows it.
- Move unordered work to a standard queue.

### Bottleneck 5: In-Flight Limit

Symptom:

- Messages are visible, but consumers receive fewer messages than expected.
- Many messages are not visible.
- Workers hold messages for a long time.

Fix:

- Delete messages faster.
- Reduce local prefetch.
- Shorten visibility timeout where safe.
- Split workload across queues.
- Request quota increase if needed.

---

## Practical Answer

If asked "How do you scale SQS when millions of messages are in the queue?", answer:

1. Use a standard queue if ordering is not required.
2. Run many consumers in parallel.
3. Use batch receive and batch delete with up to 10 messages per call.
4. Enable long polling.
5. Tune visibility timeout to processing duration.
6. Autoscale consumers using backlog and age of oldest message.
7. Cap concurrency based on downstream capacity.
8. Keep consumers idempotent because duplicate delivery can happen.
9. Watch in-flight message count so consumers do not hit queue limits.
10. For FIFO, achieve parallelism by using many `MessageGroupId` values; ordering is only parallel across groups, not inside one group.

---

## Quick Rule

```
Standard SQS:
Parallelism = number of consumers * batch size

FIFO SQS:
Parallelism = min(number of active message groups, consumer concurrency)
```

This is the key difference to remember.

---

## References

- Amazon SQS visibility timeout and in-flight messages: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html
- Amazon SQS message quotas: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/quotas-messages.html
- Amazon SQS FIFO queue quotas: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/quotas-fifo.html
- High throughput for SQS FIFO queues: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/high-throughput-fifo.html
- Amazon SQS short and long polling: https://docs.aws.amazon.com/en_gb/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-short-and-long-polling.html
- AWS Lambda SQS scaling behavior: https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-scaling.html
- AWS Lambda SQS event source parameters: https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-parameters.html
