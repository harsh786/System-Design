# 008. Design An Airline Reservation System

Source problem: `Design an airline reservation system.`  
Category: `Booking OOD`  
Primary focus: `seat inventory, fare classes, holds, payment timeout`  
Archetype: `booking`

## 1. Interview Framing

Design `airline reservation system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `airline reservation system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `AVAILABLE, HELD, TICKETED, CHECKED_IN, BOARDED`.
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

- `Traveler`
- `Agent`
- `PaymentProvider`

Primary use cases:

- `searchFlights` command on `AirlineReservationSystem`
- `holdSeat` command on `AirlineReservationSystem`
- `ticketItinerary` command on `AirlineReservationSystem`
- `releaseHold` command on `AirlineReservationSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `AirlineReservationSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Flight, Seat, FareClass, Itinerary, Ticket` | Have identity and change over time under the aggregate. |
| Value objects | `Money, Route, SeatNumber, PassengerName` | Immutable concepts compared by value. |
| Policies | `AirlineReservationSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `AirlineReservationSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
AVAILABLE, HELD, TICKETED, CHECKED_IN, BOARDED, CANCELLED
```

Invariants:

- `AirlineReservationSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.
- Money and capacity changes are atomic within the transaction boundary.
- A repeated idempotency key returns the original result and never double-applies side effects.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `AirlineReservationSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `AirlineReservationSystem` | Composes | Flight, Seat, FareClass | Owns invariants and lifecycle transitions. |
| `AirlineReservationSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `AirlineReservationSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class AirlineReservationSystem {
  +UUID id
  +AirlineReservationSystemStatus status
  +long version
  +validateInvariants()
}
class AirlineReservationSystemService {
  +handle(command)
}
class AirlineReservationSystemRepository {
  <<interface>>
  +findById(UUID id) AirlineReservationSystem
  +save(AirlineReservationSystem aggregate, long expectedVersion)
}
class AirlineReservationSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
AirlineReservationSystemService --> AirlineReservationSystemRepository
AirlineReservationSystemService --> AirlineReservationSystemPolicy
AirlineReservationSystemService --> AirlineReservationSystem
class Flight {
  +UUID id
  +validate()
}
AirlineReservationSystem "1" o-- "many" Flight
class Seat {
  +UUID id
  +validate()
}
AirlineReservationSystem "1" o-- "many" Seat
class FareClass {
  +UUID id
  +validate()
}
AirlineReservationSystem "1" o-- "many" FareClass
class Itinerary {
  +UUID id
  +validate()
}
AirlineReservationSystem "1" o-- "many" Itinerary
class Money {
  <<value object>>
}
AirlineReservationSystem ..> Money
class Route {
  <<value object>>
}
AirlineReservationSystem ..> Route
class SeatNumber {
  <<value object>>
}
AirlineReservationSystem ..> SeatNumber
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as AirlineReservationSystemService
participant Repo as AirlineReservationSystemRepository
participant Policy as AirlineReservationSystemPolicy
participant Agg as AirlineReservationSystem
participant Outbox
Client->>Service: searchFlights(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: searchFlights(command)
Agg-->>Service: AirlineReservationSystemSearchFlightsEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.airlinereservationsystem;

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

enum AirlineReservationSystemStatus {
    AVAILABLE,
    HELD,
    TICKETED,
    CHECKED_IN,
    BOARDED,
    CANCELLED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record AirlineReservationSystemSearchFlightsEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record AirlineReservationSystemHoldSeatEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record AirlineReservationSystemTicketItineraryEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record AirlineReservationSystemReleaseHoldEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface AirlineReservationSystemCommand permits SearchFlightsCommand, HoldSeatCommand, TicketItineraryCommand, ReleaseHoldCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record SearchFlightsCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements AirlineReservationSystemCommand {}
record HoldSeatCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements AirlineReservationSystemCommand {}
record TicketItineraryCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements AirlineReservationSystemCommand {}
record ReleaseHoldCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements AirlineReservationSystemCommand {}

interface AirlineReservationSystemRepository {
    Optional<AirlineReservationSystem> findById(UUID id);
    void save(AirlineReservationSystem aggregate, long expectedVersion);
}

interface AirlineReservationSystemPolicy {
    Decision evaluate(AirlineReservationSystem aggregate, AirlineReservationSystemCommand command);
}

final class Flight {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class AirlineReservationSystem {
    private final UUID id;
    private final List<Flight> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private AirlineReservationSystemStatus status;
    private long version;

    AirlineReservationSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = AirlineReservationSystemStatus.AVAILABLE;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    AirlineReservationSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void searchFlights(SearchFlightsCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run searchFlights when aggregate is terminal");
    this.status = AirlineReservationSystemStatus.HELD;
    this.version++;
    this.domainEvents.add(new AirlineReservationSystemSearchFlightsEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void holdSeat(HoldSeatCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run holdSeat when aggregate is terminal");
    this.status = AirlineReservationSystemStatus.TICKETED;
    this.version++;
    this.domainEvents.add(new AirlineReservationSystemHoldSeatEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void ticketItinerary(TicketItineraryCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run ticketItinerary when aggregate is terminal");
    this.status = AirlineReservationSystemStatus.CHECKED_IN;
    this.version++;
    this.domainEvents.add(new AirlineReservationSystemTicketItineraryEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void releaseHold(ReleaseHoldCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run releaseHold when aggregate is terminal");
    this.status = AirlineReservationSystemStatus.BOARDED;
    this.version++;
    this.domainEvents.add(new AirlineReservationSystemReleaseHoldEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == AirlineReservationSystemStatus.CANCELLED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class AirlineReservationSystemService {
    private final AirlineReservationSystemRepository repository;
    private final AirlineReservationSystemPolicy policy;
    private final Outbox outbox;

    AirlineReservationSystemService(AirlineReservationSystemRepository repository, AirlineReservationSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(AirlineReservationSystemCommand command) {
        AirlineReservationSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("AirlineReservationSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof SearchFlightsCommand c) aggregate.searchFlights(c);
        if (command instanceof HoldSeatCommand c) aggregate.holdSeat(c);
        if (command instanceof TicketItineraryCommand c) aggregate.ticketItinerary(c);
        if (command instanceof ReleaseHoldCommand c) aggregate.releaseHold(c);
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

- Persist `AirlineReservationSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `AirlineReservationSystem` invariants and each command method.
- State-machine test all valid and invalid `AirlineReservationSystemStatus` transitions.
- Contract test every `AirlineReservationSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `AirlineReservationSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `AirlineReservationSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
