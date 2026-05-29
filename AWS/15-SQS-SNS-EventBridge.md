# SQS, SNS & EventBridge - Messaging & Event-Driven Architecture

---

## 1. Amazon SQS (Simple Queue Service)

### Overview
- **What:** Fully managed message queuing service. Decouple producers from consumers
- **Types:** Standard Queue and FIFO Queue
- **Message size:** Max 256 KB (use Extended Client Library for up to 2 GB via S3)
- **Retention:** 1 minute to 14 days (default 4 days)
- **Pricing:** $0.40 per 1M Standard requests, $0.50 per 1M FIFO requests

### Standard Queue
- **Throughput:** Unlimited (virtually)
- **Ordering:** Best-effort ordering (NOT guaranteed)
- **Delivery:** At-least-once (messages may be delivered more than once)
- **Use case:** High throughput, order doesn't matter, idempotent consumers

### FIFO Queue
- **Throughput:** 300 msg/sec without batching, 3000 msg/sec with batching (per queue). High throughput FIFO: 70,000 msg/sec
- **Ordering:** Strict order within Message Group ID
- **Delivery:** Exactly-once (deduplication within 5 minutes)
- **Deduplication:** Content-based (SHA-256 hash) or Message Deduplication ID
- **Message Group ID:** Messages in same group processed in order. Different groups processed in parallel
- **Queue name:** Must end with `.fifo`

### Key Concepts

#### Visibility Timeout
- After consumer receives message, it becomes "invisible" for visibility timeout period
- Default: 30 seconds. Range: 0 seconds - 12 hours
- If consumer doesn't delete within timeout → message becomes visible again (retry by another consumer)
- **ChangeMessageVisibility:** Consumer can extend timeout if processing takes longer
- **Problem:** Too short = duplicates. Too long = slow retry on failure

#### Long Polling vs Short Polling
- **Short polling (default):** Returns immediately (even if empty). Costs more (empty receives still charged)
- **Long polling:** Waits up to 20 seconds for messages. Reduces empty receives, saves cost
- Set `WaitTimeSeconds` 1-20 on ReceiveMessage, or set at queue level (ReceiveMessageWaitTimeSeconds)
- **Best practice:** Always use long polling (20 seconds)

#### Dead Letter Queue (DLQ)
- Queue for messages that fail processing repeatedly
- **maxReceiveCount:** After N receives without deletion → message moves to DLQ
- **DLQ Redrive:** Move messages from DLQ back to source queue (for reprocessing after fix)
- **Best practice:** Set maxReceiveCount = 3-5. Monitor DLQ depth with CloudWatch alarm
- FIFO DLQ must also be FIFO

#### Delay Queue
- Postpone delivery of new messages (0 seconds - 15 minutes)
- Set at queue level (DelaySeconds) or per-message (MessageTimer)
- **Use case:** Rate limiting, scheduled processing, give downstream time to prepare

### SQS + Lambda Integration
- Lambda polls SQS (event source mapping)
- Batch size: 1-10,000 messages (FIFO max 10)
- Batch window: 0-300 seconds
- Concurrent: Up to 1000 Lambda instances polling (scales with queue depth)
- On failure: Message returns to queue after visibility timeout
- **Partial batch failure:** Report failed message IDs → only those return to queue (ReportBatchItemFailures)

### SQS Scaling Patterns
```
Target Tracking Scaling:
  SQS queue depth / number of consumers = backlog per instance
  Scale out when > threshold (e.g., > 10 messages per instance)
  
CloudWatch metric: ApproximateNumberOfMessagesVisible
Custom metric: Backlog per instance = visible messages / running tasks
ASG target tracking: maintain backlog per instance at acceptable level
```

---

## 2. Amazon SNS (Simple Notification Service)

### Overview
- **What:** Pub/Sub messaging service. One message → many subscribers
- **Model:** Publisher → Topic → Subscribers (fan-out pattern)
- **Delivery:** Push-based (SNS pushes to subscribers immediately)
- **Throughput:** 30,000,000 messages/sec (soft limit)
- **Pricing:** $0.50 per 1M publishes + delivery charges per protocol

