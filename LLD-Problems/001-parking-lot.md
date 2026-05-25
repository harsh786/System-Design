# 001. Design A Parking Lot

Source problem: `Design a parking lot.`  
Category: `Classic OOD`  
Primary focus: `composition, allocation strategy, pricing policy, ticket lifecycle`  
Archetype: `state-workflow`

## 1. Interview Framing

Design `parking lot` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `parking lot` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `SPOT_AVAILABLE, SPOT_HELD, SPOT_OCCUPIED, PAYMENT_PENDING, PAID`.
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

- `Driver`
- `ParkingAttendant`
- `PaymentProvider`

Primary use cases:

- `issueTicket` command on `ParkingLot`
- `allocateSpot` command on `ParkingLot`
- `capturePayment` command on `ParkingLot`
- `releaseSpot` command on `ParkingLot`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `ParkingLot` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `ParkingFloor, ParkingSpot, Vehicle, ParkingTicket, Gate` | Have identity and change over time under the aggregate. |
| Value objects | `Money, LicensePlate, SpotType, TimeRange` | Immutable concepts compared by value. |
| Policies | `ParkingLotPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `ParkingLotRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
SPOT_AVAILABLE, SPOT_HELD, SPOT_OCCUPIED, PAYMENT_PENDING, PAID, EXITED
```

Invariants:

- `ParkingLot` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `ParkingLotService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `ParkingLot` | Composes | ParkingFloor, ParkingSpot, Vehicle | Owns invariants and lifecycle transitions. |
| `ParkingLotRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `ParkingLotPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class ParkingLot {
  +UUID id
  +ParkingLotStatus status
  +long version
  +validateInvariants()
}
class ParkingLotService {
  +handle(command)
}
class ParkingLotRepository {
  <<interface>>
  +findById(UUID id) ParkingLot
  +save(ParkingLot aggregate, long expectedVersion)
}
class ParkingLotPolicy {
  <<interface>>
  +evaluate(context) Decision
}
ParkingLotService --> ParkingLotRepository
ParkingLotService --> ParkingLotPolicy
ParkingLotService --> ParkingLot
class ParkingFloor {
  +UUID id
  +validate()
}
ParkingLot "1" o-- "many" ParkingFloor
class ParkingSpot {
  +UUID id
  +validate()
}
ParkingLot "1" o-- "many" ParkingSpot
class Vehicle {
  +UUID id
  +validate()
}
ParkingLot "1" o-- "many" Vehicle
class ParkingTicket {
  +UUID id
  +validate()
}
ParkingLot "1" o-- "many" ParkingTicket
class Money {
  <<value object>>
}
ParkingLot ..> Money
class LicensePlate {
  <<value object>>
}
ParkingLot ..> LicensePlate
class SpotType {
  <<value object>>
}
ParkingLot ..> SpotType
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as ParkingLotService
participant Repo as ParkingLotRepository
participant Policy as ParkingLotPolicy
participant Agg as ParkingLot
participant Outbox
Client->>Service: issueTicket(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: issueTicket(command)
Agg-->>Service: ParkingLotIssueTicketEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |
| Strategy | Swap algorithms such as pricing, ranking, scheduling, matching, or retry without changing the aggregate. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.parkinglot;

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

enum ParkingLotStatus {
    SPOT_AVAILABLE,
    SPOT_HELD,
    SPOT_OCCUPIED,
    PAYMENT_PENDING,
    PAID,
    EXITED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record ParkingLotIssueTicketEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ParkingLotAllocateSpotEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ParkingLotCapturePaymentEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ParkingLotReleaseSpotEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface ParkingLotCommand permits IssueTicketCommand, AllocateSpotCommand, CapturePaymentCommand, ReleaseSpotCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record IssueTicketCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ParkingLotCommand {}
record AllocateSpotCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ParkingLotCommand {}
record CapturePaymentCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ParkingLotCommand {}
record ReleaseSpotCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ParkingLotCommand {}

interface ParkingLotRepository {
    Optional<ParkingLot> findById(UUID id);
    void save(ParkingLot aggregate, long expectedVersion);
}

interface ParkingLotPolicy {
    Decision evaluate(ParkingLot aggregate, ParkingLotCommand command);
}

final class ParkingFloor {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class ParkingLot {
    private final UUID id;
    private final List<ParkingFloor> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private ParkingLotStatus status;
    private long version;

    ParkingLot(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = ParkingLotStatus.SPOT_AVAILABLE;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    ParkingLotStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void issueTicket(IssueTicketCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run issueTicket when aggregate is terminal");
    this.status = ParkingLotStatus.SPOT_HELD;
    this.version++;
    this.domainEvents.add(new ParkingLotIssueTicketEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void allocateSpot(AllocateSpotCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run allocateSpot when aggregate is terminal");
    this.status = ParkingLotStatus.SPOT_OCCUPIED;
    this.version++;
    this.domainEvents.add(new ParkingLotAllocateSpotEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void capturePayment(CapturePaymentCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run capturePayment when aggregate is terminal");
    this.status = ParkingLotStatus.PAYMENT_PENDING;
    this.version++;
    this.domainEvents.add(new ParkingLotCapturePaymentEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void releaseSpot(ReleaseSpotCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run releaseSpot when aggregate is terminal");
    this.status = ParkingLotStatus.PAID;
    this.version++;
    this.domainEvents.add(new ParkingLotReleaseSpotEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == ParkingLotStatus.EXITED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class ParkingLotService {
    private final ParkingLotRepository repository;
    private final ParkingLotPolicy policy;
    private final Outbox outbox;

    ParkingLotService(ParkingLotRepository repository, ParkingLotPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(ParkingLotCommand command) {
        ParkingLot aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("ParkingLot not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof IssueTicketCommand c) aggregate.issueTicket(c);
        if (command instanceof AllocateSpotCommand c) aggregate.allocateSpot(c);
        if (command instanceof CapturePaymentCommand c) aggregate.capturePayment(c);
        if (command instanceof ReleaseSpotCommand c) aggregate.releaseSpot(c);
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

- Persist `ParkingLot` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `ParkingLot` invariants and each command method.
- State-machine test all valid and invalid `ParkingLotStatus` transitions.
- Contract test every `ParkingLotRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `ParkingLot` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `ParkingLotService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
