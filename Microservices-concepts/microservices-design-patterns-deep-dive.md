# Microservices Design Patterns Deep Dive

This note explains core microservice design patterns in depth, with real-world examples and production concerns. The focus is not just "what the pattern is", but when to use it, how it fails, how to operate it, and how to combine patterns safely.

Core patterns covered:

- Saga pattern
- Compensating transactions
- Transactional outbox pattern
- Event sourcing
- Event storming
- CQRS
- Two-phase commit and three-phase commit
- Other important microservice patterns used in production systems

---

## 1. Microservices Pattern Mental Model

Microservices are not just small services. A microservice architecture is a system where business capabilities are owned by independently deployable services, each with clear data ownership and operational responsibility.

The hardest problems are not HTTP routing or Docker. The hardest problems are:

- Distributed data consistency
- Failure handling across service boundaries
- Reliable messaging
- Schema and contract evolution
- Observability across many hops
- Operational ownership
- Safe deployment and rollback
- Avoiding accidental distributed monoliths

A useful mental model:

```text
Microservice architecture = local autonomy + distributed coordination

Local autonomy:
  - service owns its domain model
  - service owns its data
  - service can be deployed independently
  - service can fail independently

Distributed coordination:
  - workflows cross services
  - data is duplicated into read models
  - messages can be delayed, duplicated, reordered, or lost if not designed well
  - business consistency is often eventual, not immediate
```

Most microservice patterns exist because one simple thing becomes hard once data and behavior are split across services:

```text
How do we keep the business process correct when no single database transaction covers everything?
```

---

## 2. Pattern Selection Map

| Problem | Common Pattern | Main Trade-off |
|---------|----------------|----------------|
| One business transaction spans many services | Saga | Eventual consistency instead of one ACID transaction |
| Publish an event reliably after a DB update | Transactional outbox | Extra table and relay process |
| Consumers need duplicate protection | Idempotent consumer / inbox | Extra state for deduplication |
| Need complete history and audit trail | Event sourcing | More complex reads, replay, and schema evolution |
| Read queries differ from write model | CQRS | Extra read models and eventual consistency |
| Need to discover domain boundaries | Event storming | Requires workshop discipline and domain experts |
| Need atomic commit across resources | 2PC / 3PC | Blocking, coupling, poor availability at scale |
| Need migrate legacy system gradually | Strangler fig | Temporary routing and duplication complexity |
| Need isolate from legacy or external model | Anti-corruption layer | Translation code and model mapping overhead |
| Need client-specific API shape | BFF | More API services to own |
| Need service-to-service resilience | Circuit breaker / retry / timeout / bulkhead | Correct tuning is non-trivial |
| Need separate service databases | Database per service | Harder joins and reporting |
| Need aggregate data from many services | API composition / CQRS read model | Latency or staleness trade-off |

---

## 3. Foundation Principles Before Patterns

### 3.1 Own Data by Service

The most important rule:

```text
Only one service writes a piece of business data.
```

Example:

```text
Order Service owns:
  - order id
  - order state
  - order lines
  - order total

Payment Service owns:
  - payment authorization
  - capture status
  - refund status
  - payment provider references

Inventory Service owns:
  - available stock
  - reservations
  - warehouse allocation
```

Other services may keep copies for reads, but those copies are projections, caches, or read models. They are not the source of truth.

### 3.2 Prefer Business Consistency Over Technical Atomicity

In a monolith, a checkout operation might be one database transaction:

```text
BEGIN;
insert order;
reserve inventory;
charge payment;
update shipment;
COMMIT;
```

In microservices, this is dangerous because each operation belongs to a different service and often a different database. Instead of forcing one technical transaction across everything, define business states:

```text
OrderCreated
InventoryReserved
PaymentAuthorized
ShipmentRequested
OrderConfirmed
OrderCancelled
```

The system becomes correct because every state transition is explicit, observable, retryable, and recoverable.

### 3.3 Assume Messages Are At-Least-Once

In production, a message can be:

- Delivered more than once
- Delivered late
- Delivered out of order
- Processed successfully but acknowledged unsuccessfully
- Published successfully but the producer crashes before recording that fact
- Consumed successfully but the consumer crashes before committing its database update

Therefore, production event-driven systems need:

- Idempotency keys
- Deduplication
- Retries with backoff
- Dead-letter queues
- Poison message handling
- Event schema versioning
- Observability for lag and failure

---

## 4. Saga Pattern

## 4.1 What Is a Saga?

A saga is a sequence of local transactions that together implement a larger business transaction across multiple services.

Each service updates its own database in a local ACID transaction. After that, the saga moves to the next step by sending a command or publishing an event.

If a later step fails, the saga executes compensating actions to undo or neutralize earlier successful steps.

```text
Distributed transaction goal:
  One transaction commits everything or rolls back everything.

Saga goal:
  Each service commits locally.
  The overall process eventually reaches a valid business outcome.
```

Example: ecommerce checkout.

```text
1. Order Service creates order in PENDING state.
2. Inventory Service reserves stock.
3. Payment Service authorizes payment.
4. Shipping Service creates shipment.
5. Order Service confirms order.

If payment fails:
  - Inventory reservation is released.
  - Order is marked CANCELLED.
```

### 4.2 Why Saga Exists

Sagas solve the problem of business workflows where:

- Multiple services must participate.
- Each service owns its own database.
- A single global ACID transaction is undesirable or impossible.
- The business can tolerate temporary inconsistency.
- Failures must be handled explicitly.

Common examples:

- Ecommerce checkout
- Travel booking
- Food delivery order lifecycle
- Ride booking
- Loan origination
- Insurance claim processing
- Subscription activation
- Marketplace payout
- Account onboarding with KYC

### 4.3 Saga Is Not a Technical Rollback

A database rollback restores old database state before commit. A saga compensation is a new business action.

Example:

```text
Payment captured -> compensation is refund payment.
Inventory reserved -> compensation is release reservation.
Email sent -> compensation is send correction email, not unsend email.
Shipment created -> compensation may be cancel shipment if not picked up.
Shipment picked up -> compensation may be return merchandise process.
```

This distinction is critical. Some actions are irreversible. A saga does not magically undo the past; it drives the system to a valid next state.

---

## 4.4 Saga Types

### Choreography-Based Saga

In choreography, services react to events from each other. There is no central workflow controller.

```text
Order Service
  -> publishes OrderCreated

Inventory Service
  -> consumes OrderCreated
  -> reserves stock
  -> publishes InventoryReserved

Payment Service
  -> consumes InventoryReserved
  -> authorizes payment
  -> publishes PaymentAuthorized

Shipping Service
  -> consumes PaymentAuthorized
  -> creates shipment
  -> publishes ShipmentCreated

Order Service
  -> consumes ShipmentCreated
  -> marks order CONFIRMED
```

Failure flow:

```text
Payment Service
  -> publishes PaymentFailed

Inventory Service
  -> consumes PaymentFailed
  -> releases reservation
  -> publishes InventoryReleased

Order Service
  -> consumes PaymentFailed or InventoryReleased
  -> marks order CANCELLED
```

Benefits:

- Simple for small workflows.
- No single orchestrator service.
- Services are loosely coupled through events.
- Good for natural domain event propagation.

Problems:

- Flow is hard to see because logic is distributed.
- Adding a new step can affect many services.
- Debugging requires tracing events across services.
- Risk of cyclic event dependencies.
- Harder to enforce timeouts and global policies.

Use choreography when:

- Workflow is simple.
- Number of participants is small.
- Events are natural domain facts.
- There is no complex branching.
- Teams can maintain strong event contracts.

### Orchestration-Based Saga

In orchestration, a saga orchestrator explicitly controls the workflow.

```text
Checkout Saga Orchestrator
  -> command: CreateOrder
  <- event: OrderCreated

  -> command: ReserveInventory
  <- event: InventoryReserved

  -> command: AuthorizePayment
  <- event: PaymentAuthorized

  -> command: CreateShipment
  <- event: ShipmentCreated

  -> command: ConfirmOrder
  <- event: OrderConfirmed
```

Failure flow:

```text
Checkout Saga Orchestrator
  -> AuthorizePayment fails
  -> command: ReleaseInventory
  -> command: CancelOrder
```

Benefits:

- Workflow is explicit.
- Easier to handle branching, retries, and timeouts.
- Easier to monitor one saga instance state.
- Better for long-running business processes.
- Easier to test end-to-end workflow logic.

Problems:

- Orchestrator can become too smart.
- Services may become anemic command executors.
- Coupling shifts into the orchestrator.
- Orchestrator state must be highly reliable.

Use orchestration when:

- Workflow has many steps.
- Failure handling is complex.
- Business needs clear process visibility.
- Timeouts and manual intervention are required.
- State machine semantics matter.

### Choreography vs Orchestration

| Dimension | Choreography | Orchestration |
|-----------|--------------|---------------|
| Control | Distributed | Central workflow controller |
| Visibility | Harder | Easier |
| Coupling | Event coupling | Command coupling |
| Best for | Simple flows | Complex flows |
| Failure handling | Spread across services | Centralized |
| Debugging | Trace event chain | Inspect saga state |
| Risk | Event spaghetti | God orchestrator |

Production rule:

```text
Start with choreography only when the process is genuinely simple.
Use orchestration when the workflow itself is a business concept.
```

---

## 4.5 Saga State Machine

A production saga should usually be modeled as a state machine.

Example checkout saga states:

```text
STARTED
ORDER_CREATED
INVENTORY_RESERVED
PAYMENT_AUTHORIZED
SHIPMENT_CREATED
COMPLETED
CANCELLING
INVENTORY_RELEASED
PAYMENT_VOIDED
CANCELLED
FAILED_REQUIRES_MANUAL_REVIEW
```