### Topic Types
| | Standard Topic | FIFO Topic |
|--|---|---|
| Throughput | Unlimited | 300 pub/sec (3000 batched) |
| Ordering | No guarantee | Strict (per message group) |
| Deduplication | None | Content or ID based |
| Subscribers | All protocols | SQS FIFO only |
| Use case | Notifications, fan-out | Ordered event processing |

### Subscriber Protocols
| Protocol | Notes |
|----------|-------|
| SQS | Fan-out to queues (most common) |
| Lambda | Serverless processing |
| HTTP/HTTPS | Webhook endpoints |
| Email/Email-JSON | Human notifications |
| SMS | Text messages |
| Kinesis Data Firehose | Direct to S3, Redshift, etc. |
| Platform endpoint (Mobile) | Push notifications (APNs, FCM) |

### Message Filtering
- **Filter Policy:** JSON policy on subscription. Only delivers matching messages
- **Filter on:** Message attributes (key-value pairs on the message)
- **Benefit:** Subscribers only get relevant messages (no code filtering needed)
```json
{
  "order_type": ["premium"],
  "amount": [{"numeric": [">=", 100]}],
  "region": ["us-east-1", "us-west-2"]
}
```
- **Filter policy scope:** MessageAttributes (default) or MessageBody

### SNS Fan-Out Pattern
```
Publisher → SNS Topic → SQS Queue 1 (processing service A)
                      → SQS Queue 2 (processing service B)
                      → Lambda (analytics)
                      → Kinesis Firehose (archive to S3)
```
- **Why SQS behind SNS?** Persistence, retry, independent consumer speed, DLQ for failures
- **S3 Event → SNS → Multiple SQS:** One S3 event, multiple processors

### SNS Message Delivery
- **Retry policy (HTTP/S):** 3 immediate, 2×1sec, 10×10sec, 100×10sec, 35×5min (23 retries over ~1 hour)
- **DLQ:** On final delivery failure, message goes to SQS DLQ (per subscription)
- **Delivery status logging:** Enable for SQS, Lambda, HTTP (logs success/failure to CloudWatch)

---

## 3. Amazon EventBridge

### Overview
- **What:** Serverless event bus for building event-driven architectures
- **Evolution:** CloudWatch Events renamed/upgraded → EventBridge (superset)
- **Model:** Event sources → Event bus → Rules (pattern matching) → Targets
- **Pricing:** $1.00 per 1M events put on custom/partner bus. Default bus: AWS events free

### Event Bus Types
- **Default bus:** Receives events from AWS services (free)
- **Custom bus:** Your application events ($1/M events)
- **Partner bus:** SaaS partner events (Zendesk, Datadog, Shopify, etc.)
- **Cross-account:** Send events to another account's event bus

### Event Structure
```json
{
  "version": "0",
  "id": "unique-id",
  "source": "my.application",
  "detail-type": "OrderPlaced",
  "account": "123456789012",
  "time": "2024-01-15T10:30:00Z",
  "region": "us-east-1",
  "resources": ["arn:aws:..."],
  "detail": {
    "orderId": "12345",
    "amount": 99.99,
    "customer": "user@example.com"
  }
}
```

### Event Rules & Patterns
```json
{
  "source": ["my.application"],
  "detail-type": ["OrderPlaced"],
  "detail": {
    "amount": [{"numeric": [">=", 100]}],
    "status": ["confirmed", "shipped"],
    "region": [{"prefix": "us-"}],
    "name": [{"exists": true}]
  }
}
```
- Pattern types: exact match, prefix, suffix, numeric, exists, anything-but, CIDR
- **Content-based filtering:** Far richer than SNS filter policies

### Targets (35+ supported)
| Category | Targets |
|----------|---------|
| Compute | Lambda, ECS task, Step Functions, Batch |
| Integration | API Gateway, API Destination (HTTP), AppSync |
| Messaging | SQS, SNS, Kinesis, Firehose |
| Automation | SSM, CodePipeline, Inspector |
| Cross-account | Event bus in another account |
| Input transformation | Transform event before delivery to target |

