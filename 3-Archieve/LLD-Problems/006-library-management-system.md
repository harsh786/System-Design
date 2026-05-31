# 006. Design A Library Management System

Source problem: `Design a library management system.`  
Category: `Domain modeling`  
Primary focus: `catalog, loans, reservations, fines, policies`  
Archetype: `domain`

## 1. Interview Framing

Design `library management system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `library management system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `AVAILABLE, ON_LOAN, RESERVED, LOST, OVERDUE`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `Member`
- `Librarian`
- `NotificationProvider`

Primary use cases:

- `checkoutCopy` command on `LibraryManagementSystem`
- `returnCopy` command on `LibraryManagementSystem`
- `placeHold` command on `LibraryManagementSystem`
- `assessFine` command on `LibraryManagementSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `LibraryManagementSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `BookTitle, BookCopy, Loan, Reservation, Fine` | Have identity and change over time under the aggregate. |
| Value objects | `ISBN, Money, DateRange, MemberId` | Immutable concepts compared by value. |
| Policies | `LibraryManagementSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `LibraryManagementSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
AVAILABLE, ON_LOAN, RESERVED, LOST, OVERDUE, ARCHIVED
```

Invariants:

- `LibraryManagementSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `LibraryManagementSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `LibraryManagementSystem` | Composes | BookTitle, BookCopy, Loan | Owns invariants and lifecycle transitions. |
| `LibraryManagementSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `LibraryManagementSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class LibraryManagementSystem {
  +UUID id
  +LibraryManagementSystemStatus status
  +long version
  +validateInvariants()
}
class LibraryManagementSystemService {
  +handle(command)
}
class LibraryManagementSystemRepository {
  <<interface>>
  +findById(UUID id) LibraryManagementSystem
  +save(LibraryManagementSystem aggregate, long expectedVersion)
}
class LibraryManagementSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
LibraryManagementSystemService --> LibraryManagementSystemRepository
LibraryManagementSystemService --> LibraryManagementSystemPolicy
LibraryManagementSystemService --> LibraryManagementSystem
class BookTitle {
  +UUID id
  +validate()
}
LibraryManagementSystem "1" o-- "many" BookTitle
class BookCopy {
  +UUID id
  +validate()
}
LibraryManagementSystem "1" o-- "many" BookCopy
class Loan {
  +UUID id
  +validate()
}
LibraryManagementSystem "1" o-- "many" Loan
class Reservation {
  +UUID id
  +validate()
}
LibraryManagementSystem "1" o-- "many" Reservation
class ISBN {
  <<value object>>
}
LibraryManagementSystem ..> ISBN
class Money {
  <<value object>>
}
LibraryManagementSystem ..> Money
class DateRange {
  <<value object>>
}
LibraryManagementSystem ..> DateRange
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as LibraryManagementSystemService
participant Repo as LibraryManagementSystemRepository
participant Policy as LibraryManagementSystemPolicy
participant Agg as LibraryManagementSystem
participant Outbox
Client->>Service: checkoutCopy(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: checkoutCopy(command)
Agg-->>Service: LibraryManagementSystemCheckoutCopyEvent
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
package lld.librarymanagementsystem;

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

enum LibraryManagementSystemStatus {
    AVAILABLE,
    ON_LOAN,
    RESERVED,
    LOST,
    OVERDUE,
    ARCHIVED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record LibraryManagementSystemCheckoutCopyEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record LibraryManagementSystemReturnCopyEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record LibraryManagementSystemPlaceHoldEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record LibraryManagementSystemAssessFineEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface LibraryManagementSystemCommand permits CheckoutCopyCommand, ReturnCopyCommand, PlaceHoldCommand, AssessFineCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record CheckoutCopyCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements LibraryManagementSystemCommand {}
record ReturnCopyCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements LibraryManagementSystemCommand {}
record PlaceHoldCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements LibraryManagementSystemCommand {}
record AssessFineCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements LibraryManagementSystemCommand {}

interface LibraryManagementSystemRepository {
    Optional<LibraryManagementSystem> findById(UUID id);
    void save(LibraryManagementSystem aggregate, long expectedVersion);
}

interface LibraryManagementSystemPolicy {
    Decision evaluate(LibraryManagementSystem aggregate, LibraryManagementSystemCommand command);
}

final class BookTitle {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class LibraryManagementSystem {
    private final UUID id;
    private final List<BookTitle> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private LibraryManagementSystemStatus status;
    private long version;

    LibraryManagementSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = LibraryManagementSystemStatus.AVAILABLE;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    LibraryManagementSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void checkoutCopy(CheckoutCopyCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run checkoutCopy when aggregate is terminal");
    this.status = LibraryManagementSystemStatus.ON_LOAN;
    this.version++;
    this.domainEvents.add(new LibraryManagementSystemCheckoutCopyEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void returnCopy(ReturnCopyCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run returnCopy when aggregate is terminal");
    this.status = LibraryManagementSystemStatus.RESERVED;
    this.version++;
    this.domainEvents.add(new LibraryManagementSystemReturnCopyEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void placeHold(PlaceHoldCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run placeHold when aggregate is terminal");
    this.status = LibraryManagementSystemStatus.LOST;
    this.version++;
    this.domainEvents.add(new LibraryManagementSystemPlaceHoldEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void assessFine(AssessFineCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run assessFine when aggregate is terminal");
    this.status = LibraryManagementSystemStatus.OVERDUE;
    this.version++;
    this.domainEvents.add(new LibraryManagementSystemAssessFineEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == LibraryManagementSystemStatus.ARCHIVED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class LibraryManagementSystemService {
    private final LibraryManagementSystemRepository repository;
    private final LibraryManagementSystemPolicy policy;
    private final Outbox outbox;

    LibraryManagementSystemService(LibraryManagementSystemRepository repository, LibraryManagementSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(LibraryManagementSystemCommand command) {
        LibraryManagementSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("LibraryManagementSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof CheckoutCopyCommand c) aggregate.checkoutCopy(c);
        if (command instanceof ReturnCopyCommand c) aggregate.returnCopy(c);
        if (command instanceof PlaceHoldCommand c) aggregate.placeHold(c);
        if (command instanceof AssessFineCommand c) aggregate.assessFine(c);
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

- Persist `LibraryManagementSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `LibraryManagementSystem` invariants and each command method.
- State-machine test all valid and invalid `LibraryManagementSystemStatus` transitions.
- Contract test every `LibraryManagementSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `LibraryManagementSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `LibraryManagementSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