Every transition should be explicit:

| Current State | Event | Next State | Action |
|---------------|-------|------------|--------|
| STARTED | StartCheckout | ORDER_CREATING | Create order |
| ORDER_CREATING | OrderCreated | INVENTORY_RESERVING | Reserve inventory |
| INVENTORY_RESERVING | InventoryReserved | PAYMENT_AUTHORIZING | Authorize payment |
| PAYMENT_AUTHORIZING | PaymentAuthorized | SHIPMENT_CREATING | Create shipment |
| PAYMENT_AUTHORIZING | PaymentFailed | CANCELLING | Release inventory |
| CANCELLING | InventoryReleased | CANCELLED | Cancel order |

This avoids hidden workflow behavior in scattered if-else blocks.

### Saga Instance Data

A saga instance should store enough information to resume after failure.

```text
saga_id
business_key             // order_id, booking_id, claim_id
current_state
version                  // optimistic concurrency control
started_at
updated_at
deadline_at
last_error
retry_count
completed_steps
compensation_steps
correlation_id
```

Never rely only on in-memory workflow state. A saga may run for seconds, minutes, days, or weeks.

---

## 4.6 How to Do Compensation in Saga

Compensation is the most important part of saga design. A weak compensation design creates data corruption, customer-impacting failures, and manual cleanup.

### Step 1: Classify Every Saga Step

Every step should be classified as one of these:

| Step Type | Meaning | Example |
|-----------|---------|---------|
| Compensatable | Can be semantically undone | Reserve inventory -> release inventory |
| Retriable | Can be retried until success | Send command to internal service |
| Pivot | Point after which saga must complete forward | Capture payment, issue ticket, submit order to exchange |
| Irreversible | Cannot be undone, only corrected | Email sent, SMS sent, package delivered |

Classic saga design separates the flow into:

```text
Compensatable steps -> Pivot step -> Retriable steps
```

Example:

```text
1. Create pending order       compensatable
2. Reserve inventory          compensatable
3. Authorize payment          compensatable by voiding authorization
4. Capture payment            pivot
5. Request shipment           retriable after payment capture
6. Confirm order              retriable
```

After the pivot, you usually avoid cancellation and prefer forward recovery.

### Step 2: Define a Compensation for Every Compensatable Step

Do not write:

```text
If checkout fails, rollback checkout.
```

Write concrete compensations:

| Successful Step | Compensation |
|-----------------|--------------|
| Create pending order | Mark order CANCELLED with reason |
| Reserve inventory | Release reservation id |
| Authorize payment | Void authorization id |
| Apply coupon | Restore coupon usage or mark usage cancelled |
| Create loyalty hold | Release loyalty points hold |
| Create shipment label | Cancel label if carrier allows |
| Send confirmation email | Send cancellation/correction email |

Compensation must use stable identifiers from the original step:

```text
reserve inventory -> reservation_id
authorize payment -> payment_authorization_id
create shipment -> shipment_id
```

Avoid compensating by re-querying unstable business state. Store the exact IDs needed to compensate.

### Step 3: Make Compensation Idempotent

Compensation commands can be retried. Therefore, they must be safe to run more than once.

Bad:

```text
release 2 units of SKU-123
```

If retried twice, stock may be over-released.

Good:

```text
release reservation RES-789
```

Inventory Service can store:

```text
reservation_id = RES-789
status = RELEASED
```

If the release command arrives again, it returns success without changing stock again.

Production rule:

```text
Compensate using operation IDs, reservation IDs, authorization IDs, and idempotency keys.
Never compensate with blind arithmetic.
```

### Step 4: Store Compensation Progress

A compensation flow can also fail halfway.

Example:

```text
Payment failed.
Saga begins compensation:
  - release inventory succeeded
  - cancel order failed because Order Service is down
```

The saga must store:

```text
compensation_started_at
compensation_step = CANCEL_ORDER
inventory_release_status = SUCCEEDED
order_cancel_status = PENDING
last_error = Order Service timeout
next_retry_at
```

Without durable compensation progress, a crash can leave the system in an unknown state.

### Step 5: Prefer Reservations Over Direct Mutation

A reservation is easier to compensate than a completed business action.

Inventory example:

```text
Bad:
  Decrease available stock immediately.

Better:
  Create reservation with expiration.
  Confirm reservation only when order completes.
  Release reservation on failure or timeout.
```

Payment example:

```text
Better:
  Authorize payment first.
  Capture payment only after inventory and fraud checks pass.

Harder:
  Capture payment immediately.
  Refund later if anything fails.
```

Shipping example:

```text
Better:
  Create shipment request in PENDING state.
  Buy label only after payment is safe.

Harder:
  Buy label immediately.
  Cancel label later, if carrier allows.
```

### Step 6: Use Timeouts and Expiration

Sagas cannot wait forever.

Example:

```text
Inventory reservation TTL = 15 minutes
Payment authorization TTL = provider-specific, often hours or days
Checkout saga deadline = 10 minutes
```

If the saga times out:

```text
START compensation.
Release inventory.
Void payment authorization.
Cancel pending order.
Notify customer if needed.
```

Timeouts must be business-aware. A hotel booking hold may last 10 minutes. A loan application may last 30 days.

### Step 7: Accept That Some Compensation Is Forward Correction

Not all actions can be undone.

| Action | Realistic Compensation |
|--------|------------------------|
| Email sent | Send correction email |
| SMS sent | Send follow-up message |
| Payment captured | Refund |
| Package shipped | Return workflow |
| Account created | Disable account |
| KYC submitted to vendor | Mark application cancelled locally and ignore callback |
| Ticket issued | Cancel ticket if allowed, otherwise issue credit |

Production systems should model these states explicitly:

```text
REFUND_PENDING
RETURN_REQUIRED
CANCELLATION_REQUESTED
MANUAL_REVIEW_REQUIRED
```

### Step 8: Design Manual Recovery

Some failures cannot be resolved automatically.

Examples:

- Payment captured, but shipment provider rejects the shipment permanently.
- Inventory reservation release keeps failing because inventory record is corrupt.
- Partner API accepted a request but never returns a final status.
- Refund provider says refund is pending for 48 hours.

Production saga systems need:

- Manual review queue
- Admin actions with audit trail
- Runbooks
- Safe replay controls
- Ability to retry a specific step
- Ability to force a terminal state with reason
- Customer support visibility

### Step 9: Use a Compensation Matrix

Before implementing a saga, create a table like this:

| Step | Local Transaction | Success Event | Failure Event | Compensation | Idempotency Key | Timeout |
|------|-------------------|---------------|---------------|--------------|-----------------|---------|
| Create order | Insert PENDING order | OrderCreated | OrderCreateFailed | Cancel order | checkout_id | 30 sec |
| Reserve inventory | Create reservation | InventoryReserved | InventoryRejected | Release reservation | reservation_id | 2 min |
| Authorize payment | Create auth | PaymentAuthorized | PaymentDeclined | Void authorization | payment_auth_id | 2 min |
| Create shipment | Create shipment request | ShipmentCreated | ShipmentRejected | Cancel shipment | shipment_id | 2 min |
| Confirm order | Mark CONFIRMED | OrderConfirmed | OrderConfirmFailed | Forward retry | order_id | retry forever with alert |

This table exposes missing compensation before production incidents do.

---

## 4.7 Saga Production Concerns

### Idempotency

Every command handler should accept an idempotency key.

```text
ReserveInventory(order_id=O-100, saga_id=S-500, idempotency_key=S-500.reserve_inventory)
```

If the same command is received twice, the service returns the original result.

### Ordering

If events can arrive out of order, include:

- Aggregate version
- Event timestamp
- Causal sequence number
- Saga step number

Do not assume broker delivery order is enough unless you control partitioning and keys carefully.

### Observability

For every saga instance, you need:

- Correlation ID
- Saga ID
- Business key
- Current state
- Last successful step
- Last failed step
- Retry count
- Compensation status
- Event lag
- End-to-end duration

Useful metrics:

```text
saga_started_total
saga_completed_total
saga_cancelled_total
saga_failed_total
saga_compensation_started_total
saga_compensation_failed_total
saga_duration_seconds
saga_step_retry_total
saga_stuck_instances
```

### Testing

Test more than the happy path:

- Payment fails after inventory succeeds.
- Inventory succeeds but event publish is delayed.
- Duplicate InventoryReserved event arrives.
- PaymentAuthorized arrives after saga timeout.
- Compensation command is delivered twice.
- Orchestrator crashes after sending command but before updating state.
- Consumer processes event but crashes before ack.
- Service returns timeout but actually completed the operation.

### Common Saga Mistakes

- Treating compensation as database rollback.
- Not storing IDs needed for compensation.
- No idempotency keys.
- No timeout strategy.
- No manual recovery path.
- Publishing events outside the local transaction without outbox.
- Letting choreography become invisible event spaghetti.
- Compensating irreversible side effects as if they never happened.
- Not defining terminal states.

---

## 5. Transactional Outbox Pattern

## 5.1 What Problem Does Outbox Solve?

A service often needs to update its database and publish an event.

Example:

```text
Order Service:
  1. Insert order into database.
  2. Publish OrderCreated event to Kafka/SNS/RabbitMQ/SQS.
```

The dangerous version:

```text
BEGIN;
insert order;
COMMIT;

publish OrderCreated;
```

Failure cases:

| Failure | Result |
|---------|--------|
| DB commit succeeds, service crashes before publish | Order exists but no event |
| Publish succeeds, DB commit fails | Event says order exists but DB does not |
| Publish succeeds, service times out and retries | Duplicate event |

The outbox pattern solves this by storing the event in the same database transaction as the business change.

