# 094. Design Warehouse Management System

Source problem: `Design warehouse management system.`  
Category: `Operations`  
Primary focus: `locations, picking, packing, inventory movements`  
Archetype: `domain`

## 1. Interview Framing

Design `warehouse management system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `warehouse management system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `RECEIVED, STORED, ALLOCATED, PICKED, PACKED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `WarehouseWorker`
- `InventoryPlanner`
- `Carrier`

Primary use cases:

- `receiveGoods` command on `WarehouseManagementSystem`
- `allocateInventory` command on `WarehouseManagementSystem`
- `pickItem` command on `WarehouseManagementSystem`
- `shipPackage` command on `WarehouseManagementSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `WarehouseManagementSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Warehouse, Location, InventoryItem, PickTask, Shipment` | Have identity and change over time under the aggregate. |
| Value objects | `SKU, LocationCode, Quantity, Barcode` | Immutable concepts compared by value. |
| Policies | `WarehouseManagementSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `WarehouseManagementSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
RECEIVED, STORED, ALLOCATED, PICKED, PACKED, SHIPPED
```

Invariants:

- `WarehouseManagementSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `WarehouseManagementSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `WarehouseManagementSystem` | Composes | Warehouse, Location, InventoryItem | Owns invariants and lifecycle transitions. |
| `WarehouseManagementSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `WarehouseManagementSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class WarehouseManagementSystem {
  +UUID id
  +WarehouseManagementSystemStatus status
  +long version
  +validateInvariants()
}
class WarehouseManagementSystemService {
  +handle(command)
}
class WarehouseManagementSystemRepository {
  <<interface>>
  +findById(UUID id) WarehouseManagementSystem
  +save(WarehouseManagementSystem aggregate, long expectedVersion)
}
class WarehouseManagementSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
WarehouseManagementSystemService --> WarehouseManagementSystemRepository
WarehouseManagementSystemService --> WarehouseManagementSystemPolicy
WarehouseManagementSystemService --> WarehouseManagementSystem
class Warehouse {
  +UUID id
  +validate()
}
WarehouseManagementSystem "1" o-- "many" Warehouse
class Location {
  +UUID id
  +validate()
}
WarehouseManagementSystem "1" o-- "many" Location
class InventoryItem {
  +UUID id
  +validate()
}
WarehouseManagementSystem "1" o-- "many" InventoryItem
class PickTask {
  +UUID id
  +validate()
}
WarehouseManagementSystem "1" o-- "many" PickTask
class SKU {
  <<value object>>
}
WarehouseManagementSystem ..> SKU
class LocationCode {
  <<value object>>
}
WarehouseManagementSystem ..> LocationCode
class Quantity {
  <<value object>>
}
WarehouseManagementSystem ..> Quantity
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as WarehouseManagementSystemService
participant Repo as WarehouseManagementSystemRepository
participant Policy as WarehouseManagementSystemPolicy
participant Agg as WarehouseManagementSystem
participant Outbox
Client->>Service: receiveGoods(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: receiveGoods(command)
Agg-->>Service: WarehouseManagementSystemReceiveGoodsEvent
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
package lld.warehousemanagementsystem;

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

enum WarehouseManagementSystemStatus {
    RECEIVED,
    STORED,
    ALLOCATED,
    PICKED,
    PACKED,
    SHIPPED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record WarehouseManagementSystemReceiveGoodsEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record WarehouseManagementSystemAllocateInventoryEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record WarehouseManagementSystemPickItemEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record WarehouseManagementSystemShipPackageEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface WarehouseManagementSystemCommand permits ReceiveGoodsCommand, AllocateInventoryCommand, PickItemCommand, ShipPackageCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record ReceiveGoodsCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements WarehouseManagementSystemCommand {}
record AllocateInventoryCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements WarehouseManagementSystemCommand {}
record PickItemCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements WarehouseManagementSystemCommand {}
record ShipPackageCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements WarehouseManagementSystemCommand {}

interface WarehouseManagementSystemRepository {
    Optional<WarehouseManagementSystem> findById(UUID id);
    void save(WarehouseManagementSystem aggregate, long expectedVersion);
}

interface WarehouseManagementSystemPolicy {
    Decision evaluate(WarehouseManagementSystem aggregate, WarehouseManagementSystemCommand command);
}

final class Warehouse {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class WarehouseManagementSystem {
    private final UUID id;
    private final List<Warehouse> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private WarehouseManagementSystemStatus status;
    private long version;

    WarehouseManagementSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = WarehouseManagementSystemStatus.RECEIVED;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    WarehouseManagementSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void receiveGoods(ReceiveGoodsCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run receiveGoods when aggregate is terminal");
    this.status = WarehouseManagementSystemStatus.STORED;
    this.version++;
    this.domainEvents.add(new WarehouseManagementSystemReceiveGoodsEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void allocateInventory(AllocateInventoryCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run allocateInventory when aggregate is terminal");
    this.status = WarehouseManagementSystemStatus.ALLOCATED;
    this.version++;
    this.domainEvents.add(new WarehouseManagementSystemAllocateInventoryEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void pickItem(PickItemCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run pickItem when aggregate is terminal");
    this.status = WarehouseManagementSystemStatus.PICKED;
    this.version++;
    this.domainEvents.add(new WarehouseManagementSystemPickItemEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void shipPackage(ShipPackageCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run shipPackage when aggregate is terminal");
    this.status = WarehouseManagementSystemStatus.PACKED;
    this.version++;
    this.domainEvents.add(new WarehouseManagementSystemShipPackageEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == WarehouseManagementSystemStatus.SHIPPED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class WarehouseManagementSystemService {
    private final WarehouseManagementSystemRepository repository;
    private final WarehouseManagementSystemPolicy policy;
    private final Outbox outbox;

    WarehouseManagementSystemService(WarehouseManagementSystemRepository repository, WarehouseManagementSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(WarehouseManagementSystemCommand command) {
        WarehouseManagementSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("WarehouseManagementSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof ReceiveGoodsCommand c) aggregate.receiveGoods(c);
        if (command instanceof AllocateInventoryCommand c) aggregate.allocateInventory(c);
        if (command instanceof PickItemCommand c) aggregate.pickItem(c);
        if (command instanceof ShipPackageCommand c) aggregate.shipPackage(c);
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

- Persist `WarehouseManagementSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `WarehouseManagementSystem` invariants and each command method.
- State-machine test all valid and invalid `WarehouseManagementSystemStatus` transitions.
- Contract test every `WarehouseManagementSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `WarehouseManagementSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `WarehouseManagementSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
