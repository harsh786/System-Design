# 009. Design A Movie Ticket Booking System

Source problem: `Design a movie ticket booking system.`  
Category: `Booking OOD`  
Primary focus: `seat locking, concurrency, payment expiry, fairness`  
Archetype: `booking`

## 1. Interview Framing

Design `movie ticket booking system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `movie ticket booking system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `AVAILABLE, LOCKED, BOOKED, PAYMENT_PENDING, EXPIRED`.
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

- `Moviegoer`
- `TheaterAdmin`
- `PaymentProvider`

Primary use cases:

- `lockSeats` command on `MovieTicketBookingSystem`
- `confirmPayment` command on `MovieTicketBookingSystem`
- `issueTickets` command on `MovieTicketBookingSystem`
- `expireHold` command on `MovieTicketBookingSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `MovieTicketBookingSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Show, Screen, Seat, SeatHold, Booking` | Have identity and change over time under the aggregate. |
| Value objects | `Money, SeatNumber, TimeRange, BookingCode` | Immutable concepts compared by value. |
| Policies | `MovieTicketBookingSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `MovieTicketBookingSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
AVAILABLE, LOCKED, BOOKED, PAYMENT_PENDING, EXPIRED, CANCELLED
```

Invariants:

- `MovieTicketBookingSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.
- Money and capacity changes are atomic within the transaction boundary.
- A repeated idempotency key returns the original result and never double-applies side effects.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `MovieTicketBookingSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `MovieTicketBookingSystem` | Composes | Show, Screen, Seat | Owns invariants and lifecycle transitions. |
| `MovieTicketBookingSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `MovieTicketBookingSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class MovieTicketBookingSystem {
  +UUID id
  +MovieTicketBookingSystemStatus status
  +long version
  +validateInvariants()
}
class MovieTicketBookingSystemService {
  +handle(command)
}
class MovieTicketBookingSystemRepository {
  <<interface>>
  +findById(UUID id) MovieTicketBookingSystem
  +save(MovieTicketBookingSystem aggregate, long expectedVersion)
}
class MovieTicketBookingSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
MovieTicketBookingSystemService --> MovieTicketBookingSystemRepository
MovieTicketBookingSystemService --> MovieTicketBookingSystemPolicy
MovieTicketBookingSystemService --> MovieTicketBookingSystem
class Show {
  +UUID id
  +validate()
}
MovieTicketBookingSystem "1" o-- "many" Show
class Screen {
  +UUID id
  +validate()
}
MovieTicketBookingSystem "1" o-- "many" Screen
class Seat {
  +UUID id
  +validate()
}
MovieTicketBookingSystem "1" o-- "many" Seat
class SeatHold {
  +UUID id
  +validate()
}
MovieTicketBookingSystem "1" o-- "many" SeatHold
class Money {
  <<value object>>
}
MovieTicketBookingSystem ..> Money
class SeatNumber {
  <<value object>>
}
MovieTicketBookingSystem ..> SeatNumber
class TimeRange {
  <<value object>>
}
MovieTicketBookingSystem ..> TimeRange
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as MovieTicketBookingSystemService
participant Repo as MovieTicketBookingSystemRepository
participant Policy as MovieTicketBookingSystemPolicy
participant Agg as MovieTicketBookingSystem
participant Outbox
Client->>Service: lockSeats(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: lockSeats(command)
Agg-->>Service: MovieTicketBookingSystemLockSeatsEvent
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
package lld.movieticketbookingsystem;

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

enum MovieTicketBookingSystemStatus {
    AVAILABLE,
    LOCKED,
    BOOKED,
    PAYMENT_PENDING,
    EXPIRED,
    CANCELLED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record MovieTicketBookingSystemLockSeatsEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record MovieTicketBookingSystemConfirmPaymentEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record MovieTicketBookingSystemIssueTicketsEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record MovieTicketBookingSystemExpireHoldEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface MovieTicketBookingSystemCommand permits LockSeatsCommand, ConfirmPaymentCommand, IssueTicketsCommand, ExpireHoldCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record LockSeatsCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements MovieTicketBookingSystemCommand {}
record ConfirmPaymentCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements MovieTicketBookingSystemCommand {}
record IssueTicketsCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements MovieTicketBookingSystemCommand {}
record ExpireHoldCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements MovieTicketBookingSystemCommand {}

interface MovieTicketBookingSystemRepository {
    Optional<MovieTicketBookingSystem> findById(UUID id);
    void save(MovieTicketBookingSystem aggregate, long expectedVersion);
}

interface MovieTicketBookingSystemPolicy {
    Decision evaluate(MovieTicketBookingSystem aggregate, MovieTicketBookingSystemCommand command);
}

final class Show {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class MovieTicketBookingSystem {
    private final UUID id;
    private final List<Show> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private MovieTicketBookingSystemStatus status;
    private long version;

    MovieTicketBookingSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = MovieTicketBookingSystemStatus.AVAILABLE;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    MovieTicketBookingSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void lockSeats(LockSeatsCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run lockSeats when aggregate is terminal");
    this.status = MovieTicketBookingSystemStatus.LOCKED;
    this.version++;
    this.domainEvents.add(new MovieTicketBookingSystemLockSeatsEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void confirmPayment(ConfirmPaymentCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run confirmPayment when aggregate is terminal");
    this.status = MovieTicketBookingSystemStatus.BOOKED;
    this.version++;
    this.domainEvents.add(new MovieTicketBookingSystemConfirmPaymentEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void issueTickets(IssueTicketsCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run issueTickets when aggregate is terminal");
    this.status = MovieTicketBookingSystemStatus.PAYMENT_PENDING;
    this.version++;
    this.domainEvents.add(new MovieTicketBookingSystemIssueTicketsEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void expireHold(ExpireHoldCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run expireHold when aggregate is terminal");
    this.status = MovieTicketBookingSystemStatus.EXPIRED;
    this.version++;
    this.domainEvents.add(new MovieTicketBookingSystemExpireHoldEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == MovieTicketBookingSystemStatus.CANCELLED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class MovieTicketBookingSystemService {
    private final MovieTicketBookingSystemRepository repository;
    private final MovieTicketBookingSystemPolicy policy;
    private final Outbox outbox;

    MovieTicketBookingSystemService(MovieTicketBookingSystemRepository repository, MovieTicketBookingSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(MovieTicketBookingSystemCommand command) {
        MovieTicketBookingSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("MovieTicketBookingSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof LockSeatsCommand c) aggregate.lockSeats(c);
        if (command instanceof ConfirmPaymentCommand c) aggregate.confirmPayment(c);
        if (command instanceof IssueTicketsCommand c) aggregate.issueTickets(c);
        if (command instanceof ExpireHoldCommand c) aggregate.expireHold(c);
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

- Persist `MovieTicketBookingSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `MovieTicketBookingSystem` invariants and each command method.
- State-machine test all valid and invalid `MovieTicketBookingSystemStatus` transitions.
- Contract test every `MovieTicketBookingSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `MovieTicketBookingSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `MovieTicketBookingSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