```text
BEGIN;
insert order;
insert outbox event OrderCreated;
COMMIT;

Outbox relay later publishes event.
```

The database transaction atomically commits:

- Business state
- Event-to-be-published

---

## 5.2 Outbox Flow

```text
Command received
  |
  v
Service local transaction
  |
  +-- update business table
  |
  +-- insert row into outbox table
  |
  v
Commit
  |
  v
Outbox relay reads unpublished rows
  |
  v
Publishes to message broker
  |
  v
Marks outbox row as published
```

Example table:

```sql
CREATE TABLE outbox_events (
  id              UUID PRIMARY KEY,
  aggregate_type  TEXT NOT NULL,
  aggregate_id    TEXT NOT NULL,
  event_type      TEXT NOT NULL,
  event_version   INT NOT NULL,
  payload         JSONB NOT NULL,
  headers         JSONB NOT NULL,
  status          TEXT NOT NULL DEFAULT 'PENDING',
  created_at      TIMESTAMP NOT NULL,
  published_at    TIMESTAMP NULL,
  retry_count     INT NOT NULL DEFAULT 0,
  next_retry_at   TIMESTAMP NULL,
  last_error      TEXT NULL
);
```

Common headers:

```text
event_id
correlation_id
causation_id
trace_id
producer_service
schema_version
occurred_at
idempotency_key
```

---

## 5.3 Outbox Relay Implementations

### Polling Publisher

A background worker periodically queries:

```sql
SELECT *
FROM outbox_events
WHERE status = 'PENDING'
ORDER BY created_at
LIMIT 100;
```

Then it publishes and marks rows as published.

Benefits:

- Simple.
- Works with most databases.
- Easy to understand and operate.

Problems:

- Adds polling load.
- Latency depends on polling interval.
- Requires careful locking for multiple relay workers.

Use row locking where supported:

```sql
SELECT *
FROM outbox_events
WHERE status = 'PENDING'
ORDER BY created_at
LIMIT 100
FOR UPDATE SKIP LOCKED;
```

### Change Data Capture Relay

CDC reads database transaction logs and publishes outbox rows.

Example:

```text
Postgres WAL / MySQL binlog
  -> Debezium
  -> Kafka topic
```

Benefits:

- Lower application polling load.
- Preserves transaction log ordering.
- Good for high throughput.

Problems:

- More infrastructure.
- Requires CDC operational knowledge.
- Schema changes need discipline.
- Replays need careful handling.

### Broker Transaction Integration

Some platforms support transactions between consume-process-produce within the broker ecosystem. This can help in stream processing but usually does not atomically cover the application database and broker together. Outbox is still the common general-purpose solution for database plus broker consistency.

---

## 5.4 Outbox Delivery Guarantees

Outbox usually gives:

```text
At-least-once publishing
```

It does not automatically give exactly-once end-to-end behavior.

Why duplicates still happen:

```text
Relay publishes event successfully.
Relay crashes before marking row as published.
Relay restarts and publishes the same event again.
```

Therefore consumers must be idempotent.

Consumer deduplication table:

```sql
CREATE TABLE processed_messages (
  consumer_name TEXT NOT NULL,
  message_id    UUID NOT NULL,
  processed_at  TIMESTAMP NOT NULL,
  PRIMARY KEY (consumer_name, message_id)
);
```

Consumer flow:

```text
Receive event
  |
  v
Start DB transaction
  |
  +-- insert message_id into processed_messages
  |     if duplicate, skip business processing
  |
  +-- apply business update
  |
  v
Commit
```

This combination is often called:

```text
Transactional outbox + idempotent consumer
```

If the consumer also stores incoming messages before processing, that is often called the inbox pattern.

---

## 5.5 Outbox Ordering

Ordering is subtle.

If one aggregate publishes events:

```text
OrderCreated
OrderConfirmed
OrderCancelled
```

Consumers should not process `OrderConfirmed` before `OrderCreated`.

Production practices:

- Include aggregate ID and version.
- Publish events for the same aggregate to the same broker partition.
- Use ordering by database commit order where possible.
- Consumers should reject, buffer, or safely ignore impossible state transitions.
- Design events so consumers can be idempotent and state-aware.

Example event:

```json
{
  "event_id": "7c7a6c62",
  "event_type": "OrderConfirmed",
  "aggregate_type": "Order",
  "aggregate_id": "O-100",
  "aggregate_version": 5,
  "occurred_at": "2026-05-24T10:00:00Z"
}
```

Consumer logic:

```text
If event version <= last_processed_version:
  duplicate or old event, ignore

If event version == last_processed_version + 1:
  process

If event version > last_processed_version + 1:
  missing event, retry later or load current state
```

---

## 5.6 Outbox Cleanup and Operations

Outbox tables can grow quickly.

Production requirements:

- Index by status and created_at.
- Archive or delete published rows after retention.
- Keep failed rows for debugging.
- Alert on pending row age.
- Alert on retry count.
- Track relay lag.
- Track publish success and failure rate.
- Support replay by event ID or time range.
- Protect against poison events.

Useful metrics:

```text
outbox_pending_count
outbox_oldest_pending_age_seconds
outbox_publish_success_total
outbox_publish_failure_total
outbox_retry_total
outbox_dead_letter_total
outbox_relay_lag_seconds
```

Common mistakes:

- Publishing directly after DB commit without outbox.
- Marking published before broker ack.
- Deleting rows immediately without retention.
- Not making consumers idempotent.
- Assuming outbox gives exactly-once business behavior.
- No backpressure when broker is down.
- No way to replay selected events.

---

## 5.7 Real-World Outbox Example

Food delivery order accepted by restaurant:

```text
Restaurant Service local transaction:
  - update order_acceptance status = ACCEPTED
  - insert outbox event RestaurantAcceptedOrder

Outbox relay:
  - publishes RestaurantAcceptedOrder to Kafka

Delivery Dispatch Service:
  - consumes event
  - starts courier assignment

Customer Notification Service:
  - consumes event
  - sends push notification
```

If Restaurant Service crashes after DB commit, the outbox row remains. The relay publishes later. No accepted order is silently lost.

---

## 6. Event Sourcing

## 6.1 What Is Event Sourcing?

Event sourcing stores state changes as an append-only sequence of events. Current state is derived by replaying those events.

Traditional persistence:

```text
orders table stores current row:
  order_id = O-100
  status = CONFIRMED
  total = 1499
```

Event sourcing:

```text
OrderCreated(order_id=O-100, total=1499)
InventoryReserved(order_id=O-100)
PaymentAuthorized(order_id=O-100)
OrderConfirmed(order_id=O-100)
```

Current state is:

```text
replay events -> build Order aggregate -> status = CONFIRMED
```

Important distinction:

```text
Event-driven architecture:
  Services communicate with events.

Event sourcing:
  Events are the source of truth for state.
```

You can use event-driven architecture without event sourcing.

---

## 6.2 Event Store Model

Typical event store row:

```text
event_id
stream_id              // Order-O-100
stream_type            // Order
stream_version         // 1, 2, 3...
event_type
event_version
payload
metadata
occurred_at
recorded_at
```

Stream example:

```text
stream_id = Account-A-123

1. AccountOpened
2. MoneyDeposited
3. MoneyWithdrawn
4. CardBlocked
5. AccountClosed
```

The aggregate is reconstructed:

```text
state = empty
for event in stream:
  state.apply(event)
```

### Optimistic Concurrency

Event sourcing commonly uses expected version checks.

```text
Command: WithdrawMoney(account=A-123, amount=100)
Loaded stream version: 7
Append event with expected_version = 7

If current stream version is still 7:
  append MoneyWithdrawn as version 8

If current stream version is now 8:
  concurrency conflict, reload and re-evaluate command
```

This prevents lost updates.

---

## 6.3 When Event Sourcing Is Useful

Use event sourcing when:

- Audit history is a core requirement.
- Business wants to know why state changed, not just current state.
- You need temporal queries or reconstruction.
- State transitions are complex and meaningful.
- You need strong traceability, such as finance, ledger, compliance, orders, claims.
- You want to rebuild read models from a source-of-truth event log.

Good use cases:

- Banking ledger
- Wallet balance
- Trading orders
- Insurance claim lifecycle
- Shipment tracking
- Subscription billing
- Workflow engines
- Audit-heavy healthcare or compliance systems

Weak use cases:

- Simple CRUD admin tables
- Low-value reference data
- Data with frequent mass updates
- Systems where event schema evolution cannot be managed
- Teams without operational maturity for replay and projections

---

## 6.4 Event Sourcing and Read Models

Event-sourced writes are usually not queried directly for UI screens. Instead, projections build read models.

```text
Event Store
  -> OrderSummaryProjection
      -> orders_read_model

  -> CustomerOrderHistoryProjection
      -> customer_order_history_read_model

  -> AnalyticsProjection
      -> warehouse / lake
```

Example projection:

```text
OrderCreated
  -> insert read row with status PENDING

PaymentAuthorized
  -> update payment_status = AUTHORIZED

OrderConfirmed
  -> update order_status = CONFIRMED
```

Projection lag is normal:

```text
Write accepted at T1.
Read model updated at T1 + small delay.
```

The UI must handle this:

- Show "processing" state.
- Read from write model for immediate confirmation when needed.
- Use polling or WebSocket updates.
- Communicate eventual consistency to users only when necessary.

---

## 6.5 Snapshots

If a stream has many events, replay may become slow.

Snapshot:

```text
After event version 10,000:
  store current aggregate state snapshot.

To load:
  load snapshot at version 10,000
  replay events 10,001 onward
```

Production concerns:

