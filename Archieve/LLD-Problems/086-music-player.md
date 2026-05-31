# 086. Design Music Player

Source problem: `Design music player.`  
Category: `Media`  
Primary focus: `playlists, playback queue, repeat/shuffle strategy`  
Archetype: `domain`

## 1. Interview Framing

Design `music player` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `music player` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `STOPPED, PLAYING, PAUSED, BUFFERING, ENDED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `Listener`
- `PlaybackEngine`
- `LibraryProvider`

Primary use cases:

- `play` command on `MusicPlayer`
- `pause` command on `MusicPlayer`
- `seek` command on `MusicPlayer`
- `nextTrack` command on `MusicPlayer`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `MusicPlayer` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Track, Playlist, PlaybackQueue, PlaybackSession, ShufflePolicy` | Have identity and change over time under the aggregate. |
| Value objects | `TrackId, Duration, Position, RepeatMode` | Immutable concepts compared by value. |
| Policies | `MusicPlayerPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `MusicPlayerRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
STOPPED, PLAYING, PAUSED, BUFFERING, ENDED
```

Invariants:

- `MusicPlayer` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `MusicPlayerService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `MusicPlayer` | Composes | Track, Playlist, PlaybackQueue | Owns invariants and lifecycle transitions. |
| `MusicPlayerRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `MusicPlayerPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class MusicPlayer {
  +UUID id
  +MusicPlayerStatus status
  +long version
  +validateInvariants()
}
class MusicPlayerService {
  +handle(command)
}
class MusicPlayerRepository {
  <<interface>>
  +findById(UUID id) MusicPlayer
  +save(MusicPlayer aggregate, long expectedVersion)
}
class MusicPlayerPolicy {
  <<interface>>
  +evaluate(context) Decision
}
MusicPlayerService --> MusicPlayerRepository
MusicPlayerService --> MusicPlayerPolicy
MusicPlayerService --> MusicPlayer
class Track {
  +UUID id
  +validate()
}
MusicPlayer "1" o-- "many" Track
class Playlist {
  +UUID id
  +validate()
}
MusicPlayer "1" o-- "many" Playlist
class PlaybackQueue {
  +UUID id
  +validate()
}
MusicPlayer "1" o-- "many" PlaybackQueue
class PlaybackSession {
  +UUID id
  +validate()
}
MusicPlayer "1" o-- "many" PlaybackSession
class TrackId {
  <<value object>>
}
MusicPlayer ..> TrackId
class Duration {
  <<value object>>
}
MusicPlayer ..> Duration
class Position {
  <<value object>>
}
MusicPlayer ..> Position
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as MusicPlayerService
participant Repo as MusicPlayerRepository
participant Policy as MusicPlayerPolicy
participant Agg as MusicPlayer
participant Outbox
Client->>Service: play(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: play(command)
Agg-->>Service: MusicPlayerPlayEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| Strategy | Swap algorithms such as pricing, ranking, scheduling, matching, or retry without changing the aggregate. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.musicplayer;

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

enum MusicPlayerStatus {
    STOPPED,
    PLAYING,
    PAUSED,
    BUFFERING,
    ENDED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record MusicPlayerPlayEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record MusicPlayerPauseEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record MusicPlayerSeekEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record MusicPlayerNextTrackEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface MusicPlayerCommand permits PlayCommand, PauseCommand, SeekCommand, NextTrackCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record PlayCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements MusicPlayerCommand {}
record PauseCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements MusicPlayerCommand {}
record SeekCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements MusicPlayerCommand {}
record NextTrackCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements MusicPlayerCommand {}

interface MusicPlayerRepository {
    Optional<MusicPlayer> findById(UUID id);
    void save(MusicPlayer aggregate, long expectedVersion);
}

interface MusicPlayerPolicy {
    Decision evaluate(MusicPlayer aggregate, MusicPlayerCommand command);
}

final class Track {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class MusicPlayer {
    private final UUID id;
    private final List<Track> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private MusicPlayerStatus status;
    private long version;

    MusicPlayer(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = MusicPlayerStatus.STOPPED;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    MusicPlayerStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void play(PlayCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run play when aggregate is terminal");
    this.status = MusicPlayerStatus.PLAYING;
    this.version++;
    this.domainEvents.add(new MusicPlayerPlayEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void pause(PauseCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run pause when aggregate is terminal");
    this.status = MusicPlayerStatus.PAUSED;
    this.version++;
    this.domainEvents.add(new MusicPlayerPauseEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void seek(SeekCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run seek when aggregate is terminal");
    this.status = MusicPlayerStatus.BUFFERING;
    this.version++;
    this.domainEvents.add(new MusicPlayerSeekEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void nextTrack(NextTrackCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run nextTrack when aggregate is terminal");
    this.status = MusicPlayerStatus.ENDED;
    this.version++;
    this.domainEvents.add(new MusicPlayerNextTrackEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == MusicPlayerStatus.ENDED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class MusicPlayerService {
    private final MusicPlayerRepository repository;
    private final MusicPlayerPolicy policy;
    private final Outbox outbox;

    MusicPlayerService(MusicPlayerRepository repository, MusicPlayerPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(MusicPlayerCommand command) {
        MusicPlayer aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("MusicPlayer not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof PlayCommand c) aggregate.play(c);
        if (command instanceof PauseCommand c) aggregate.pause(c);
        if (command instanceof SeekCommand c) aggregate.seek(c);
        if (command instanceof NextTrackCommand c) aggregate.nextTrack(c);
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

- Persist `MusicPlayer` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Swap algorithms such as pricing, ranking, scheduling, matching, or retry without changing the aggregate. | `Strategy` |
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `MusicPlayer` invariants and each command method.
- State-machine test all valid and invalid `MusicPlayerStatus` transitions.
- Contract test every `MusicPlayerRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `MusicPlayer` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `MusicPlayerService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
