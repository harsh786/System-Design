# 023. Design Order Management System

Source problem: `Design order management system.`  
Category: `Commerce workflow`  
Primary focus: `state machine, command, outbox, idempotency`  
Archetype: `state-workflow`

## 1. Interview Framing

Design `order management system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `order management system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `DRAFT, PLACED, PAID, FULFILLING, SHIPPED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.
- Handle retries through idempotency keys and optimistic version checks.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `Customer`
- `OrderAgent`
- `FulfillmentService`

Primary use cases:

- `placeOrder` command on `OrderManagementSystem`
- `capturePayment` command on `OrderManagementSystem`
- `shipOrder` command on `OrderManagementSystem`
- `cancelOrder` command on `OrderManagementSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `OrderManagementSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Order, OrderLine, Shipment, PaymentRecord, OutboxEvent` | Have identity and change over time under the aggregate. |
| Value objects | `Money, Quantity, OrderNumber, IdempotencyKey` | Immutable concepts compared by value. |
| Policies | `OrderManagementSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `OrderManagementSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
DRAFT, PLACED, PAID, FULFILLING, SHIPPED, CANCELLED, RETURNED
```

Invariants:

- `OrderManagementSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `OrderManagementSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `OrderManagementSystem` | Composes | Order, OrderLine, Shipment | Owns invariants and lifecycle transitions. |
| `OrderManagementSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `OrderManagementSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class OrderManagementSystem {
  +UUID id
  +OrderManagementSystemStatus status
  +long version
  +validateInvariants()
}
class OrderManagementSystemService {
  +handle(command)
}
class OrderManagementSystemRepository {
  <<interface>>
  +findById(UUID id) OrderManagementSystem
  +save(OrderManagementSystem aggregate, long expectedVersion)
}
class OrderManagementSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
OrderManagementSystemService --> OrderManagementSystemRepository
OrderManagementSystemService --> OrderManagementSystemPolicy
OrderManagementSystemService --> OrderManagementSystem
class Order {
  +UUID id
  +validate()
}
OrderManagementSystem "1" o-- "many" Order
class OrderLine {
  +UUID id
  +validate()
}
OrderManagementSystem "1" o-- "many" OrderLine
class Shipment {
  +UUID id
  +validate()
}
OrderManagementSystem "1" o-- "many" Shipment
class PaymentRecord {
  +UUID id
  +validate()
}
OrderManagementSystem "1" o-- "many" PaymentRecord
class Money {
  <<value object>>
}
OrderManagementSystem ..> Money
class Quantity {
  <<value object>>
}
OrderManagementSystem ..> Quantity
class OrderNumber {
  <<value object>>
}
OrderManagementSystem ..> OrderNumber
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as OrderManagementSystemService
participant Repo as OrderManagementSystemRepository
participant Policy as OrderManagementSystemPolicy
participant Agg as OrderManagementSystem
participant Outbox
Client->>Service: placeOrder(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: placeOrder(command)
Agg-->>Service: OrderManagementSystemPlaceOrderEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |
| Command | Represent user or system intent as retryable, auditable, and optionally undoable objects. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.ordermanagementsystem;

import java.time.Instant;
import java.util.*;

record IdempotencyKey(String value) {
    IdempotencyKey {
        if (value == null || value.isBlank()) throw new IllegalArgumentException("idempotency key is required");
    }
}

record Decision(boolean allowed, String reason) {
    static Decision allow() { return new Decision(true, "allowed"); }
    static Decision reject(String reason) { return new Decision(false, reason); }
}

enum OrderManagementSystemStatus {
    DRAFT,
    PLACED,
    PAID,
    FULFILLING,
    SHIPPED,
    CANCELLED,
    RETURNED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record OrderManagementSystemPlaceOrderEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record OrderManagementSystemCapturePaymentEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record OrderManagementSystemShipOrderEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record OrderManagementSystemCancelOrderEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface OrderManagementSystemCommand permits PlaceOrderCommand, CapturePaymentCommand, ShipOrderCommand, CancelOrderCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record PlaceOrderCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements OrderManagementSystemCommand {}
record CapturePaymentCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements OrderManagementSystemCommand {}
record ShipOrderCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements OrderManagementSystemCommand {}
record CancelOrderCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements OrderManagementSystemCommand {}

interface OrderManagementSystemRepository {
    Optional<OrderManagementSystem> findById(UUID id);
    void save(OrderManagementSystem aggregate, long expectedVersion);
}

interface OrderManagementSystemPolicy {
    Decision evaluate(OrderManagementSystem aggregate, OrderManagementSystemCommand command);
}

final class Order {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class OrderManagementSystem {
    private final UUID id;
    private final List<Order> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private OrderManagementSystemStatus status;
    private long version;

    OrderManagementSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = OrderManagementSystemStatus.DRAFT;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    OrderManagementSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void placeOrder(PlaceOrderCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run placeOrder when aggregate is terminal");
    this.status = OrderManagementSystemStatus.PLACED;
    this.version++;
    this.domainEvents.add(new OrderManagementSystemPlaceOrderEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void capturePayment(CapturePaymentCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run capturePayment when aggregate is terminal");
    this.status = OrderManagementSystemStatus.PAID;
    this.version++;
    this.domainEvents.add(new OrderManagementSystemCapturePaymentEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void shipOrder(ShipOrderCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run shipOrder when aggregate is terminal");
    this.status = OrderManagementSystemStatus.FULFILLING;
    this.version++;
    this.domainEvents.add(new OrderManagementSystemShipOrderEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void cancelOrder(CancelOrderCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run cancelOrder when aggregate is terminal");
    this.status = OrderManagementSystemStatus.SHIPPED;
    this.version++;
    this.domainEvents.add(new OrderManagementSystemCancelOrderEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == OrderManagementSystemStatus.RETURNED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class OrderManagementSystemService {
    private final OrderManagementSystemRepository repository;
    private final OrderManagementSystemPolicy policy;
    private final Outbox outbox;

    OrderManagementSystemService(OrderManagementSystemRepository repository, OrderManagementSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(OrderManagementSystemCommand command) {
        OrderManagementSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("OrderManagementSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof PlaceOrderCommand c) aggregate.placeOrder(c);
        if (command instanceof CapturePaymentCommand c) aggregate.capturePayment(c);
        if (command instanceof ShipOrderCommand c) aggregate.shipOrder(c);
        if (command instanceof CancelOrderCommand c) aggregate.cancelOrder(c);
        repository.save(aggregate, expectedVersion);
        outbox.appendAll(aggregate.pullDomainEvents());
    }
}

interface Outbox {
    void appendAll(List<DomainEvent> events);
}

class InvalidStateException extends RuntimeException { InvalidStateException(String message) { super(message); } }
class DuplicateCommandException extends RuntimeException { DuplicateCommandException(String message) { super(message); } }
class PolicyRejectedException extends RuntimeException { PolicyRejectedException(String message) { super(message); } }
```