- Snapshot format must be versioned.
- Snapshots are derived data, not source of truth.
- You must be able to rebuild snapshots from events.
- Snapshot creation should not block writes.

---

## 6.6 Event Versioning and Schema Evolution

Events are historical facts. Avoid changing old event meaning.

Bad:

```text
PaymentAuthorized.amount changes from cents to rupees without version change.
```

Good:

```text
PaymentAuthorized.v1:
  amount_cents

PaymentAuthorized.v2:
  amount_minor_units
  currency
```

Strategies:

- Add optional fields.
- Use event version numbers.
- Upcast old events during read.
- Keep old handlers until old events are no longer needed.
- Avoid removing fields used by projections.
- Avoid reusing event names for different meanings.

### Upcasting

Upcasting transforms old event shape into current shape during read.

```text
PaymentAuthorized.v1
  amount_cents = 149900

Upcast to v2
  amount_minor_units = 149900
  currency = "INR"
```

---

## 6.7 Event Sourcing Production Concerns

### Privacy and Deletion

Event stores are append-only, but privacy laws may require deletion or anonymization.

Design options:

- Avoid putting sensitive data directly in events.
- Store sensitive data by reference in a separate privacy-controlled store.
- Encrypt sensitive fields with per-user keys and destroy keys when deletion is required.
- Append redaction events where legally acceptable.
- Keep retention policies explicit.

### Rebuilds

Rebuilding projections can be expensive.

You need:

- Replay tooling.
- Backpressure controls.
- Ability to rebuild one projection without affecting production writes.
- Ability to pause and resume replay.
- Metrics for projection lag.
- Versioned projection code.

### Event Immutability

Do not update historical events casually. If correction is required, append a correcting event.

Example:

```text
Wrong:
  Modify MoneyDeposited amount from 100 to 10.

Right:
  Append DepositCorrectionApplied(amount_delta=-90, reason=...)
```

### Testing

Event-sourced aggregates are testable with given-when-then style.

```text
Given:
  AccountOpened(balance=0)
  MoneyDeposited(amount=100)

When:
  WithdrawMoney(amount=30)

Then:
  MoneyWithdrawn(amount=30)
```

Also test:

- Replaying old event versions.
- Projection rebuild correctness.
- Duplicate event handling.
- Out-of-order projection events.
- Snapshot compatibility.

---

## 6.8 Real-World Event Sourcing Example: Wallet Ledger

A wallet system must explain every balance change.

Events:

```text
WalletCreated
FundsAdded
PaymentReserved
PaymentCaptured
PaymentReservationReleased
RefundCredited
AdjustmentApplied
WalletBlocked
WalletUnblocked
```

Current balance is derived from events. The ledger can answer:

- What is the current balance?
- What was the balance yesterday?
- Why did the balance change?
- Which transaction caused this debit?
- Can we rebuild customer statements?

Production design:

```text
Command API:
  AddFunds
  ReservePayment
  CapturePayment
  ReleaseReservation

Event Store:
  append-only wallet streams

Read Models:
  wallet_current_balance
  wallet_statement
  fraud_monitoring_projection
  customer_support_timeline
```

This is a strong event sourcing use case because auditability is a core business requirement.

---

## 7. Event Storming

## 7.1 What Is Event Storming?

Event storming is a collaborative modeling technique for understanding a business domain through domain events.

It is not an event broker design session. It is a domain discovery workshop.

Core idea:

```text
Start with facts that happened in the business.
Use those facts to discover commands, policies, aggregates, bounded contexts, and service boundaries.
```

Examples of domain events:

```text
OrderPlaced
PaymentAuthorized
InventoryReserved
ShipmentDispatched
DeliveryFailed
RefundIssued
```

Events are named in past tense because they represent facts.

---

## 7.2 Why Event Storming Matters for Microservices

Many microservice failures start with bad boundaries:

- Services split by technical layers instead of business capabilities.
- Shared databases.
- Chatty synchronous calls.
- Teams constantly waiting on each other.
- No clear owner for business rules.

Event storming helps discover boundaries before implementation.

It reveals:

- Important business events.
- Commands that trigger events.
- Policies and rules.
- External systems.
- Hot spots and ambiguity.
- Aggregates and invariants.
- Bounded contexts.
- Candidate microservices.

---

## 7.3 Event Storming Building Blocks

Common sticky-note colors vary by team, but the concepts are stable.

| Concept | Meaning | Example |
|---------|---------|---------|
| Domain event | Something important happened | OrderPlaced |
| Command | Request to do something | PlaceOrder |
| Actor | Person/system initiating command | Customer |
| Policy | Rule reacting to event | When PaymentAuthorized, reserve stock |
| Aggregate | Consistency boundary | Order |
| Read model | Information needed for decision | ProductAvailabilityView |
| External system | Third-party or legacy dependency | Payment Gateway |
| Hot spot | Risk, uncertainty, conflict | Can inventory be oversold? |

---

## 7.4 Event Storming Process

### Step 1: Big Picture Event Storming

Ask domain experts:

```text
What important things happen in this business process?
```

Write events in timeline order.

Example ecommerce flow:

```text
CartCreated
ItemAddedToCart
CheckoutStarted
OrderPlaced
InventoryReserved
PaymentAuthorized
OrderConfirmed
ShipmentPacked
ShipmentDispatched
ShipmentDelivered
ReturnRequested
RefundIssued
```

### Step 2: Find Commands

For each event, ask:

```text
What caused this event?
```

Examples:

```text
PlaceOrder -> OrderPlaced
ReserveInventory -> InventoryReserved
AuthorizePayment -> PaymentAuthorized
DispatchShipment -> ShipmentDispatched
```

### Step 3: Find Policies

Policies connect events to commands.

```text
When OrderPlaced:
  ReserveInventory

When InventoryReserved:
  AuthorizePayment

When PaymentAuthorized:
  ConfirmOrder

When PaymentFailed:
  CancelOrder
  ReleaseInventory
```

This is where sagas often emerge.

### Step 4: Find Aggregates

Aggregates protect invariants.

Example:

```text
Order aggregate:
  - cannot confirm before payment authorization
  - cannot cancel after delivery
  - total must match order lines

Inventory aggregate:
  - cannot reserve more than available stock
  - reservation expires if not confirmed

Payment aggregate:
  - cannot capture more than authorized amount
```

### Step 5: Find Bounded Contexts

Group related language and rules.

```text
Ordering Context:
  OrderPlaced, OrderConfirmed, OrderCancelled

Inventory Context:
  InventoryReserved, ReservationReleased, StockAdjusted

Payment Context:
  PaymentAuthorized, PaymentCaptured, RefundIssued

Shipping Context:
  ShipmentCreated, ShipmentDispatched, ShipmentDelivered
```

These contexts are stronger microservice candidates than CRUD entity names.

---

## 7.5 Event Storming Real-World Example: Food Delivery

Events:

```text
OrderSubmitted
RestaurantAcceptedOrder
RestaurantRejectedOrder
CourierSearchStarted
CourierAssigned
FoodPrepared
FoodPickedUp
FoodDelivered
PaymentCaptured
RefundIssued
CustomerRatedOrder
```

Commands:

```text
SubmitOrder
AcceptOrder
RejectOrder
AssignCourier
MarkFoodPrepared
PickUpFood
DeliverFood
CapturePayment
IssueRefund
```

Bounded contexts:

```text
Ordering
Restaurant Operations
Courier Dispatch
Payment
Customer Experience
Promotions
Support
```

Saga discovered:

```text
OrderSubmitted
  -> authorize payment
  -> send to restaurant
  -> if restaurant accepts, assign courier
  -> if restaurant rejects, void payment and notify customer
  -> if courier cannot be found, cancel or delay based on policy
```

Hot spots:

- What if restaurant accepts but no courier is available?
- When should payment be captured?
- Who owns cancellation rules?
- Can customer cancel after food preparation starts?
- How are refunds calculated?

These hot spots are exactly the decisions that should be explicit before service design.

---

## 7.6 Event Storming Mistakes

- Treating it as technical event schema design too early.
- Inviting only engineers and no domain experts.
- Modeling database tables instead of business events.
- Using vague event names like `OrderUpdated`.
- Ignoring negative events like `PaymentFailed`.
- Ignoring timeouts.
- Not capturing hot spots.
- Assuming every event becomes a Kafka topic.
- Assuming every bounded context must become a separate service immediately.

---

## 8. CQRS

## 8.1 What Is CQRS?

CQRS means Command Query Responsibility Segregation.

It separates:

```text
Commands:
  change state

Queries:
  read state
```

Simple CQRS can be just different code paths:

```text
OrderCommandService -> handles PlaceOrder, CancelOrder
OrderQueryService   -> handles GetOrderDetails, ListOrders
```

Advanced CQRS uses separate data models:

```text
Write model:
  normalized domain model optimized for correctness

Read model:
  denormalized projection optimized for queries
```

---

## 8.2 Why CQRS Exists

The model used to validate writes is often not the best model for reads.

Write model cares about invariants:

```text
Can this order be cancelled?
Can payment be captured?
Can inventory be reserved?
```

Read model cares about screen shape:

```text
Show order summary with:
  - order status
  - payment status
  - shipment status
  - customer name
  - delivery ETA
  - refund status
```

If those fields live in many services, a read model avoids expensive runtime joins.

---

## 8.3 CQRS Architecture

```text
Client command
  -> Command API
  -> Write model database
  -> Outbox event
  -> Event broker
  -> Projection workers
  -> Read model database
  -> Query API
  -> Client reads optimized view
```

Example:

```text
PlaceOrder command:
  - validates product and customer rules
  - creates order in write DB
  - emits OrderPlaced

OrderSummaryProjection:
  - consumes OrderPlaced
  - consumes PaymentAuthorized
  - consumes ShipmentDispatched
  - updates order_summary_read table
```

