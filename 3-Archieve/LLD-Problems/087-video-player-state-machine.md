# 087. Design Video Player State Machine

Source problem: `Design video player state machine.`  
Category: `Media`  
Primary focus: `buffering, play/pause, seek, quality changes`  
Archetype: `domain`

## 1. Interview Framing

Design `video player state machine` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `video player state machine` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `IDLE, BUFFERING, PLAYING, PAUSED, SEEKING`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `Viewer`
- `PlaybackEngine`
- `NetworkMonitor`

Primary use cases:

- `loadVideo` command on `VideoPlayerStateMachine`
- `play` command on `VideoPlayerStateMachine`
- `pause` command on `VideoPlayerStateMachine`
- `seek` command on `VideoPlayerStateMachine`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `VideoPlayerStateMachine` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Video, PlaybackSession, Buffer, QualityProfile, PlayerEvent` | Have identity and change over time under the aggregate. |
| Value objects | `Duration, Position, Bitrate, Resolution` | Immutable concepts compared by value. |
| Policies | `VideoPlayerStateMachinePolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `VideoPlayerStateMachineRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
IDLE, BUFFERING, PLAYING, PAUSED, SEEKING, ENDED, ERROR
```

Invariants:

- `VideoPlayerStateMachine` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `VideoPlayerStateMachineService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `VideoPlayerStateMachine` | Composes | Video, PlaybackSession, Buffer | Owns invariants and lifecycle transitions. |
| `VideoPlayerStateMachineRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `VideoPlayerStateMachinePolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class VideoPlayerStateMachine {
  +UUID id
  +VideoPlayerStateMachineStatus status
  +long version
  +validateInvariants()
}
class VideoPlayerStateMachineService {
  +handle(command)
}
class VideoPlayerStateMachineRepository {
  <<interface>>
  +findById(UUID id) VideoPlayerStateMachine
  +save(VideoPlayerStateMachine aggregate, long expectedVersion)
}
class VideoPlayerStateMachinePolicy {
  <<interface>>
  +evaluate(context) Decision
}
VideoPlayerStateMachineService --> VideoPlayerStateMachineRepository
VideoPlayerStateMachineService --> VideoPlayerStateMachinePolicy
VideoPlayerStateMachineService --> VideoPlayerStateMachine
class Video {
  +UUID id
  +validate()
}
VideoPlayerStateMachine "1" o-- "many" Video
class PlaybackSession {
  +UUID id
  +validate()
}
VideoPlayerStateMachine "1" o-- "many" PlaybackSession
class Buffer {
  +UUID id
  +validate()
}
VideoPlayerStateMachine "1" o-- "many" Buffer
class QualityProfile {
  +UUID id
  +validate()
}
VideoPlayerStateMachine "1" o-- "many" QualityProfile
class Duration {
  <<value object>>
}
VideoPlayerStateMachine ..> Duration
class Position {
  <<value object>>
}
VideoPlayerStateMachine ..> Position
class Bitrate {
  <<value object>>
}
VideoPlayerStateMachine ..> Bitrate
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as VideoPlayerStateMachineService
participant Repo as VideoPlayerStateMachineRepository
participant Policy as VideoPlayerStateMachinePolicy
participant Agg as VideoPlayerStateMachine
participant Outbox
Client->>Service: loadVideo(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: loadVideo(command)
Agg-->>Service: VideoPlayerStateMachineLoadVideoEvent
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
package lld.videoplayerstatemachine;

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

enum VideoPlayerStateMachineStatus {
    IDLE,
    BUFFERING,
    PLAYING,
    PAUSED,
    SEEKING,
    ENDED,
    ERROR
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record VideoPlayerStateMachineLoadVideoEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record VideoPlayerStateMachinePlayEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record VideoPlayerStateMachinePauseEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record VideoPlayerStateMachineSeekEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface VideoPlayerStateMachineCommand permits LoadVideoCommand, PlayCommand, PauseCommand, SeekCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record LoadVideoCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements VideoPlayerStateMachineCommand {}
record PlayCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements VideoPlayerStateMachineCommand {}
record PauseCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements VideoPlayerStateMachineCommand {}
record SeekCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements VideoPlayerStateMachineCommand {}

interface VideoPlayerStateMachineRepository {
    Optional<VideoPlayerStateMachine> findById(UUID id);
    void save(VideoPlayerStateMachine aggregate, long expectedVersion);
}

interface VideoPlayerStateMachinePolicy {
    Decision evaluate(VideoPlayerStateMachine aggregate, VideoPlayerStateMachineCommand command);
}

final class Video {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class VideoPlayerStateMachine {
    private final UUID id;
    private final List<Video> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private VideoPlayerStateMachineStatus status;
    private long version;

    VideoPlayerStateMachine(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = VideoPlayerStateMachineStatus.IDLE;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    VideoPlayerStateMachineStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void loadVideo(LoadVideoCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run loadVideo when aggregate is terminal");
    this.status = VideoPlayerStateMachineStatus.BUFFERING;
    this.version++;
    this.domainEvents.add(new VideoPlayerStateMachineLoadVideoEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void play(PlayCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run play when aggregate is terminal");
    this.status = VideoPlayerStateMachineStatus.PLAYING;
    this.version++;
    this.domainEvents.add(new VideoPlayerStateMachinePlayEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void pause(PauseCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run pause when aggregate is terminal");
    this.status = VideoPlayerStateMachineStatus.PAUSED;
    this.version++;
    this.domainEvents.add(new VideoPlayerStateMachinePauseEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void seek(SeekCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run seek when aggregate is terminal");
    this.status = VideoPlayerStateMachineStatus.SEEKING;
    this.version++;
    this.domainEvents.add(new VideoPlayerStateMachineSeekEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == VideoPlayerStateMachineStatus.ERROR;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class VideoPlayerStateMachineService {
    private final VideoPlayerStateMachineRepository repository;
    private final VideoPlayerStateMachinePolicy policy;
    private final Outbox outbox;

    VideoPlayerStateMachineService(VideoPlayerStateMachineRepository repository, VideoPlayerStateMachinePolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(VideoPlayerStateMachineCommand command) {
        VideoPlayerStateMachine aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("VideoPlayerStateMachine not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof LoadVideoCommand c) aggregate.loadVideo(c);
        if (command instanceof PlayCommand c) aggregate.play(c);
        if (command instanceof PauseCommand c) aggregate.pause(c);
        if (command instanceof SeekCommand c) aggregate.seek(c);
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

- Persist `VideoPlayerStateMachine` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `VideoPlayerStateMachine` invariants and each command method.
- State-machine test all valid and invalid `VideoPlayerStateMachineStatus` transitions.
- Contract test every `VideoPlayerStateMachineRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `VideoPlayerStateMachine` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `VideoPlayerStateMachineService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
