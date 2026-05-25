# 010. Design A Car Rental System

Source problem: `Design a car rental system.`  
Category: `Rental OOD`  
Primary focus: `vehicle fleet, pricing, availability, pickup/return workflow`  
Archetype: `booking`

## 1. Interview Framing

Design `car rental system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `car rental system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `AVAILABLE, RESERVED, PICKED_UP, IN_USE, RETURNED`.
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
- `FleetManager`
- `PaymentProvider`

Primary use cases:

- `reserveVehicle` command on `CarRentalSystem`
- `pickupVehicle` command on `CarRentalSystem`
- `extendRental` command on `CarRentalSystem`
- `returnVehicle` command on `CarRentalSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `CarRentalSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Vehicle, Branch, Reservation, RentalAgreement, InspectionReport` | Have identity and change over time under the aggregate. |
| Value objects | `Money, DateRange, LicenseNumber, Odometer` | Immutable concepts compared by value. |
| Policies | `CarRentalSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `CarRentalSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
AVAILABLE, RESERVED, PICKED_UP, IN_USE, RETURNED, MAINTENANCE
```

Invariants:

- `CarRentalSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.
- Money and capacity changes are atomic within the transaction boundary.
- A repeated idempotency key returns the original result and never double-applies side effects.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `CarRentalSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `CarRentalSystem` | Composes | Vehicle, Branch, Reservation | Owns invariants and lifecycle transitions. |
| `CarRentalSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `CarRentalSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class CarRentalSystem {
  +UUID id
  +CarRentalSystemStatus status
  +long version
  +validateInvariants()
}
class CarRentalSystemService {
  +handle(command)
}
class CarRentalSystemRepository {
  <<interface>>
  +findById(UUID id) CarRentalSystem
  +save(CarRentalSystem aggregate, long expectedVersion)
}
class CarRentalSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
CarRentalSystemService --> CarRentalSystemRepository
CarRentalSystemService --> CarRentalSystemPolicy
CarRentalSystemService --> CarRentalSystem
class Vehicle {
  +UUID id
  +validate()
}
CarRentalSystem "1" o-- "many" Vehicle
class Branch {
  +UUID id
  +validate()
}
CarRentalSystem "1" o-- "many" Branch
class Reservation {
  +UUID id
  +validate()
}
CarRentalSystem "1" o-- "many" Reservation
class RentalAgreement {
  +UUID id
  +validate()
}
CarRentalSystem "1" o-- "many" RentalAgreement
class Money {
  <<value object>>
}
CarRentalSystem ..> Money
class DateRange {
  <<value object>>
}
CarRentalSystem ..> DateRange
class LicenseNumber {
  <<value object>>
}
CarRentalSystem ..> LicenseNumber
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as CarRentalSystemService
participant Repo as CarRentalSystemRepository
participant Policy as CarRentalSystemPolicy
participant Agg as CarRentalSystem
participant Outbox
Client->>Service: reserveVehicle(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: reserveVehicle(command)
Agg-->>Service: CarRentalSystemReserveVehicleEvent
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
| Repository | Keep persistence and optimistic version checks outside the domain model. |
| Saga / Process Manager | Coordinate multi-step workflows and compensation across payment, inventory, delivery, or approvals. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.carrentalsystem;

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

enum CarRentalSystemStatus {
    AVAILABLE,
    RESERVED,
    PICKED_UP,
    IN_USE,
    RETURNED,
    MAINTENANCE
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record CarRentalSystemReserveVehicleEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record CarRentalSystemPickupVehicleEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record CarRentalSystemExtendRentalEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record CarRentalSystemReturnVehicleEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface CarRentalSystemCommand permits ReserveVehicleCommand, PickupVehicleCommand, ExtendRentalCommand, ReturnVehicleCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record ReserveVehicleCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CarRentalSystemCommand {}
record PickupVehicleCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CarRentalSystemCommand {}
record ExtendRentalCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CarRentalSystemCommand {}
record ReturnVehicleCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CarRentalSystemCommand {}

interface CarRentalSystemRepository {
    Optional<CarRentalSystem> findById(UUID id);
    void save(CarRentalSystem aggregate, long expectedVersion);
}

interface CarRentalSystemPolicy {
    Decision evaluate(CarRentalSystem aggregate, CarRentalSystemCommand command);
}

final class Vehicle {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class CarRentalSystem {
    private final UUID id;
    private final List<Vehicle> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private CarRentalSystemStatus status;
    private long version;

    CarRentalSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = CarRentalSystemStatus.AVAILABLE;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    CarRentalSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void reserveVehicle(ReserveVehicleCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run reserveVehicle when aggregate is terminal");
    this.status = CarRentalSystemStatus.RESERVED;
    this.version++;
    this.domainEvents.add(new CarRentalSystemReserveVehicleEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void pickupVehicle(PickupVehicleCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run pickupVehicle when aggregate is terminal");
    this.status = CarRentalSystemStatus.PICKED_UP;
    this.version++;
    this.domainEvents.add(new CarRentalSystemPickupVehicleEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void extendRental(ExtendRentalCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run extendRental when aggregate is terminal");
    this.status = CarRentalSystemStatus.IN_USE;
    this.version++;
    this.domainEvents.add(new CarRentalSystemExtendRentalEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void returnVehicle(ReturnVehicleCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run returnVehicle when aggregate is terminal");
    this.status = CarRentalSystemStatus.RETURNED;
    this.version++;
    this.domainEvents.add(new CarRentalSystemReturnVehicleEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == CarRentalSystemStatus.MAINTENANCE;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class CarRentalSystemService {
    private final CarRentalSystemRepository repository;
    private final CarRentalSystemPolicy policy;
    private final Outbox outbox;

    CarRentalSystemService(CarRentalSystemRepository repository, CarRentalSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(CarRentalSystemCommand command) {
        CarRentalSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("CarRentalSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof ReserveVehicleCommand c) aggregate.reserveVehicle(c);
        if (command instanceof PickupVehicleCommand c) aggregate.pickupVehicle(c);
        if (command instanceof ExtendRentalCommand c) aggregate.extendRental(c);
        if (command instanceof ReturnVehicleCommand c) aggregate.returnVehicle(c);
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

- Persist `CarRentalSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| Coordinate multi-step workflows and compensation across payment, inventory, delivery, or approvals. | `Saga / Process Manager` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `CarRentalSystem` invariants and each command method.
- State-machine test all valid and invalid `CarRentalSystemStatus` transitions.
- Contract test every `CarRentalSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `CarRentalSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `CarRentalSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