---

## 8.4 CQRS With and Without Event Sourcing

CQRS does not require event sourcing.

CQRS without event sourcing:

```text
Write DB tables are source of truth.
Outbox publishes events after updates.
Read models are built from events.
```

CQRS with event sourcing:

```text
Event store is source of truth.
Read models are projections from event store.
```

Do not combine CQRS and event sourcing just because they are often mentioned together. Use event sourcing only when its audit and replay benefits justify the complexity.

---

## 8.5 CQRS Production Concerns

### Read-After-Write Consistency

Problem:

```text
User submits order.
Command succeeds.
User immediately refreshes order page.
Read model has not caught up yet.
```

Solutions:

- Return command result with enough data for immediate UI.
- Show pending state until projection catches up.
- Query write model for the specific aggregate immediately after command.
- Use session consistency token:

```text
Command response includes event_version = 12.
Query waits until read model has processed version >= 12.
```

### Projection Rebuild

Read models are disposable but rebuilding them must be planned.

Need:

- Replay from event log or source DB.
- Backfill jobs.
- Projection versioning.
- Dual-run old and new projections during migration.
- Lag metrics.
- Idempotent projection updates.

### Security

Read models may duplicate sensitive data.

Control:

- Minimize copied PII.
- Encrypt sensitive fields.
- Apply access controls at query API.
- Include retention and deletion handling.
- Avoid building "god read models" that expose everything.

### Denormalization Risk

Read models can become stale or inconsistent.

Design read models for specific use cases:

```text
order_summary_for_customer
order_dashboard_for_support
merchant_settlement_report
```

Avoid one giant read model for all consumers.

---

## 8.6 Real-World CQRS Example: Marketplace Order Page

A marketplace customer order page needs data from:

- Order Service
- Payment Service
- Shipment Service
- Seller Service
- Promotion Service
- Support Service

Runtime composition:

```text
Order page API
  -> Order Service
  -> Payment Service
  -> Shipment Service
  -> Seller Service
  -> Promotion Service
```

This can be slow and fragile.

CQRS read model:

```text
order_page_view
  order_id
  customer_id
  order_status
  payment_status
  shipment_status
  seller_name
  tracking_number
  refund_status
  support_case_status
```

Events update it:

```text
OrderPlaced
PaymentAuthorized
PaymentCaptured
ShipmentDispatched
RefundIssued
SupportCaseOpened
```

The page reads from one optimized view.

Trade-off:

```text
Faster queries and lower coupling
  in exchange for projection lag and more infrastructure
```

---

## 9. Two-Phase Commit and Three-Phase Commit

## 9.1 Why Distributed Commit Exists

Sometimes a transaction spans multiple resource managers:

```text
Database A
Database B
Message broker
```

The goal:

```text
Either all participants commit or all participants abort.
```

Two-phase commit and three-phase commit are protocols for atomic distributed commit.

In microservices, they are usually avoided across service boundaries because they reduce availability, increase coupling, and make independent ownership harder.

---

## 9.2 Two-Phase Commit

Two-phase commit has:

- Coordinator
- Participants

### Phase 1: Prepare / Vote

```text
Coordinator -> participants: Can you commit?

Participant A:
  - validates transaction
  - writes enough log to commit later
  - locks required resources
  - replies YES or NO

Participant B:
  - same
```

### Phase 2: Commit / Abort

If all vote YES:

```text
Coordinator -> participants: COMMIT
Participants commit and release locks.
```

If any vote NO:

```text
Coordinator -> participants: ABORT
Participants roll back and release locks.
```

Diagram:

```text
Client
  -> Coordinator
      -> Prepare A
      <- YES
      -> Prepare B
      <- YES
      -> Commit A
      -> Commit B
```

### 2PC Failure Problem

2PC can block.

Example:

```text
Participant voted YES.
Participant is now waiting for coordinator decision.
Coordinator crashes before sending COMMIT or ABORT.
Participant must keep locks until decision is known.
```

This hurts availability and throughput.

### 2PC Production Concerns

Costs:

- Locks held across network round trips.
- Coordinator is critical infrastructure.
- Participants are tightly coupled.
- Long-running transactions are dangerous.
- Failure recovery is complex.
- Cross-service autonomy is reduced.

2PC can be acceptable when:

- Resources are inside one trust and operational boundary.
- Transaction duration is short.
- Participants support XA or equivalent correctly.
- Throughput and availability requirements allow blocking.
- The business truly needs atomic commit.

Examples where 2PC may be reasonable:

- Internal enterprise system with two XA-compliant databases.
- Legacy monolith integration during migration.
- Financial batch process with controlled participants.

Examples where 2PC is usually a poor fit:

- Public microservice APIs.
- Long-running workflows.
- Cloud services without XA support.
- High-scale checkout across payment, inventory, shipping, and notification.
- Any flow involving human actions or third-party APIs.

---

## 9.3 Three-Phase Commit

Three-phase commit tries to reduce blocking by adding another phase.

Phases:

```text
1. CanCommit?
2. PreCommit
3. DoCommit
```

Simplified flow:

```text
Coordinator -> participants: CanCommit?
Participants -> coordinator: YES

Coordinator -> participants: PreCommit
Participants acknowledge they are prepared to commit

Coordinator -> participants: DoCommit
Participants commit
```

3PC attempts to make states more explicit so participants can make progress in some coordinator failure cases.

However, 3PC assumes bounded network delays and no network partitions in ways that do not hold reliably in many real distributed systems.

Production reality:

```text
3PC is mostly important academically.
It is rarely used as the default solution for modern microservice business workflows.
```

Microservices usually prefer:

- Saga
- Outbox
- Idempotent consumers
- Reconciliation jobs
- Explicit business states

---

## 9.4 2PC vs 3PC vs Saga

| Dimension | 2PC | 3PC | Saga |
|-----------|-----|-----|------|
| Goal | Atomic commit | Non-blocking-ish atomic commit | Eventual business consistency |
| Duration | Short | Short | Short or long |
| Locks | Yes | Yes, reduced blocking intent | No global locks |
| Failure style | Can block | Still complex under partitions | Compensate or recover forward |
| Coupling | High | High | Medium |
| External APIs | Poor fit | Poor fit | Good fit |
| Production usage | Limited | Rare | Common |
| Best for | Controlled resource managers | Mostly academic/specialized | Business workflows |

Rule of thumb:

```text
Use local ACID inside a service.
Avoid distributed ACID across services.
Use saga and compensation for cross-service business workflows.
Use 2PC only when atomicity is mandatory and participants are controlled.
```

---

## 10. Other Critical Microservice Patterns

## 10.1 Database per Service

Each service owns its database schema and persistence decisions.

```text
Order Service -> order_db
Payment Service -> payment_db
Inventory Service -> inventory_db
Shipping Service -> shipping_db
```

Benefits:

- Clear ownership.
- Independent schema changes.
- Independent scaling.
- Teams do not bypass service APIs.
- Service can choose best storage technology.

Costs:

- No simple cross-service joins.
- Reporting is harder.
- Data duplication is required.
- Consistency is eventual.
- Transactions across services need saga or similar pattern.

Production advice:

- Do not let other services write your database.
- Avoid shared tables.
- Use APIs, events, or replicated read models.
- Build analytics through CDC, event streams, or data pipelines.
- Define data contracts and ownership explicitly.

---

## 10.2 Decomposition by Business Capability

Split services by business capability, not by technical layer.

Bad split:

```text
UserControllerService
OrderControllerService
RepositoryService
ValidationService
```

This creates a distributed monolith.

Better split:

```text
Ordering
Payments
Inventory
Shipping
Catalog
Pricing
Promotions
Customer Support
Fraud
```

Each service should own:

- Business rules
- Data
- APIs/events
- Operational metrics
- Team accountability

Good service boundary test:

```text
Can this service make important decisions without constantly calling five other services?
```

If not, the boundary may be wrong.

---

## 10.3 Bounded Context Pattern

A bounded context is a boundary within which a domain model has a specific meaning.

Example: "Customer" can mean different things:

```text
Sales Context:
  prospect, lead score, sales owner

Ordering Context:
  buyer, shipping address, order history

Support Context:
  ticket requester, support tier, SLA

Billing Context:
  bill-to party, tax profile, payment terms
```

Do not force one global Customer model across all services. That creates coupling and ambiguity.

Production approach:

- Define context-specific models.
- Translate between contexts through APIs or events.
- Use anti-corruption layers when integrating with external or legacy models.
- Allow duplication where it supports autonomy.

---

## 10.4 API Gateway Pattern

An API Gateway is the entry point for external API traffic.

Responsibilities:

- Authentication
- Authorization enforcement hooks
- Rate limiting
- Routing
- Request validation
- TLS termination
- API versioning
- Request/response transformation
- Observability
- WAF integration
- Developer portal integration

```text
Mobile/Web Client
  -> API Gateway
      -> Order Service
      -> Payment Service
      -> Catalog Service
```

Production warning:

```text
Do not put core business logic in the gateway.
```

The gateway should enforce edge policies and route traffic. Business decisions belong in domain services.

---

## 10.5 Backend for Frontend

BFF creates a dedicated backend for each client experience.

```text
Mobile App -> Mobile BFF -> internal services
Web App    -> Web BFF    -> internal services
Admin UI   -> Admin BFF  -> internal services
```

Use when:

- Mobile and web need different response shapes.
- Client teams need independent evolution.
- You want to reduce client-side service orchestration.
- You need client-specific caching or aggregation.

Example:

```text
Mobile order screen needs compact payload and low bandwidth.
Admin support screen needs full customer, payment, fraud, and shipment history.
```

