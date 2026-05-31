# 029. Design Ride-Sharing Trip Lifecycle

Source problem: `Design ride-sharing trip lifecycle.`  
Category: `Marketplace`  
Primary focus: `matching policy, trip states, pricing, cancellation`  
Archetype: `state-workflow`

## 1. Interview Framing

Design `ride-sharing trip lifecycle` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `ride-sharing trip lifecycle` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `REQUESTED, MATCHED, DRIVER_ARRIVING, IN_PROGRESS, COMPLETED`.
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

- `Rider`
- `Driver`
- `MatchingService`
- `PaymentProvider`

Primary use cases:

- `requestRide` command on `RideSharingTripLifecycle`
- `matchDriver` command on `RideSharingTripLifecycle`
- `startTrip` command on `RideSharingTripLifecycle`
- `completeTrip` command on `RideSharingTripLifecycle`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `RideSharingTripLifecycle` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Trip, RideRequest, DriverAssignment, Fare, Location` | Have identity and change over time under the aggregate. |
| Value objects | `Money, GeoPoint, ETA, Distance` | Immutable concepts compared by value. |
| Policies | `RideSharingTripLifecyclePolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `RideSharingTripLifecycleRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
REQUESTED, MATCHED, DRIVER_ARRIVING, IN_PROGRESS, COMPLETED, CANCELLED
```

Invariants:

- `RideSharingTripLifecycle` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `RideSharingTripLifecycleService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `RideSharingTripLifecycle` | Composes | Trip, RideRequest, DriverAssignment | Owns invariants and lifecycle transitions. |
| `RideSharingTripLifecycleRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `RideSharingTripLifecyclePolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class RideSharingTripLifecycle {
  +UUID id
  +RideSharingTripLifecycleStatus status
  +long version
  +validateInvariants()
}
class RideSharingTripLifecycleService {
  +handle(command)
}
class RideSharingTripLifecycleRepository {
  <<interface>>
  +findById(UUID id) RideSharingTripLifecycle
  +save(RideSharingTripLifecycle aggregate, long expectedVersion)
}
class RideSharingTripLifecyclePolicy {
  <<interface>>
  +evaluate(context) Decision
}
RideSharingTripLifecycleService --> RideSharingTripLifecycleRepository
RideSharingTripLifecycleService --> RideSharingTripLifecyclePolicy
RideSharingTripLifecycleService --> RideSharingTripLifecycle
class Trip {
  +UUID id
  +validate()
}
RideSharingTripLifecycle "1" o-- "many" Trip
class RideRequest {
  +UUID id
  +validate()
}
RideSharingTripLifecycle "1" o-- "many" RideRequest
class DriverAssignment {
  +UUID id
  +validate()
}
RideSharingTripLifecycle "1" o-- "many" DriverAssignment
class Fare {
  +UUID id
  +validate()
}
RideSharingTripLifecycle "1" o-- "many" Fare
class Money {
  <<value object>>
}
RideSharingTripLifecycle ..> Money
class GeoPoint {
  <<value object>>
}
RideSharingTripLifecycle ..> GeoPoint
class ETA {
  <<value object>>
}
RideSharingTripLifecycle ..> ETA
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as RideSharingTripLifecycleService
participant Repo as RideSharingTripLifecycleRepository
participant Policy as RideSharingTripLifecyclePolicy
participant Agg as RideSharingTripLifecycle
participant Outbox
Client->>Service: requestRide(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: requestRide(command)
Agg-->>Service: RideSharingTripLifecycleRequestRideEvent
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
package lld.ridesharingtriplifecycle;

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

enum RideSharingTripLifecycleStatus {
    REQUESTED,
    MATCHED,
    DRIVER_ARRIVING,
    IN_PROGRESS,
    COMPLETED,
    CANCELLED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record RideSharingTripLifecycleRequestRideEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record RideSharingTripLifecycleMatchDriverEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record RideSharingTripLifecycleStartTripEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record RideSharingTripLifecycleCompleteTripEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface RideSharingTripLifecycleCommand permits RequestRideCommand, MatchDriverCommand, StartTripCommand, CompleteTripCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record RequestRideCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RideSharingTripLifecycleCommand {}
record MatchDriverCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RideSharingTripLifecycleCommand {}
record StartTripCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RideSharingTripLifecycleCommand {}
record CompleteTripCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RideSharingTripLifecycleCommand {}

interface RideSharingTripLifecycleRepository {
    Optional<RideSharingTripLifecycle> findById(UUID id);
    void save(RideSharingTripLifecycle aggregate, long expectedVersion);
}

interface RideSharingTripLifecyclePolicy {
    Decision evaluate(RideSharingTripLifecycle aggregate, RideSharingTripLifecycleCommand command);
}

final class Trip {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class RideSharingTripLifecycle {
    private final UUID id;
    private final List<Trip> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private RideSharingTripLifecycleStatus status;
    private long version;

    RideSharingTripLifecycle(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = RideSharingTripLifecycleStatus.REQUESTED;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    RideSharingTripLifecycleStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void requestRide(RequestRideCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run requestRide when aggregate is terminal");
    this.status = RideSharingTripLifecycleStatus.MATCHED;
    this.version++;
    this.domainEvents.add(new RideSharingTripLifecycleRequestRideEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void matchDriver(MatchDriverCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run matchDriver when aggregate is terminal");
    this.status = RideSharingTripLifecycleStatus.DRIVER_ARRIVING;
    this.version++;
    this.domainEvents.add(new RideSharingTripLifecycleMatchDriverEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void startTrip(StartTripCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run startTrip when aggregate is terminal");
    this.status = RideSharingTripLifecycleStatus.IN_PROGRESS;
    this.version++;
    this.domainEvents.add(new RideSharingTripLifecycleStartTripEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void completeTrip(CompleteTripCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run completeTrip when aggregate is terminal");
    this.status = RideSharingTripLifecycleStatus.COMPLETED;
    this.version++;
    this.domainEvents.add(new RideSharingTripLifecycleCompleteTripEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == RideSharingTripLifecycleStatus.CANCELLED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class RideSharingTripLifecycleService {
    private final RideSharingTripLifecycleRepository repository;
    private final RideSharingTripLifecyclePolicy policy;
    private final Outbox outbox;

    RideSharingTripLifecycleService(RideSharingTripLifecycleRepository repository, RideSharingTripLifecyclePolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(RideSharingTripLifecycleCommand command) {
        RideSharingTripLifecycle aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("RideSharingTripLifecycle not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof RequestRideCommand c) aggregate.requestRide(c);
        if (command instanceof MatchDriverCommand c) aggregate.matchDriver(c);
        if (command instanceof StartTripCommand c) aggregate.startTrip(c);
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

- Persist `RideSharingTripLifecycle` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `RideSharingTripLifecycle` invariants and each command method.
- State-machine test all valid and invalid `RideSharingTripLifecycleStatus` transitions.
- Contract test every `RideSharingTripLifecycleRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `RideSharingTripLifecycle` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `RideSharingTripLifecycleService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
