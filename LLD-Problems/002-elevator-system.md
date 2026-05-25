# 002. Design An Elevator System

Source problem: `Design an elevator system.`  
Category: `State machine`  
Primary focus: `scheduler, direction state, request queues, concurrency`  
Archetype: `state-workflow`

## 1. Interview Framing

Design `elevator system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `elevator system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `IDLE, MOVING_UP, MOVING_DOWN, DOOR_OPEN, DOOR_CLOSED`.
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

- `Passenger`
- `MaintenanceOperator`
- `Dispatcher`

Primary use cases:

- `registerHallCall` command on `ElevatorSystem`
- `assignCar` command on `ElevatorSystem`
- `openDoor` command on `ElevatorSystem`
- `completeTrip` command on `ElevatorSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `ElevatorSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `ElevatorCar, Floor, HallCall, CarCall, Scheduler` | Have identity and change over time under the aggregate. |
| Value objects | `Direction, FloorNumber, Capacity, TimeWindow` | Immutable concepts compared by value. |
| Policies | `ElevatorSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `ElevatorSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
IDLE, MOVING_UP, MOVING_DOWN, DOOR_OPEN, DOOR_CLOSED, MAINTENANCE
```

Invariants:

- `ElevatorSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `ElevatorSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `ElevatorSystem` | Composes | ElevatorCar, Floor, HallCall | Owns invariants and lifecycle transitions. |
| `ElevatorSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `ElevatorSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class ElevatorSystem {
  +UUID id
  +ElevatorSystemStatus status
  +long version
  +validateInvariants()
}
class ElevatorSystemService {
  +handle(command)
}
class ElevatorSystemRepository {
  <<interface>>
  +findById(UUID id) ElevatorSystem
  +save(ElevatorSystem aggregate, long expectedVersion)
}
class ElevatorSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
ElevatorSystemService --> ElevatorSystemRepository
ElevatorSystemService --> ElevatorSystemPolicy
ElevatorSystemService --> ElevatorSystem
class ElevatorCar {
  +UUID id
  +validate()
}
ElevatorSystem "1" o-- "many" ElevatorCar
class Floor {
  +UUID id
  +validate()
}
ElevatorSystem "1" o-- "many" Floor
class HallCall {
  +UUID id
  +validate()
}
ElevatorSystem "1" o-- "many" HallCall
class CarCall {
  +UUID id
  +validate()
}
ElevatorSystem "1" o-- "many" CarCall
class Direction {
  <<value object>>
}
ElevatorSystem ..> Direction
class FloorNumber {
  <<value object>>
}
ElevatorSystem ..> FloorNumber
class Capacity {
  <<value object>>
}
ElevatorSystem ..> Capacity
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as ElevatorSystemService
participant Repo as ElevatorSystemRepository
participant Policy as ElevatorSystemPolicy
participant Agg as ElevatorSystem
participant Outbox
Client->>Service: registerHallCall(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: registerHallCall(command)
Agg-->>Service: ElevatorSystemRegisterHallCallEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |
| Strategy | Swap algorithms such as pricing, ranking, scheduling, matching, or retry without changing the aggregate. |
| Command | Represent user or system intent as retryable, auditable, and optionally undoable objects. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.elevatorsystem;

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

enum ElevatorSystemStatus {
    IDLE,
    MOVING_UP,
    MOVING_DOWN,
    DOOR_OPEN,
    DOOR_CLOSED,
    MAINTENANCE
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record ElevatorSystemRegisterHallCallEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ElevatorSystemAssignCarEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ElevatorSystemOpenDoorEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ElevatorSystemCompleteTripEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface ElevatorSystemCommand permits RegisterHallCallCommand, AssignCarCommand, OpenDoorCommand, CompleteTripCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record RegisterHallCallCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ElevatorSystemCommand {}
record AssignCarCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ElevatorSystemCommand {}
record OpenDoorCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ElevatorSystemCommand {}
record CompleteTripCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ElevatorSystemCommand {}

interface ElevatorSystemRepository {
    Optional<ElevatorSystem> findById(UUID id);
    void save(ElevatorSystem aggregate, long expectedVersion);
}

interface ElevatorSystemPolicy {
    Decision evaluate(ElevatorSystem aggregate, ElevatorSystemCommand command);
}

final class ElevatorCar {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class ElevatorSystem {
    private final UUID id;
    private final List<ElevatorCar> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private ElevatorSystemStatus status;
    private long version;

    ElevatorSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = ElevatorSystemStatus.IDLE;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    ElevatorSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void registerHallCall(RegisterHallCallCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run registerHallCall when aggregate is terminal");
    this.status = ElevatorSystemStatus.MOVING_UP;
    this.version++;
    this.domainEvents.add(new ElevatorSystemRegisterHallCallEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void assignCar(AssignCarCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run assignCar when aggregate is terminal");
    this.status = ElevatorSystemStatus.MOVING_DOWN;
    this.version++;
    this.domainEvents.add(new ElevatorSystemAssignCarEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void openDoor(OpenDoorCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run openDoor when aggregate is terminal");
    this.status = ElevatorSystemStatus.DOOR_OPEN;
    this.version++;
    this.domainEvents.add(new ElevatorSystemOpenDoorEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void completeTrip(CompleteTripCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run completeTrip when aggregate is terminal");
    this.status = ElevatorSystemStatus.DOOR_CLOSED;
    this.version++;
    this.domainEvents.add(new ElevatorSystemCompleteTripEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == ElevatorSystemStatus.MAINTENANCE;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class ElevatorSystemService {
    private final ElevatorSystemRepository repository;
    private final ElevatorSystemPolicy policy;
    private final Outbox outbox;

    ElevatorSystemService(ElevatorSystemRepository repository, ElevatorSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(ElevatorSystemCommand command) {
        ElevatorSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("ElevatorSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof RegisterHallCallCommand c) aggregate.registerHallCall(c);
        if (command instanceof AssignCarCommand c) aggregate.assignCar(c);
        if (command instanceof OpenDoorCommand c) aggregate.openDoor(c);
        if (command instanceof CompleteTripCommand c) aggregate.completeTrip(c);
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

- Persist `ElevatorSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Swap algorithms such as pricing, ranking, scheduling, matching, or retry without changing the aggregate. | `Strategy` |
| Represent user or system intent as retryable, auditable, and optionally undoable objects. | `Command` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `ElevatorSystem` invariants and each command method.
- State-machine test all valid and invalid `ElevatorSystemStatus` transitions.
- Contract test every `ElevatorSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `ElevatorSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `ElevatorSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