Both should not be forced through one generic API.

Production concerns:

- Avoid duplicating domain logic across BFFs.
- Keep BFF focused on presentation composition.
- Apply consistent auth and audit.
- Watch for too many thin services with unclear ownership.

---

## 10.6 API Composition Pattern

API composition builds a response by calling multiple services at request time.

```text
Order Details API
  -> Order Service
  -> Payment Service
  -> Shipment Service
  -> Customer Service
```

Benefits:

- Simple for low-volume or fresh reads.
- No need for separate read model.
- Data is current at time of request.

Problems:

- Latency is sum or max of dependencies.
- Partial failure handling is required.
- Fan-out can overload internal services.
- Response consistency can be mixed.

Production techniques:

- Parallelize calls.
- Use timeouts per dependency.
- Return partial response where acceptable.
- Cache stable parts.
- Apply circuit breakers.
- Limit fan-out.
- Move to CQRS read model for hot paths.

---

## 10.7 Strangler Fig Pattern

Strangler fig pattern gradually replaces a legacy system.

```text
Client
  -> Router / Gateway
      -> Legacy Monolith for old capabilities
      -> New Microservice for migrated capabilities
```

Steps:

1. Put a routing layer in front of legacy.
2. Choose one business capability to extract.
3. Build new service.
4. Route selected traffic to new service.
5. Synchronize or migrate data safely.
6. Expand capability coverage.
7. Retire legacy path.

Real example:

```text
Retail monolith owns all checkout.
Extract promotions first.
Gateway routes promotion calculation to new Promotion Service.
Later extract payment, order history, and shipment tracking.
```

Production concerns:

- Data ownership during transition.
- Dual writes are dangerous.
- Reconciliation jobs are required.
- Observability must compare old vs new behavior.
- Feature flags help progressive migration.
- Rollback path must be clear.

---

## 10.8 Anti-Corruption Layer

An anti-corruption layer protects your domain model from another model.

Use when integrating with:

- Legacy monolith
- External payment provider
- ERP
- CRM
- Vendor API
- Another bounded context with different language

Example:

```text
External payment provider says:
  AUTH, SALE, VOID, REVERSAL

Your Payment Context says:
  PaymentAuthorized
  PaymentCaptured
  AuthorizationVoided
  RefundIssued
```

The ACL translates between them.

Benefits:

- Keeps domain model clean.
- Isolates vendor changes.
- Centralizes mapping and error handling.
- Prevents legacy concepts from leaking everywhere.

Production concerns:

- Map error codes explicitly.
- Normalize retryable vs non-retryable failures.
- Store external IDs.
- Preserve raw payloads when useful for audit.
- Version provider integrations.

---

## 10.9 Circuit Breaker Pattern

A circuit breaker prevents repeated calls to a failing dependency.

States:

```text
CLOSED:
  calls allowed

OPEN:
  calls fail fast

HALF_OPEN:
  limited trial calls to check recovery
```

Example:

```text
Order Service calls Recommendation Service.
Recommendation Service starts timing out.
Circuit opens.
Order page returns without recommendations instead of failing checkout.
```

Production tuning:

- Use separate breakers per dependency and operation.
- Define failure thresholds.
- Define slow-call thresholds.
- Choose fallback behavior intentionally.
- Alert when circuit opens.
- Avoid using fallback for critical correctness decisions unless safe.

Do not hide important failures. A circuit breaker is a resilience control, not an observability substitute.

---

## 10.10 Retry Pattern

Retries handle transient failures.

Good retry candidates:

- Network timeout
- 503 Service Unavailable
- Rate-limited response with retry-after
- Temporary lock conflict
- Broker publish failure

Bad retry candidates:

- Validation error
- Payment declined
- Unauthorized request
- Duplicate business command without idempotency

Production retry rules:

- Use exponential backoff.
- Add jitter to prevent retry storms.
- Set a maximum retry budget.
- Use idempotency keys.
- Respect retry-after headers.
- Avoid retrying across long request chains.

Bad:

```text
Service A retries B 3 times.
B retries C 3 times.
C retries D 3 times.

One user request can become 27 downstream calls.
```

Better:

```text
Use timeouts, retry budgets, queue-based retry where appropriate,
and clear failure responses.
```

---

## 10.11 Timeout Pattern

Every network call needs a timeout.

Without timeouts:

```text
threads wait forever
connection pools exhaust
latency cascades
system appears down
```

Timeout design:

```text
Client timeout > API gateway timeout > service timeout > dependency timeout
```

Example:

```text
Mobile client timeout: 10 sec
API gateway timeout: 8 sec
Order Service handler budget: 6 sec
Payment call timeout: 2 sec
Inventory call timeout: 2 sec
```

Production advice:

- Use deadline propagation.
- Track timeout metrics.
- Avoid one global timeout for all operations.
- Tune based on SLOs and latency distributions.
- Prefer async workflows for long-running operations.

---

## 10.12 Bulkhead Pattern

Bulkheads isolate failures.

Example:

```text
Order Service thread pools:
  - checkout pool
  - order history pool
  - recommendations pool
```

If recommendations become slow, checkout still has resources.

Bulkheads can be:

- Separate thread pools
- Separate connection pools
- Separate queues
- Separate Kubernetes deployments
- Separate databases
- Separate rate limits

Production use:

- Protect critical paths.
- Isolate noisy tenants.
- Separate batch from online traffic.
- Separate admin jobs from customer requests.

---

## 10.13 Rate Limiting and Load Shedding

Rate limiting controls how much traffic a caller can send.

Load shedding rejects work when the system is overloaded.

Example:

```text
API Gateway:
  customer API limit = 100 req/min per user
  partner API limit = 1000 req/min per partner

Order Service:
  reject low-priority recommendation refresh when CPU > 85%
  keep checkout path available
```

Production concerns:

- Return clear 429 or overload responses.
- Use per-tenant limits.
- Avoid one noisy client taking down everyone.
- Track rejected requests.
- Prioritize critical business operations.

---

## 10.14 Idempotency Pattern

Idempotency means repeating the same operation produces the same intended result.

Critical for:

- Payment APIs
- Order creation
- Message consumers
- Saga commands
- Retryable endpoints

Example:

```text
POST /orders
Idempotency-Key: checkout-123
```

Server stores:

```text
idempotency_key
request_hash
response_body
status
created_at
expires_at
```

If the client retries the same request:

```text
Same key + same request:
  return original response

Same key + different request:
  reject as conflict
```

Production details:

- Choose idempotency key scope carefully.
- Store response for completed operations.
- Handle in-progress duplicate requests.
- Expire old keys after safe retention.
- Include tenant/account in uniqueness key.

---

## 10.15 Inbox Pattern

The inbox pattern stores received messages before or while processing them to ensure idempotent consumption.

```text
Consumer receives event
  -> insert into inbox table with message_id
  -> process if not already processed
  -> mark processed
```

Use with outbox:

```text
Producer:
  transactional outbox

Consumer:
  inbox / processed_messages
```

This gives practical reliability:

```text
At-least-once delivery + idempotent processing = effectively-once business effect
```

Not mathematically exactly once, but usually what business systems need.

---

## 10.16 Service Discovery Pattern

Services need to find other services.

Options:

- DNS-based discovery
- Kubernetes service discovery
- Service registry such as Consul or Eureka
- Service mesh discovery
- Cloud load balancer endpoints

Production concerns:

- Health checks must reflect readiness, not just process alive.
- Remove unhealthy instances quickly but avoid flapping.
- Use connection draining on shutdown.
- Prefer stable logical names over hardcoded IPs.
- Watch DNS caching behavior.

---

## 10.17 Service Mesh / Sidecar Pattern

A service mesh moves cross-cutting network concerns into sidecars or infrastructure.

Common capabilities:

- mTLS between services
- Traffic routing
- Retries and timeouts
- Circuit breaking
- Observability
- Policy enforcement
- Canary routing

```text
Service A -> sidecar proxy -> sidecar proxy -> Service B
```

Benefits:

- Consistent traffic policy.
- Less duplicated client library code.
- Strong service-to-service identity.

Costs:

- Operational complexity.
- Debugging requires mesh knowledge.
- Misconfigured retries can amplify traffic.
- Sidecars consume resources.

Use a mesh when platform maturity justifies it. Do not add it only because microservices exist.

---

## 10.18 Consumer-Driven Contract Testing

Microservices evolve independently, so API contracts must be protected.

Consumer-driven contract testing means consumers define expectations and providers verify them.

Example:

```text
Order BFF expects Payment Service:
  GET /payments/{orderId}
  returns payment_status and authorized_amount
```

Payment Service runs provider verification before deployment.

Production benefits:

- Prevents breaking consumers.
- Enables independent deployment.
- Documents real usage.
- Reduces need for giant end-to-end test suites.

Still needed:

- Backward-compatible API evolution.
- Schema versioning.
- Deprecation policy.
- Runtime monitoring.

---

## 10.19 Schema Versioning Pattern

Event and API schemas must evolve without breaking consumers.

Rules:

- Add fields instead of removing fields.
- Make consumers ignore unknown fields.
- Avoid changing field meaning.
- Version breaking changes.
- Support old and new versions during migration.
- Track consumer adoption.

Event naming:

```text
Good:
  OrderPlaced.v1
  OrderPlaced.v2

Risky:
  OrderUpdated
```

Prefer semantic events:

```text
OrderCancelled
DeliveryAddressChanged
PaymentCaptureFailed
```

Over vague events:

```text
OrderChanged
EntityUpdated
```

---

## 10.20 Reconciliation Pattern

Even with good messaging, production systems need reconciliation.

Reconciliation compares source-of-truth state across systems and fixes or flags mismatches.