### EventBridge Pipes
- **Point-to-point integration:** Source → [Filter] → [Enrichment] → Target
- **Sources:** SQS, Kinesis, DynamoDB Streams, MSK, MQ
- **Enrichment:** Lambda, Step Functions, API Gateway, API Destination
- **Target:** Any EventBridge target
- **Use case:** Replace Lambda "glue" code between services

### EventBridge Scheduler
- **One-time:** Schedule event at specific time (replace CloudWatch Events scheduled rules)
- **Rate-based:** Every N minutes/hours/days
- **Cron-based:** Complex schedules (cron expression)
- **Features:** Time zones, flexible time window, retry policy, DLQ
- **Scale:** Millions of schedules (vs. CloudWatch Events limited to 300 rules)

### Schema Registry & Discovery
- **Schema Registry:** Central store for event schemas (auto-discovered or manual)
- **Schema Discovery:** Automatically detect and register schemas from events on the bus
- **Code Bindings:** Generate typed code (Java, Python, TypeScript) from schemas
- **Versioning:** Track schema changes over time

### Archive & Replay
- **Archive:** Store all events (or filtered) from an event bus (charged per GB)
- **Replay:** Re-process archived events (for debugging, testing, recovery)
- **Use case:** New service comes online → replay historical events to populate state

---

## 4. Comparison: SQS vs SNS vs EventBridge

| Feature | SQS | SNS | EventBridge |
|---------|-----|-----|-------------|
| Model | Queue (pull) | Pub/Sub (push) | Event bus (push) |
| Consumers | 1 (per message) | Many (fan-out) | Many (rules) |
| Persistence | Yes (14 days) | No (immediate) | Archive (optional) |
| Ordering | FIFO only | FIFO topics | Partial (pipe sources) |
| Filtering | No (app-level) | Attribute filter | Rich content filter |
| Dead letter | Yes | Yes (per subscription) | Yes (per rule/target) |
| Throughput | Unlimited (Standard) | 30M/sec | Burst-limited |
| Latency | ms (long poll) | ms (push) | ~0.5s typical |
| **When** | Decouple, buffer, throttle | Fan-out, notifications | Event-driven, routing, SaaS |

---

## 5. Messaging Patterns

### Fan-Out
```
Event → SNS Topic → SQS Queue A (service A)
                   → SQS Queue B (service B)
                   → Lambda C (analytics)
```

### Fan-Out with Filtering
```
Order Event → SNS Topic
  Subscription 1 (filter: premium orders) → Lambda (priority processing)
  Subscription 2 (filter: all orders) → SQS (standard processing)
  Subscription 3 (no filter) → Firehose → S3 (archive all)
```

### Request-Response (async)
```
Client → Request Queue → Service → Response Queue → Client
         (correlation ID to match request/response)
```

### Saga Pattern (choreography)
```
Order Service → "OrderCreated" event → EventBridge
  → Payment Service (processes payment) → "PaymentCompleted" event
    → Shipping Service (ships order) → "OrderShipped" event
      → Notification Service (notifies customer)
      
Compensation on failure:
  Payment fails → "PaymentFailed" → Order Service cancels order
```

### CQRS with Events
```
Write path: API → Command Handler → DynamoDB → DynamoDB Stream → EventBridge
Read path:  EventBridge → Lambda → Update read model (ElastiCache/RDS)
Query:      API → Read model (fast, denormalized)
```

### Competing Consumers
```
SQS Queue → Multiple consumers (ASG)
Each message processed by exactly ONE consumer
Scale consumers based on queue depth
```

---

## 6. Scenario-Based Interview Questions

### Q1: Design notification system that sends email, SMS, push, and in-app notifications
**Answer:**
```
Notification Request API → SQS (buffer, decouple)
  → Notification Router Lambda:
    - Reads user preferences (DynamoDB)
    - Publishes to SNS Topic with attributes (channel, priority, user_id)
    
SNS Topic subscriptions with filters:
  - Email filter → SQS → Email Service (SES) - batch for digest
  - SMS filter → Direct SMS delivery via SNS
  - Push filter → Platform endpoints (APNs/FCM)
  - In-app filter → SQS → Lambda → WebSocket (API Gateway) or DynamoDB for polling

Delivery tracking:
  - Each channel Lambda writes delivery status to DynamoDB
  - Failed deliveries → DLQ → retry with exponential backoff
  - Unsubscribe: Update preference in DynamoDB, filter prevents delivery
```

