# 007. Design A Hotel Booking System

Source problem: `Design a hotel booking system.`  
Category: `Booking OOD`  
Primary focus: `availability, reservation state, pricing, cancellation`  
Archetype: `booking`

## 1. Interview Framing

Design `hotel booking system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `hotel booking system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `AVAILABLE, HELD, CONFIRMED, CHECKED_IN, CHECKED_OUT`.
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

- `Guest`
- `FrontDeskAgent`
- `PaymentProvider`

Primary use cases:

- `searchAvailability` command on `HotelBookingSystem`
- `holdRoom` command on `HotelBookingSystem`
- `confirmReservation` command on `HotelBookingSystem`
- `cancelReservation` command on `HotelBookingSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `HotelBookingSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Hotel, RoomType, Room, Reservation, RatePlan` | Have identity and change over time under the aggregate. |
| Value objects | `Money, DateRange, GuestProfile, ConfirmationCode` | Immutable concepts compared by value. |
| Policies | `HotelBookingSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `HotelBookingSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
AVAILABLE, HELD, CONFIRMED, CHECKED_IN, CHECKED_OUT, CANCELLED
```

Invariants:

- `HotelBookingSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.
- Money and capacity changes are atomic within the transaction boundary.
- A repeated idempotency key returns the original result and never double-applies side effects.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `HotelBookingSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `HotelBookingSystem` | Composes | Hotel, RoomType, Room | Owns invariants and lifecycle transitions. |
| `HotelBookingSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `HotelBookingSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class HotelBookingSystem {
  +UUID id
  +HotelBookingSystemStatus status
  +long version
  +validateInvariants()
}
class HotelBookingSystemService {
  +handle(command)
}
class HotelBookingSystemRepository {
  <<interface>>
  +findById(UUID id) HotelBookingSystem
  +save(HotelBookingSystem aggregate, long expectedVersion)
}
class HotelBookingSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
HotelBookingSystemService --> HotelBookingSystemRepository
HotelBookingSystemService --> HotelBookingSystemPolicy
HotelBookingSystemService --> HotelBookingSystem
class Hotel {
  +UUID id
  +validate()
}
HotelBookingSystem "1" o-- "many" Hotel
class RoomType {
  +UUID id
  +validate()
}
HotelBookingSystem "1" o-- "many" RoomType
class Room {
  +UUID id
  +validate()
}
HotelBookingSystem "1" o-- "many" Room
class Reservation {
  +UUID id
  +validate()
}
HotelBookingSystem "1" o-- "many" Reservation
class Money {
  <<value object>>
}
HotelBookingSystem ..> Money
class DateRange {
  <<value object>>
}
HotelBookingSystem ..> DateRange
class GuestProfile {
  <<value object>>
}
HotelBookingSystem ..> GuestProfile
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as HotelBookingSystemService
participant Repo as HotelBookingSystemRepository
participant Policy as HotelBookingSystemPolicy
participant Agg as HotelBookingSystem
participant Outbox
Client->>Service: searchAvailability(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: searchAvailability(command)
Agg-->>Service: HotelBookingSystemSearchAvailabilityEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |
| Strategy | Swap algorithms such as pricing, ranking, scheduling, matching, or retry without changing the aggregate. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.hotelbookingsystem;

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

enum HotelBookingSystemStatus {
    AVAILABLE,
    HELD,
    CONFIRMED,
    CHECKED_IN,
    CHECKED_OUT,
    CANCELLED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record HotelBookingSystemSearchAvailabilityEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record HotelBookingSystemHoldRoomEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record HotelBookingSystemConfirmReservationEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record HotelBookingSystemCancelReservationEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface HotelBookingSystemCommand permits SearchAvailabilityCommand, HoldRoomCommand, ConfirmReservationCommand, CancelReservationCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record SearchAvailabilityCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements HotelBookingSystemCommand {}
record HoldRoomCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements HotelBookingSystemCommand {}
record ConfirmReservationCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements HotelBookingSystemCommand {}
record CancelReservationCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements HotelBookingSystemCommand {}

interface HotelBookingSystemRepository {
    Optional<HotelBookingSystem> findById(UUID id);
    void save(HotelBookingSystem aggregate, long expectedVersion);
}

interface HotelBookingSystemPolicy {
    Decision evaluate(HotelBookingSystem aggregate, HotelBookingSystemCommand command);
}

final class Hotel {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class HotelBookingSystem {
    private final UUID id;
    private final List<Hotel> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private HotelBookingSystemStatus status;
    private long version;

    HotelBookingSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = HotelBookingSystemStatus.AVAILABLE;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    HotelBookingSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void searchAvailability(SearchAvailabilityCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run searchAvailability when aggregate is terminal");
    this.status = HotelBookingSystemStatus.HELD;
    this.version++;
    this.domainEvents.add(new HotelBookingSystemSearchAvailabilityEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void holdRoom(HoldRoomCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run holdRoom when aggregate is terminal");
    this.status = HotelBookingSystemStatus.CONFIRMED;
    this.version++;
    this.domainEvents.add(new HotelBookingSystemHoldRoomEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void confirmReservation(ConfirmReservationCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run confirmReservation when aggregate is terminal");
    this.status = HotelBookingSystemStatus.CHECKED_IN;
    this.version++;
    this.domainEvents.add(new HotelBookingSystemConfirmReservationEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void cancelReservation(CancelReservationCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run cancelReservation when aggregate is terminal");
    this.status = HotelBookingSystemStatus.CHECKED_OUT;
    this.version++;
    this.domainEvents.add(new HotelBookingSystemCancelReservationEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == HotelBookingSystemStatus.CANCELLED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class HotelBookingSystemService {
    private final HotelBookingSystemRepository repository;
    private final HotelBookingSystemPolicy policy;
    private final Outbox outbox;

    HotelBookingSystemService(HotelBookingSystemRepository repository, HotelBookingSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(HotelBookingSystemCommand command) {
        HotelBookingSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("HotelBookingSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof SearchAvailabilityCommand c) aggregate.searchAvailability(c);
        if (command instanceof HoldRoomCommand c) aggregate.holdRoom(c);
        if (command instanceof ConfirmReservationCommand c) aggregate.confirmReservation(c);
        if (command instanceof CancelReservationCommand c) aggregate.cancelReservation(c);
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

- Persist `HotelBookingSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `HotelBookingSystem` invariants and each command method.
- State-machine test all valid and invalid `HotelBookingSystemStatus` transitions.
- Contract test every `HotelBookingSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `HotelBookingSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `HotelBookingSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
