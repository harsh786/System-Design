# 093. Design Restaurant Management System

Source problem: `Design restaurant management system.`  
Category: `Operations`  
Primary focus: `tables, orders, kitchen queue, billing`  
Archetype: `domain`

## 1. Interview Framing

Design `restaurant management system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `restaurant management system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `TABLE_AVAILABLE, SEATED, ORDERED, COOKING, SERVED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `Server`
- `Chef`
- `Customer`
- `Cashier`

Primary use cases:

- `seatParty` command on `RestaurantManagementSystem`
- `takeOrder` command on `RestaurantManagementSystem`
- `routeToKitchen` command on `RestaurantManagementSystem`
- `closeBill` command on `RestaurantManagementSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `RestaurantManagementSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Table, DiningOrder, KitchenTicket, MenuItem, Bill` | Have identity and change over time under the aggregate. |
| Value objects | `TableNumber, Money, Quantity, OrderNumber` | Immutable concepts compared by value. |
| Policies | `RestaurantManagementSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `RestaurantManagementSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
TABLE_AVAILABLE, SEATED, ORDERED, COOKING, SERVED, PAID
```

Invariants:

- `RestaurantManagementSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `RestaurantManagementSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `RestaurantManagementSystem` | Composes | Table, DiningOrder, KitchenTicket | Owns invariants and lifecycle transitions. |
| `RestaurantManagementSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `RestaurantManagementSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class RestaurantManagementSystem {
  +UUID id
  +RestaurantManagementSystemStatus status
  +long version
  +validateInvariants()
}
class RestaurantManagementSystemService {
  +handle(command)
}
class RestaurantManagementSystemRepository {
  <<interface>>
  +findById(UUID id) RestaurantManagementSystem
  +save(RestaurantManagementSystem aggregate, long expectedVersion)
}
class RestaurantManagementSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
RestaurantManagementSystemService --> RestaurantManagementSystemRepository
RestaurantManagementSystemService --> RestaurantManagementSystemPolicy
RestaurantManagementSystemService --> RestaurantManagementSystem
class Table {
  +UUID id
  +validate()
}
RestaurantManagementSystem "1" o-- "many" Table
class DiningOrder {
  +UUID id
  +validate()
}
RestaurantManagementSystem "1" o-- "many" DiningOrder
class KitchenTicket {
  +UUID id
  +validate()
}
RestaurantManagementSystem "1" o-- "many" KitchenTicket
class MenuItem {
  +UUID id
  +validate()
}
RestaurantManagementSystem "1" o-- "many" MenuItem
class TableNumber {
  <<value object>>
}
RestaurantManagementSystem ..> TableNumber
class Money {
  <<value object>>
}
RestaurantManagementSystem ..> Money
class Quantity {
  <<value object>>
}
RestaurantManagementSystem ..> Quantity
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as RestaurantManagementSystemService
participant Repo as RestaurantManagementSystemRepository
participant Policy as RestaurantManagementSystemPolicy
participant Agg as RestaurantManagementSystem
participant Outbox
Client->>Service: seatParty(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: seatParty(command)
Agg-->>Service: RestaurantManagementSystemSeatPartyEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.restaurantmanagementsystem;

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

enum RestaurantManagementSystemStatus {
    TABLE_AVAILABLE,
    SEATED,
    ORDERED,
    COOKING,
    SERVED,
    PAID
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record RestaurantManagementSystemSeatPartyEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record RestaurantManagementSystemTakeOrderEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record RestaurantManagementSystemRouteToKitchenEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record RestaurantManagementSystemCloseBillEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface RestaurantManagementSystemCommand permits SeatPartyCommand, TakeOrderCommand, RouteToKitchenCommand, CloseBillCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record SeatPartyCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RestaurantManagementSystemCommand {}
record TakeOrderCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RestaurantManagementSystemCommand {}
record RouteToKitchenCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RestaurantManagementSystemCommand {}
record CloseBillCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RestaurantManagementSystemCommand {}

interface RestaurantManagementSystemRepository {
    Optional<RestaurantManagementSystem> findById(UUID id);
    void save(RestaurantManagementSystem aggregate, long expectedVersion);
}

interface RestaurantManagementSystemPolicy {
    Decision evaluate(RestaurantManagementSystem aggregate, RestaurantManagementSystemCommand command);
}

final class Table {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class RestaurantManagementSystem {
    private final UUID id;
    private final List<Table> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private RestaurantManagementSystemStatus status;
    private long version;

    RestaurantManagementSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = RestaurantManagementSystemStatus.TABLE_AVAILABLE;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    RestaurantManagementSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void seatParty(SeatPartyCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run seatParty when aggregate is terminal");
    this.status = RestaurantManagementSystemStatus.SEATED;
    this.version++;
    this.domainEvents.add(new RestaurantManagementSystemSeatPartyEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void takeOrder(TakeOrderCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run takeOrder when aggregate is terminal");
    this.status = RestaurantManagementSystemStatus.ORDERED;
    this.version++;
    this.domainEvents.add(new RestaurantManagementSystemTakeOrderEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void routeToKitchen(RouteToKitchenCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run routeToKitchen when aggregate is terminal");
    this.status = RestaurantManagementSystemStatus.COOKING;
    this.version++;
    this.domainEvents.add(new RestaurantManagementSystemRouteToKitchenEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void closeBill(CloseBillCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run closeBill when aggregate is terminal");
    this.status = RestaurantManagementSystemStatus.SERVED;
    this.version++;
    this.domainEvents.add(new RestaurantManagementSystemCloseBillEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == RestaurantManagementSystemStatus.PAID;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class RestaurantManagementSystemService {
    private final RestaurantManagementSystemRepository repository;
    private final RestaurantManagementSystemPolicy policy;
    private final Outbox outbox;

    RestaurantManagementSystemService(RestaurantManagementSystemRepository repository, RestaurantManagementSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(RestaurantManagementSystemCommand command) {
        RestaurantManagementSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("RestaurantManagementSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof SeatPartyCommand c) aggregate.seatParty(c);
        if (command instanceof TakeOrderCommand c) aggregate.takeOrder(c);
        if (command instanceof RouteToKitchenCommand c) aggregate.routeToKitchen(c);
        if (command instanceof CloseBillCommand c) aggregate.closeBill(c);
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

- Persist `RestaurantManagementSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
- Persist child entities in owned tables/documents keyed by aggregate id.
- Store domain events in an outbox table in the same transaction.
- Add indexes for business lookup keys, active state, owner/user id, and expiry deadlines.

## 13. Error Handling And Idempotency

- Return typed domain errors: `NotFound`, `InvalidState`, `PolicyRejected`, `Conflict`, and `DuplicateCommand`.
- Never partially mutate aggregate state before all guards pass.
- Log rejection reasons with correlation id; avoid logging secrets, tokens, or sensitive payloads.

## 14. Extensibility Hooks

| Change point | Extension mechanism |
|---|---|
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `RestaurantManagementSystem` invariants and each command method.
- State-machine test all valid and invalid `RestaurantManagementSystemStatus` transitions.
- Contract test every `RestaurantManagementSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `RestaurantManagementSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `RestaurantManagementSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