### Q2: SQS messages being processed multiple times (duplicates)
**Answer:**
- **Root causes:** Visibility timeout too short, consumer crash before delete, standard queue at-least-once
- **Fix 1:** Increase visibility timeout (2-3× average processing time)
- **Fix 2:** Use FIFO queue (exactly-once, but lower throughput)
- **Fix 3:** Idempotent processing (deduplication table in DynamoDB)
```python
# Idempotency pattern
message_id = event['Records'][0]['messageId']
try:
    # Conditional put - fails if already processed
    table.put_item(
        Item={'message_id': message_id, 'ttl': int(time.time()) + 86400},
        ConditionExpression='attribute_not_exists(message_id)'
    )
    # Process message...
    # Delete from queue
except ConditionalCheckFailedException:
    # Already processed, just delete from queue
    pass
```

### Q3: EventBridge vs SNS for microservices communication?
**Answer:**
| Criteria | Choose EventBridge | Choose SNS |
|----------|-------------------|------------|
| Filtering | Complex content-based filtering needed | Simple attribute filtering sufficient |
| Sources | Need SaaS integrations, schema registry | Only AWS services or custom |
| Throughput | < 10K events/sec typical | > 100K events/sec needed |
| Cost | $1/M events (publish cost) | $0.50/M publishes |
| Latency | ~0.5s acceptable | Need sub-100ms |
| Evolution | Schema discovery, versioning important | Stable, known schemas |
| **Verdict** | Modern event-driven, evolving schemas | High-throughput fan-out, low latency |

### Q4: Design order processing system handling 10K orders/minute during flash sales
**Answer:**
```
Normal: 100 orders/min. Flash sale: 10,000 orders/min (100× spike)

Architecture:
  API Gateway → Lambda → SQS (Standard, buffer the spike)
    → ECS Service (auto-scaled based on queue depth)
      → Process order → DynamoDB (write order)
      → EventBridge ("OrderPlaced" event)
        → Inventory Service (SQS + Lambda)
        → Payment Service (SQS + Lambda) 
        → Email Service (SQS + Lambda)

Why SQS buffer?
  - Absorbs 100× spike without dropping orders
  - Downstream processes at sustainable rate
  - No data loss during peak

Scaling:
  - API Gateway + Lambda: handles burst immediately
  - SQS: unlimited ingestion
  - ECS: Target tracking on ApproximateNumberOfMessagesVisible / RunningTaskCount
  - Scale target: < 5 messages per task (process within seconds)
  
Failure handling:
  - DLQ on each queue (max 3 retries)
  - Saga compensation: Payment fails → EventBridge → Order Service reverses
  - Monitoring: DLQ depth alarm → PagerDuty
```

### Q5: Migrate from synchronous microservices to event-driven architecture
**Answer:**
**Phase 1: Identify boundaries**
- Map synchronous call chains (A → B → C → D)
- Identify which calls need immediate response vs fire-and-forget
- Classify: Command (needs response) vs Event (notification)

**Phase 2: Introduce event bus**
- Deploy EventBridge custom bus
- Services publish events AFTER completing their work (dual-write initially)
- New consumers subscribe to events

**Phase 3: Strangler fig pattern**
- For each sync call:
  - If response needed: Keep sync OR use request-response queue pattern
  - If fire-and-forget: Replace with event publication
  - If ordering needed: Use FIFO SQS behind EventBridge rule

**Phase 4: Eventual consistency**
- Replace strong consistency (sync) with eventual consistency (event)
- Add saga pattern for distributed transactions
- Implement compensation logic for failures

**Pitfalls:**
- Event ordering (use correlation IDs, sequence numbers)
- Exactly-once processing (idempotent consumers)
- Debugging (distributed tracing with X-Ray, correlation IDs)
- Schema evolution (EventBridge schema registry, versioning)

