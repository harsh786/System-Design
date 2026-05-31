# 005. Design A Traffic Signal Controller

Source problem: `Design a traffic signal controller.`  
Category: `Control system`  
Primary focus: `State, timing policy, pedestrian events, emergency override`  
Archetype: `state-workflow`

## 1. Interview Framing

Design `traffic signal controller` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `traffic signal controller` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `GREEN, YELLOW, RED, PEDESTRIAN_WALK, EMERGENCY_PREEMPTION`.
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

- `VehicleSensor`
- `Pedestrian`
- `EmergencyVehicle`
- `Operator`

Primary use cases:

- `detectDemand` command on `TrafficSignalController`
- `advancePhase` command on `TrafficSignalController`
- `preemptForEmergency` command on `TrafficSignalController`
- `restorePlan` command on `TrafficSignalController`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `TrafficSignalController` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Intersection, SignalHead, Phase, Sensor, TimingPlan` | Have identity and change over time under the aggregate. |
| Value objects | `Duration, LaneId, Priority` | Immutable concepts compared by value. |
| Policies | `TrafficSignalControllerPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `TrafficSignalControllerRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
GREEN, YELLOW, RED, PEDESTRIAN_WALK, EMERGENCY_PREEMPTION, FLASHING
```

Invariants:

- `TrafficSignalController` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `TrafficSignalControllerService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `TrafficSignalController` | Composes | Intersection, SignalHead, Phase | Owns invariants and lifecycle transitions. |
| `TrafficSignalControllerRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `TrafficSignalControllerPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class TrafficSignalController {
  +UUID id
  +TrafficSignalControllerStatus status
  +long version
  +validateInvariants()
}
class TrafficSignalControllerService {
  +handle(command)
}
class TrafficSignalControllerRepository {
  <<interface>>
  +findById(UUID id) TrafficSignalController
  +save(TrafficSignalController aggregate, long expectedVersion)
}
class TrafficSignalControllerPolicy {
  <<interface>>
  +evaluate(context) Decision
}
TrafficSignalControllerService --> TrafficSignalControllerRepository
TrafficSignalControllerService --> TrafficSignalControllerPolicy
TrafficSignalControllerService --> TrafficSignalController
class Intersection {
  +UUID id
  +validate()
}
TrafficSignalController "1" o-- "many" Intersection
class SignalHead {
  +UUID id
  +validate()
}
TrafficSignalController "1" o-- "many" SignalHead
class Phase {
  +UUID id
  +validate()
}
TrafficSignalController "1" o-- "many" Phase
class Sensor {
  +UUID id
  +validate()
}
TrafficSignalController "1" o-- "many" Sensor
class Duration {
  <<value object>>
}
TrafficSignalController ..> Duration
class LaneId {
  <<value object>>
}
TrafficSignalController ..> LaneId
class Priority {
  <<value object>>
}
TrafficSignalController ..> Priority
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as TrafficSignalControllerService
participant Repo as TrafficSignalControllerRepository
participant Policy as TrafficSignalControllerPolicy
participant Agg as TrafficSignalController
participant Outbox
Client->>Service: detectDemand(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: detectDemand(command)
Agg-->>Service: TrafficSignalControllerDetectDemandEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |
| Strategy | Swap algorithms such as pricing, ranking, scheduling, matching, or retry without changing the aggregate. |
| Observer / Domain Events | Emit facts after state changes so subscribers can update read models or send notifications. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.trafficsignalcontroller;

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

enum TrafficSignalControllerStatus {
    GREEN,
    YELLOW,
    RED,
    PEDESTRIAN_WALK,
    EMERGENCY_PREEMPTION,
    FLASHING
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record TrafficSignalControllerDetectDemandEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record TrafficSignalControllerAdvancePhaseEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record TrafficSignalControllerPreemptForEmergencyEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record TrafficSignalControllerRestorePlanEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface TrafficSignalControllerCommand permits DetectDemandCommand, AdvancePhaseCommand, PreemptForEmergencyCommand, RestorePlanCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record DetectDemandCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements TrafficSignalControllerCommand {}
record AdvancePhaseCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements TrafficSignalControllerCommand {}
record PreemptForEmergencyCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements TrafficSignalControllerCommand {}
record RestorePlanCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements TrafficSignalControllerCommand {}

interface TrafficSignalControllerRepository {
    Optional<TrafficSignalController> findById(UUID id);
    void save(TrafficSignalController aggregate, long expectedVersion);
}

interface TrafficSignalControllerPolicy {
    Decision evaluate(TrafficSignalController aggregate, TrafficSignalControllerCommand command);
}

final class Intersection {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class TrafficSignalController {
    private final UUID id;
    private final List<Intersection> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private TrafficSignalControllerStatus status;
    private long version;

    TrafficSignalController(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = TrafficSignalControllerStatus.GREEN;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    TrafficSignalControllerStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void detectDemand(DetectDemandCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run detectDemand when aggregate is terminal");
    this.status = TrafficSignalControllerStatus.YELLOW;
    this.version++;
    this.domainEvents.add(new TrafficSignalControllerDetectDemandEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void advancePhase(AdvancePhaseCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run advancePhase when aggregate is terminal");
    this.status = TrafficSignalControllerStatus.RED;
    this.version++;
    this.domainEvents.add(new TrafficSignalControllerAdvancePhaseEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void preemptForEmergency(PreemptForEmergencyCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run preemptForEmergency when aggregate is terminal");
    this.status = TrafficSignalControllerStatus.PEDESTRIAN_WALK;
    this.version++;
    this.domainEvents.add(new TrafficSignalControllerPreemptForEmergencyEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void restorePlan(RestorePlanCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run restorePlan when aggregate is terminal");
    this.status = TrafficSignalControllerStatus.EMERGENCY_PREEMPTION;
    this.version++;
    this.domainEvents.add(new TrafficSignalControllerRestorePlanEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == TrafficSignalControllerStatus.FLASHING;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class TrafficSignalControllerService {
    private final TrafficSignalControllerRepository repository;
    private final TrafficSignalControllerPolicy policy;
    private final Outbox outbox;

    TrafficSignalControllerService(TrafficSignalControllerRepository repository, TrafficSignalControllerPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(TrafficSignalControllerCommand command) {
        TrafficSignalController aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("TrafficSignalController not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof DetectDemandCommand c) aggregate.detectDemand(c);
        if (command instanceof AdvancePhaseCommand c) aggregate.advancePhase(c);
        if (command instanceof PreemptForEmergencyCommand c) aggregate.preemptForEmergency(c);
        if (command instanceof RestorePlanCommand c) aggregate.restorePlan(c);
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

- Persist `TrafficSignalController` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Emit facts after state changes so subscribers can update read models or send notifications. | `Observer / Domain Events` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `TrafficSignalController` invariants and each command method.
- State-machine test all valid and invalid `TrafficSignalControllerStatus` transitions.
- Contract test every `TrafficSignalControllerRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `TrafficSignalController` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `TrafficSignalControllerService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
