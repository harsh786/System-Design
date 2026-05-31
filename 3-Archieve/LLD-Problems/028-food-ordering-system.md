# 028. Design Food Ordering System

Source problem: `Design food ordering system.`  
Category: `Marketplace`  
Primary focus: `restaurant menu, order lifecycle, delivery assignment`  
Archetype: `state-workflow`

## 1. Interview Framing

Design `food ordering system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `food ordering system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `CREATED, ACCEPTED, PREPARING, READY_FOR_PICKUP, OUT_FOR_DELIVERY`.
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
- `Restaurant`
- `Courier`
- `PaymentProvider`

Primary use cases:

- `placeOrder` command on `FoodOrderingSystem`
- `acceptOrder` command on `FoodOrderingSystem`
- `assignCourier` command on `FoodOrderingSystem`
- `completeDelivery` command on `FoodOrderingSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `FoodOrderingSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Restaurant, MenuItem, FoodOrder, DeliveryAssignment, Payment` | Have identity and change over time under the aggregate. |
| Value objects | `Money, Address, Quantity, ETA` | Immutable concepts compared by value. |
| Policies | `FoodOrderingSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `FoodOrderingSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
CREATED, ACCEPTED, PREPARING, READY_FOR_PICKUP, OUT_FOR_DELIVERY, DELIVERED, CANCELLED
```

Invariants:

- `FoodOrderingSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `FoodOrderingSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `FoodOrderingSystem` | Composes | Restaurant, MenuItem, FoodOrder | Owns invariants and lifecycle transitions. |
| `FoodOrderingSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `FoodOrderingSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class FoodOrderingSystem {
  +UUID id
  +FoodOrderingSystemStatus status
  +long version
  +validateInvariants()
}
class FoodOrderingSystemService {
  +handle(command)
}
class FoodOrderingSystemRepository {
  <<interface>>
  +findById(UUID id) FoodOrderingSystem
  +save(FoodOrderingSystem aggregate, long expectedVersion)
}
class FoodOrderingSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
FoodOrderingSystemService --> FoodOrderingSystemRepository
FoodOrderingSystemService --> FoodOrderingSystemPolicy
FoodOrderingSystemService --> FoodOrderingSystem
class Restaurant {
  +UUID id
  +validate()
}
FoodOrderingSystem "1" o-- "many" Restaurant
class MenuItem {
  +UUID id
  +validate()
}
FoodOrderingSystem "1" o-- "many" MenuItem
class FoodOrder {
  +UUID id
  +validate()
}
FoodOrderingSystem "1" o-- "many" FoodOrder
class DeliveryAssignment {
  +UUID id
  +validate()
}
FoodOrderingSystem "1" o-- "many" DeliveryAssignment
class Money {
  <<value object>>
}
FoodOrderingSystem ..> Money
class Address {
  <<value object>>
}
FoodOrderingSystem ..> Address
class Quantity {
  <<value object>>
}
FoodOrderingSystem ..> Quantity
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as FoodOrderingSystemService
participant Repo as FoodOrderingSystemRepository
participant Policy as FoodOrderingSystemPolicy
participant Agg as FoodOrderingSystem
participant Outbox
Client->>Service: placeOrder(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: placeOrder(command)
Agg-->>Service: FoodOrderingSystemPlaceOrderEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.foodorderingsystem;

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

enum FoodOrderingSystemStatus {
    CREATED,
    ACCEPTED,
    PREPARING,
    READY_FOR_PICKUP,
    OUT_FOR_DELIVERY,
    DELIVERED,
    CANCELLED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record FoodOrderingSystemPlaceOrderEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record FoodOrderingSystemAcceptOrderEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record FoodOrderingSystemAssignCourierEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record FoodOrderingSystemCompleteDeliveryEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface FoodOrderingSystemCommand permits PlaceOrderCommand, AcceptOrderCommand, AssignCourierCommand, CompleteDeliveryCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record PlaceOrderCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements FoodOrderingSystemCommand {}
record AcceptOrderCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements FoodOrderingSystemCommand {}
record AssignCourierCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements FoodOrderingSystemCommand {}
record CompleteDeliveryCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements FoodOrderingSystemCommand {}

interface FoodOrderingSystemRepository {
    Optional<FoodOrderingSystem> findById(UUID id);
    void save(FoodOrderingSystem aggregate, long expectedVersion);
}

interface FoodOrderingSystemPolicy {
    Decision evaluate(FoodOrderingSystem aggregate, FoodOrderingSystemCommand command);
}

final class Restaurant {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class FoodOrderingSystem {
    private final UUID id;
    private final List<Restaurant> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private FoodOrderingSystemStatus status;
    private long version;

    FoodOrderingSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = FoodOrderingSystemStatus.CREATED;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    FoodOrderingSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void placeOrder(PlaceOrderCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run placeOrder when aggregate is terminal");
    this.status = FoodOrderingSystemStatus.ACCEPTED;
    this.version++;
    this.domainEvents.add(new FoodOrderingSystemPlaceOrderEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void acceptOrder(AcceptOrderCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run acceptOrder when aggregate is terminal");
    this.status = FoodOrderingSystemStatus.PREPARING;
    this.version++;
    this.domainEvents.add(new FoodOrderingSystemAcceptOrderEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void assignCourier(AssignCourierCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run assignCourier when aggregate is terminal");
    this.status = FoodOrderingSystemStatus.READY_FOR_PICKUP;
    this.version++;
    this.domainEvents.add(new FoodOrderingSystemAssignCourierEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void completeDelivery(CompleteDeliveryCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run completeDelivery when aggregate is terminal");
    this.status = FoodOrderingSystemStatus.OUT_FOR_DELIVERY;
    this.version++;
    this.domainEvents.add(new FoodOrderingSystemCompleteDeliveryEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == FoodOrderingSystemStatus.CANCELLED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class FoodOrderingSystemService {
    private final FoodOrderingSystemRepository repository;
    private final FoodOrderingSystemPolicy policy;
    private final Outbox outbox;

    FoodOrderingSystemService(FoodOrderingSystemRepository repository, FoodOrderingSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(FoodOrderingSystemCommand command) {
        FoodOrderingSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("FoodOrderingSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof PlaceOrderCommand c) aggregate.placeOrder(c);
        if (command instanceof AcceptOrderCommand c) aggregate.acceptOrder(c);
        if (command instanceof AssignCourierCommand c) aggregate.assignCourier(c);
        if (command instanceof CompleteDeliveryCommand c) aggregate.completeDelivery(c);
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

- Persist `FoodOrderingSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `FoodOrderingSystem` invariants and each command method.
- State-machine test all valid and invalid `FoodOrderingSystemStatus` transitions.
- Contract test every `FoodOrderingSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `FoodOrderingSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `FoodOrderingSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