Examples:

```text
Payment provider says payment captured.
Payment Service says authorization only.
Reconciliation job detects mismatch and updates or alerts.
```

```text
Inventory reservation expired.
Order still waiting for payment.
Reconciliation cancels stale checkout.
```

Use reconciliation for:

- External providers
- Payment and refunds
- Inventory reservations
- Settlement
- Subscription billing
- Long-running sagas

Production requirements:

- Clear source of truth per field.
- Idempotent repair actions.
- Audit trail.
- Dry-run mode.
- Metrics and alerts.
- Manual review path.

---

## 10.21 Leader Election and Lease Pattern

Some background jobs should have only one active worker.

Examples:

- Outbox relay shard coordinator
- Scheduled billing run
- Reconciliation coordinator
- Projection migration

Use a lease:

```text
worker_id = W1
lease_name = billing-run
expires_at = now + 30 sec
```

Worker must renew lease. If it dies, another worker can take over after expiration.

Production concerns:

- Use fencing tokens to prevent old leader from writing after lease loss.
- Keep lease duration longer than expected clock skew and renew interval.
- Make job steps idempotent anyway.
- Monitor leader changes.

---

## 10.22 Side Effects Isolation Pattern

Side effects include:

- Email
- SMS
- Push notifications
- Payment provider calls
- Webhooks
- External API calls

Do not mix irreversible side effects carelessly inside critical DB transactions.

Better:

```text
Local transaction:
  - record intent to send email
  - commit

Async worker:
  - sends email
  - records provider response
```

Benefits:

- Retryable.
- Observable.
- Avoids long DB transactions.
- Enables DLQ and manual recovery.

---

## 10.23 Versioned Deployment Patterns

Microservices need safe release patterns.

Common patterns:

- Rolling deployment
- Blue-green deployment
- Canary deployment
- Feature flags
- Shadow traffic
- Dark launch

Production advice:

- Make database changes backward compatible.
- Deploy expand-and-contract migrations.
- Keep old event consumers compatible.
- Monitor business metrics, not just CPU.
- Have rollback and roll-forward plans.

Expand-and-contract example:

```text
1. Add new nullable column.
2. Deploy code that writes both old and new.
3. Backfill old rows.
4. Deploy code that reads new.
5. Stop writing old.
6. Drop old column later.
```

---

## 10.24 Publish-Subscribe Pattern

Publish-subscribe lets one producer publish an event without knowing all consumers.

```text
Order Service publishes OrderConfirmed
  -> Notification Service sends email
  -> Shipping Service starts fulfillment
  -> Analytics Service updates dashboard
  -> Loyalty Service awards points
```

Benefits:

- Producer is decoupled from consumers.
- New consumers can be added without changing producer.
- Good fit for domain events.

Production risks:

- Consumers may depend on events the producer does not treat as a contract.
- Event schema changes can break many consumers.
- Event ordering and replay semantics must be clear.
- A high-volume producer can overload many consumers.

Production rules:

- Own event contracts like APIs.
- Version events.
- Track consumers.
- Define retention and replay policy.
- Keep events meaningful and business-specific.

---

## 10.25 Competing Consumers Pattern

Competing consumers process messages from the same queue in parallel.

```text
Queue
  -> Worker 1
  -> Worker 2
  -> Worker 3
  -> Worker N
```

Use when:

- Work items are independent.
- Throughput can scale horizontally.
- Processing order is not globally important.

Examples:

- Image resizing jobs
- Email sending
- Invoice generation
- Webhook delivery
- Order projection updates partitioned by aggregate ID

Production concerns:

- Use idempotent processing.
- Set visibility timeout or ack deadline correctly.
- Use dead-letter queues for poison messages.
- Protect downstream dependencies from too much parallelism.
- Partition by key if per-aggregate ordering matters.

---

## 10.26 Dead-Letter Queue and Poison Message Pattern

A poison message repeatedly fails and blocks useful work.

Dead-letter queue flow:

```text
Consumer receives message
  -> processing fails
  -> retry with backoff
  -> still fails after max attempts
  -> move to DLQ
```

DLQ is not a trash can. It is an operational queue requiring ownership.

Production requirements:

- Alert on DLQ growth.
- Store failure reason.
- Provide replay tooling.
- Allow replay after code or data fix.
- Separate retryable and non-retryable failures.
- Avoid infinite retry loops.

Common poison message causes:

- Bad schema version.
- Missing referenced data.
- Consumer bug.
- External dependency permanently rejects request.
- Message violates business invariant.

DLQ handling example:

```text
PaymentCaptured event fails in Shipment Service because address is invalid.
Message goes to DLQ.
Support fixes address or cancels order.
Engineer replays message or triggers compensation.
```

---

## 10.27 Claim Check Pattern

The claim check pattern stores a large payload externally and sends only a reference in the message.

```text
Large document or image
  -> Object storage
  -> Message contains object key and metadata
```

Example:

```json
{
  "event_type": "MedicalReportUploaded",
  "report_id": "R-100",
  "object_uri": "s3://reports-bucket/R-100.pdf",
  "checksum": "abc123",
  "content_type": "application/pdf"
}
```

Use when:

- Payload exceeds broker limits.
- Payload is binary or large.
- Multiple consumers need the same object.
- Payload needs separate retention or access control.

Production concerns:

- Secure object access.
- Include checksum.
- Define object retention.
- Handle object missing or deleted.
- Avoid leaking sensitive object URIs.
- Make object write and message publish reliable, often with outbox or durable intent.

---

## 10.28 Event Notification vs Event-Carried State Transfer

There are two common event styles.

Event notification:

```text
OrderConfirmed event says:
  order_id = O-100
```

Consumer must call Order Service to get details.

Benefits:

- Small events.
- Less duplicated data.
- Producer exposes current state through API.

Costs:

- Consumer depends synchronously on producer.
- Replay can see current state, not historical state.
- Can create thundering herd after high-volume events.

Event-carried state transfer:

```text
OrderConfirmed event contains:
  order_id
  customer_id
  total
  currency
  line_items
  confirmed_at
```

Benefits:

- Consumer can process without calling producer.
- Better for read model projections.
- Better replay behavior if event contains historical facts.

Costs:

- Larger events.
- More schema management.
- Duplicated data.
- Sensitive data can spread.

Production choice:

```text
Use event notification when consumers only need to know something changed.
Use event-carried state when consumers need facts to build their own state.
```

---

## 10.29 Health Check, Readiness, and Graceful Shutdown Pattern

Health checks are production contracts between services and infrastructure.

Different checks answer different questions:

| Check | Question | Example |
|-------|----------|---------|
| Liveness | Should this process be restarted? | Main loop is not deadlocked |
| Readiness | Should this instance receive traffic? | DB connection ready, warmup complete |
| Startup | Has startup completed? | Migrations/warmup finished |
| Dependency health | Is a downstream dependency usable? | Payment provider reachable |

Production advice:

- Do not make liveness depend on every downstream service.
- Readiness should fail during startup, shutdown, or severe dependency loss.
- Use graceful shutdown to stop receiving new work before exiting.
- Drain in-flight requests.
- Stop polling queues before terminating workers.
- Extend visibility timeout or release messages safely during shutdown.

Shutdown flow:

```text
SIGTERM received
  -> mark readiness false
  -> stop accepting new HTTP requests
  -> stop taking new queue messages
  -> finish in-flight work within deadline
  -> commit or safely abandon work
  -> exit
```

---

## 10.30 Externalized Configuration and Secrets Pattern

Microservices should not hardcode environment-specific configuration.

Configuration examples:

- Database URLs
- Broker topic names
- Feature flags
- Rate limits
- Timeout values
- Third-party endpoints

Secrets examples:

- API keys
- DB passwords
- OAuth client secrets
- Signing keys

Production rules:

- Store secrets in a secret manager, not in git.
- Rotate secrets.
- Audit secret access.
- Separate config from secrets.
- Validate config at startup.
- Prefer dynamic config only where runtime changes are safe.
- Version important business configuration.

Be careful with dynamic config. Changing retry counts, timeouts, or rate limits at runtime can destabilize a system if not reviewed and monitored.

---

## 10.31 Distributed Tracing and Correlation ID Pattern

Distributed tracing connects work across services.

```text
Client request
  -> API Gateway
  -> Order Service
  -> Payment Service
  -> Inventory Service
  -> Shipping Service
```

Every hop should carry:

- Trace ID
- Span ID
- Correlation ID
- Causation ID for event-driven flows
- Business key where safe, such as order_id

In synchronous calls:

```text
traceparent header
x-correlation-id
```

In events:

```text
headers:
  trace_id
  correlation_id
  causation_id
  producer_service
```

Production benefits:

- Debug cross-service latency.
- Find where failures begin.
- Connect logs, metrics, traces, and business events.
- Support customer incident investigation.

Important rule:

```text
Do not put sensitive data in trace IDs, log correlation IDs, or span names.
```

---

## 10.32 Materialized View Pattern

A materialized view stores precomputed query data.

In microservices, materialized views are often built from events.

```text
Order events + Payment events + Shipment events
  -> order_support_view
```

Use when:

- Query requires data from many services.
- Query is frequent.
- Low latency is required.
- Slight staleness is acceptable.

Production concerns:

- Define the source events.
- Make updates idempotent.
- Track projection lag.
- Rebuild view from source.
- Apply access control.
- Avoid turning one view into a hidden shared database for writes.

---

## 11. End-to-End Production Example: Ecommerce Checkout

This section shows how patterns combine in a realistic system.

Services:

```text
Catalog Service
Pricing Service
Promotion Service
Order Service
Inventory Service
Payment Service
Shipping Service
Notification Service
Customer Support Service
```

