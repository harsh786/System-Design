# 080. Design Collaborative Whiteboard Model

Source problem: `Design collaborative whiteboard model.`  
Category: `Collaboration`  
Primary focus: `shapes, layers, events, conflict handling`  
Archetype: `domain`

## 1. Interview Framing

Design `collaborative whiteboard model` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `collaborative whiteboard model` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `OPEN, EDITING, MERGING, CONFLICTED, SAVED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `User`
- `RealtimeSession`
- `StorageProvider`

Primary use cases:

- `addShape` command on `CollaborativeWhiteboardModel`
- `moveShape` command on `CollaborativeWhiteboardModel`
- `applyRemoteOperation` command on `CollaborativeWhiteboardModel`
- `saveSnapshot` command on `CollaborativeWhiteboardModel`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `CollaborativeWhiteboardModel` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Board, Shape, Layer, Operation, Presence` | Have identity and change over time under the aggregate. |
| Value objects | `ShapeId, Coordinate, Revision, UserId` | Immutable concepts compared by value. |
| Policies | `CollaborativeWhiteboardModelPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `CollaborativeWhiteboardModelRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
OPEN, EDITING, MERGING, CONFLICTED, SAVED, CLOSED
```

Invariants:

- `CollaborativeWhiteboardModel` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `CollaborativeWhiteboardModelService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `CollaborativeWhiteboardModel` | Composes | Board, Shape, Layer | Owns invariants and lifecycle transitions. |
| `CollaborativeWhiteboardModelRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `CollaborativeWhiteboardModelPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class CollaborativeWhiteboardModel {
  +UUID id
  +CollaborativeWhiteboardModelStatus status
  +long version
  +validateInvariants()
}
class CollaborativeWhiteboardModelService {
  +handle(command)
}
class CollaborativeWhiteboardModelRepository {
  <<interface>>
  +findById(UUID id) CollaborativeWhiteboardModel
  +save(CollaborativeWhiteboardModel aggregate, long expectedVersion)
}
class CollaborativeWhiteboardModelPolicy {
  <<interface>>
  +evaluate(context) Decision
}
CollaborativeWhiteboardModelService --> CollaborativeWhiteboardModelRepository
CollaborativeWhiteboardModelService --> CollaborativeWhiteboardModelPolicy
CollaborativeWhiteboardModelService --> CollaborativeWhiteboardModel
class Board {
  +UUID id
  +validate()
}
CollaborativeWhiteboardModel "1" o-- "many" Board
class Shape {
  +UUID id
  +validate()
}
CollaborativeWhiteboardModel "1" o-- "many" Shape
class Layer {
  +UUID id
  +validate()
}
CollaborativeWhiteboardModel "1" o-- "many" Layer
class Operation {
  +UUID id
  +validate()
}
CollaborativeWhiteboardModel "1" o-- "many" Operation
class ShapeId {
  <<value object>>
}
CollaborativeWhiteboardModel ..> ShapeId
class Coordinate {
  <<value object>>
}
CollaborativeWhiteboardModel ..> Coordinate
class Revision {
  <<value object>>
}
CollaborativeWhiteboardModel ..> Revision
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as CollaborativeWhiteboardModelService
participant Repo as CollaborativeWhiteboardModelRepository
participant Policy as CollaborativeWhiteboardModelPolicy
participant Agg as CollaborativeWhiteboardModel
participant Outbox
Client->>Service: addShape(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: addShape(command)
Agg-->>Service: CollaborativeWhiteboardModelAddShapeEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| Observer / Domain Events | Emit facts after state changes so subscribers can update read models or send notifications. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.collaborativewhiteboardmodel;

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

enum CollaborativeWhiteboardModelStatus {
    OPEN,
    EDITING,
    MERGING,
    CONFLICTED,
    SAVED,
    CLOSED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record CollaborativeWhiteboardModelAddShapeEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record CollaborativeWhiteboardModelMoveShapeEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record CollaborativeWhiteboardModelApplyRemoteOperationEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record CollaborativeWhiteboardModelSaveSnapshotEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface CollaborativeWhiteboardModelCommand permits AddShapeCommand, MoveShapeCommand, ApplyRemoteOperationCommand, SaveSnapshotCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record AddShapeCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CollaborativeWhiteboardModelCommand {}
record MoveShapeCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CollaborativeWhiteboardModelCommand {}
record ApplyRemoteOperationCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CollaborativeWhiteboardModelCommand {}
record SaveSnapshotCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CollaborativeWhiteboardModelCommand {}

interface CollaborativeWhiteboardModelRepository {
    Optional<CollaborativeWhiteboardModel> findById(UUID id);
    void save(CollaborativeWhiteboardModel aggregate, long expectedVersion);
}

interface CollaborativeWhiteboardModelPolicy {
    Decision evaluate(CollaborativeWhiteboardModel aggregate, CollaborativeWhiteboardModelCommand command);
}

final class Board {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class CollaborativeWhiteboardModel {
    private final UUID id;
    private final List<Board> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private CollaborativeWhiteboardModelStatus status;
    private long version;

    CollaborativeWhiteboardModel(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = CollaborativeWhiteboardModelStatus.OPEN;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    CollaborativeWhiteboardModelStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void addShape(AddShapeCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run addShape when aggregate is terminal");
    this.status = CollaborativeWhiteboardModelStatus.EDITING;
    this.version++;
    this.domainEvents.add(new CollaborativeWhiteboardModelAddShapeEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void moveShape(MoveShapeCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run moveShape when aggregate is terminal");
    this.status = CollaborativeWhiteboardModelStatus.MERGING;
    this.version++;
    this.domainEvents.add(new CollaborativeWhiteboardModelMoveShapeEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void applyRemoteOperation(ApplyRemoteOperationCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run applyRemoteOperation when aggregate is terminal");
    this.status = CollaborativeWhiteboardModelStatus.CONFLICTED;
    this.version++;
    this.domainEvents.add(new CollaborativeWhiteboardModelApplyRemoteOperationEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void saveSnapshot(SaveSnapshotCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run saveSnapshot when aggregate is terminal");
    this.status = CollaborativeWhiteboardModelStatus.SAVED;
    this.version++;
    this.domainEvents.add(new CollaborativeWhiteboardModelSaveSnapshotEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == CollaborativeWhiteboardModelStatus.CLOSED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class CollaborativeWhiteboardModelService {
    private final CollaborativeWhiteboardModelRepository repository;
    private final CollaborativeWhiteboardModelPolicy policy;
    private final Outbox outbox;

    CollaborativeWhiteboardModelService(CollaborativeWhiteboardModelRepository repository, CollaborativeWhiteboardModelPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(CollaborativeWhiteboardModelCommand command) {
        CollaborativeWhiteboardModel aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("CollaborativeWhiteboardModel not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof AddShapeCommand c) aggregate.addShape(c);
        if (command instanceof MoveShapeCommand c) aggregate.moveShape(c);
        if (command instanceof ApplyRemoteOperationCommand c) aggregate.applyRemoteOperation(c);
        if (command instanceof SaveSnapshotCommand c) aggregate.saveSnapshot(c);
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

- Persist `CollaborativeWhiteboardModel` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Emit facts after state changes so subscribers can update read models or send notifications. | `Observer / Domain Events` |
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `CollaborativeWhiteboardModel` invariants and each command method.
- State-machine test all valid and invalid `CollaborativeWhiteboardModelStatus` transitions.
- Contract test every `CollaborativeWhiteboardModelRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `CollaborativeWhiteboardModel` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `CollaborativeWhiteboardModelService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