## 11. Concurrency And Thread Safety

- Use optimistic concurrency on aggregate save: `save(aggregate, expectedVersion)`.
- Lock scarce resources such as seats, rooms, inventory, accounts, or tasks with short-lived holds.
- Make commands idempotent when callers can retry after timeout.
- Publish events through an outbox in the same transaction as the aggregate update.

## 12. Persistence And Transactions

- Persist `OrderManagementSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
- Persist child entities in owned tables/documents keyed by aggregate id.
- Store domain events in an outbox table in the same transaction.
- Add indexes for business lookup keys, active state, owner/user id, and expiry deadlines.

## 13. Error Handling And Idempotency

- Return typed domain errors: `NotFound`, `InvalidState`, `PolicyRejected`, `Conflict`, and `DuplicateCommand`.
- Never partially mutate aggregate state before all guards pass.
- Log rejection reasons with correlation id; avoid logging secrets, tokens, or sensitive payloads.
- Use idempotency records for externally retried commands and provider callbacks.

## 14. Extensibility Hooks

| Change point | Extension mechanism |
|---|---|
| Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. | `State` |
| Represent user or system intent as retryable, auditable, and optionally undoable objects. | `Command` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `OrderManagementSystem` invariants and each command method.
- State-machine test all valid and invalid `OrderManagementSystemStatus` transitions.
- Contract test every `OrderManagementSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `OrderManagementSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `OrderManagementSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