Data ownership:

```text
Order Service:
  order state, order lines, order total

Inventory Service:
  stock, reservations

Payment Service:
  authorization, capture, refund

Shipping Service:
  shipment request, label, tracking

Notification Service:
  notification intent and delivery status
```

Checkout saga:

```text
1. Create pending order
2. Reserve inventory
3. Authorize payment
4. Confirm order
5. Capture payment
6. Create shipment request
7. Send confirmation notification
```

Compensation:

```text
If inventory fails:
  cancel order

If payment authorization fails:
  release inventory
  cancel order

If order confirmation fails after payment authorization:
  retry confirm order
  if impossible, void payment authorization and release inventory

If payment capture succeeds but shipment fails:
  do not simply cancel silently
  choose business policy:
    - retry shipment
    - route to manual fulfillment
    - refund payment and cancel order

If notification fails:
  do not cancel order
  retry notification and expose status to support
```

Outbox usage:

```text
Order Service:
  create order + outbox OrderCreated

Inventory Service:
  reserve inventory + outbox InventoryReserved

Payment Service:
  authorize payment + outbox PaymentAuthorized

Shipping Service:
  create shipment + outbox ShipmentCreated
```

CQRS read model:

```text
order_tracking_view:
  order_id
  order_status
  payment_status
  inventory_status
  shipment_status
  tracking_number
  estimated_delivery
```

Events feeding read model:

```text
OrderCreated
InventoryReserved
PaymentAuthorized
PaymentCaptured
ShipmentCreated
ShipmentDispatched
ShipmentDelivered
RefundIssued
OrderCancelled
```

Resilience:

```text
Payment provider:
  timeout + retry with idempotency key + reconciliation

Inventory:
  reservation TTL + release compensation

Shipping:
  retry label creation + manual review if carrier rejects

Notifications:
  async side-effect worker + DLQ
```

Observability:

```text
correlation_id = checkout request id
saga_id = checkout saga id
order_id = business key

Trace:
  API Gateway
  Order Service
  Saga Orchestrator
  Inventory Service
  Payment Service
  Shipping Service
  Notification Service
```

Critical alerts:

- Checkout saga stuck above threshold.
- Compensation failure.
- Outbox pending age too high.
- Payment authorization success but order not confirmed.
- Inventory reservation expired while order still pending.
- Read model lag too high.
- DLQ count increasing.

---

## 12. Choosing Between Patterns

### Saga vs 2PC

Use saga when:

- Workflow spans services.
- External APIs are involved.
- Business process can be eventually consistent.
- Steps may be long-running.
- Compensation or forward recovery is acceptable.

Use 2PC only when:

- All participants support distributed transactions.
- Participants are under one operational control.
- Locks will be short-lived.
- Atomicity is mandatory.
- Availability trade-off is acceptable.

### Outbox vs Direct Publish

Use outbox when:

- Event must not be lost after DB commit.
- Event represents business state change.
- Consumers depend on event for workflow.

Direct publish may be acceptable when:

- Event is low-value telemetry.
- Loss is acceptable.
- Event can be reconstructed easily.

### CQRS vs API Composition

Use API composition when:

- Low traffic.
- Few dependencies.
- Freshness is more important than latency.
- Partial failures are acceptable.

Use CQRS read model when:

- Query is hot.
- Many services are involved.
- Low latency is required.
- You can tolerate projection lag.
- You need query-specific denormalization.

### Event Sourcing vs Normal Persistence

Use event sourcing when:

- Audit trail is core.
- State transitions are business-critical.
- Rebuildable projections are valuable.
- Temporal analysis matters.

Use normal persistence when:

- CRUD state is enough.
- Audit can be handled separately.
- Team does not need replay complexity.
- Query simplicity is more valuable.

---

## 13. Production Checklist

### Service Boundary Checklist

- Does the service own a business capability?
- Does it own its data?
- Can it make decisions without excessive synchronous calls?
- Does it expose stable contracts?
- Can it deploy independently?
- Does a team own it operationally?

### Data Consistency Checklist

- What is the source of truth for each field?
- Which updates are strongly consistent?
- Which updates are eventually consistent?
- What happens if events arrive late?
- What happens if events are duplicated?
- What happens if a consumer is down for hours?
- How is data reconciled?

### Saga Checklist

- Is the saga choreography or orchestration?
- What is the state machine?
- What are terminal states?
- Which steps are compensatable?
- Which step is the pivot?
- Which steps are retriable?
- What is the compensation for each successful step?
- Are compensations idempotent?
- What are the timeouts?
- What is the manual recovery process?
- What metrics and alerts exist?

### Outbox Checklist

- Is event insertion in the same DB transaction as business update?
- How does the relay claim rows?
- What happens if publish succeeds but marking published fails?
- Are consumers idempotent?
- Is event ordering required?
- How are failed events retried?
- How are poison events handled?
- How is the outbox table cleaned?
- Can events be replayed?

### Event Sourcing Checklist

- Are events true business facts?
- Is event schema versioned?
- Are old events readable forever?
- Are projections rebuildable?
- Are snapshots versioned?
- Is sensitive data handled safely?
- Is replay tested?
- Is concurrency handled with expected version?

### CQRS Checklist

- What read models are needed?
- Which events update each read model?
- How much lag is acceptable?
- How is read-after-write handled?
- Can projections be rebuilt?
- Are projection updates idempotent?
- Are read models access-controlled?

### Resilience Checklist

- Does every network call have a timeout?
- Are retries bounded and jittered?
- Are idempotency keys used?
- Are circuit breakers configured?
- Are bulkheads protecting critical paths?
- Are DLQs monitored?
- Is there backpressure?
- Are rate limits per tenant or caller?

### Observability Checklist

- Is there a correlation ID across services?
- Are traces sampled correctly?
- Are business metrics emitted?
- Are logs structured?
- Can support inspect workflow state?
- Are dashboards tied to SLOs?
- Are alerts actionable?
- Can engineers replay or repair safely?

---

## 14. Common Anti-Patterns

### Distributed Monolith

Symptoms:

- Services must deploy together.
- One request synchronously calls many services.
- Shared database.
- Business rules spread randomly.
- Every change requires cross-team coordination.

Fix:

- Redraw boundaries by business capability.
- Move rules to owning service.
- Use events/read models to reduce synchronous chains.
- Create clear ownership.

### Shared Database Between Services

Symptoms:

- Many services write the same tables.
- Schema changes break unrelated services.
- No clear source of truth.

Fix:

- Assign table ownership.
- Move access behind APIs/events.
- Use CDC or read replicas for reporting.
- Migrate gradually with strangler pattern.

### Event Soup

Symptoms:

- Too many vague events.
- No one knows who consumes what.
- Events named `EntityUpdated`.
- Breaking changes surprise consumers.

Fix:

- Use domain events.
- Maintain schema registry or contract catalog.
- Track consumers.
- Version events.
- Keep event ownership clear.

### Synchronous Chain Explosion

Symptoms:

```text
API Gateway -> A -> B -> C -> D -> E
```

Problems:

- High latency.
- Failure propagation.
- Retry amplification.
- Hard debugging.

Fix:

- Collapse boundaries if wrong.
- Use async workflow.
- Use CQRS read model.
- Use API composition only at controlled edges.

### Fake Exactly Once

Symptoms:

- Team assumes broker prevents duplicates.
- Consumers are not idempotent.
- Duplicate payment or duplicate order appears during retry.

Fix:

- Design for at-least-once.
- Use idempotency keys.
- Use processed message table.
- Use business operation IDs.

---

## 15. Pattern Combinations That Work Well

### Saga + Outbox + Inbox

Best for reliable cross-service workflows.

```text
Saga orchestrator sends command.
Participant updates local DB and outbox atomically.
Outbox publishes event.
Orchestrator consumes event idempotently with inbox.
```

### CQRS + Outbox

Best for read models derived from write model changes.

```text
Write service commits state + outbox event.
Projection consumer updates read model idempotently.
```

### Event Sourcing + CQRS

Best for audit-heavy systems with specialized read models.

```text
Event store is source of truth.
Projections build query models.
```

### Strangler + Anti-Corruption Layer

Best for legacy modernization.

```text
New service protects its domain model from legacy model.
Gateway routes migrated capability to new service.
ACL translates legacy calls/events/data.
```

### API Gateway + BFF

Best for external API management plus client-specific experience.

```text
API Gateway handles edge policy.
BFF handles client-specific composition.
Domain services own business logic.
```

---

## 16. Final Mental Model

Microservice design patterns are not independent tricks. They are responses to specific forces:

```text
Need independent data ownership
  -> Database per service

Need cross-service workflow
  -> Saga

Need reliable event publishing
  -> Outbox

Need duplicate-safe consumption
  -> Inbox / idempotent consumer

Need audit and replay
  -> Event sourcing

Need optimized reads
  -> CQRS

Need discover boundaries
  -> Event storming

Need atomic commit across controlled resources
  -> 2PC, rarely across microservices

Need legacy migration
  -> Strangler fig + anti-corruption layer

Need runtime resilience
  -> Timeout, retry, circuit breaker, bulkhead, rate limit
```

The production-grade approach is:

```text
1. Model business boundaries first.
2. Keep data ownership clear.
3. Use local ACID transactions inside services.
4. Use outbox for reliable event publishing.
5. Use idempotency everywhere messages or retries exist.
6. Use saga for cross-service business workflows.
7. Use compensation as explicit business action, not technical rollback.
8. Use CQRS/read models for query needs, not by default.
9. Use event sourcing only when history is the source of truth.
10. Build reconciliation, observability, and manual recovery from day one.
```

That is the difference between a diagram that looks like microservices and a production system that can survive real failures.
