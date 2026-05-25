# 085. Design Instagram-Like Media Post Model

Source problem: `Design Instagram-like media post model.`  
Category: `Social/media`  
Primary focus: `media, captions, likes, comments, moderation`  
Archetype: `domain`

## 1. Interview Framing

Design `Instagram-like media post model` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `Instagram-like media post model` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `DRAFT, PUBLISHED, FLAGGED, HIDDEN, DELETED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `Creator`
- `Follower`
- `ModerationService`

Primary use cases:

- `createPost` command on `InstagramMediaPostModel`
- `attachMedia` command on `InstagramMediaPostModel`
- `likePost` command on `InstagramMediaPostModel`
- `moderatePost` command on `InstagramMediaPostModel`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `InstagramMediaPostModel` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `MediaPost, MediaAsset, Caption, Like, Comment` | Have identity and change over time under the aggregate. |
| Value objects | `MediaId, UserId, Visibility, Hashtag` | Immutable concepts compared by value. |
| Policies | `InstagramMediaPostModelPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `InstagramMediaPostModelRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
DRAFT, PUBLISHED, FLAGGED, HIDDEN, DELETED, ARCHIVED
```

Invariants:

- `InstagramMediaPostModel` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `InstagramMediaPostModelService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `InstagramMediaPostModel` | Composes | MediaPost, MediaAsset, Caption | Owns invariants and lifecycle transitions. |
| `InstagramMediaPostModelRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `InstagramMediaPostModelPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class InstagramMediaPostModel {
  +UUID id
  +InstagramMediaPostModelStatus status
  +long version
  +validateInvariants()
}
class InstagramMediaPostModelService {
  +handle(command)
}
class InstagramMediaPostModelRepository {
  <<interface>>
  +findById(UUID id) InstagramMediaPostModel
  +save(InstagramMediaPostModel aggregate, long expectedVersion)
}
class InstagramMediaPostModelPolicy {
  <<interface>>
  +evaluate(context) Decision
}
InstagramMediaPostModelService --> InstagramMediaPostModelRepository
InstagramMediaPostModelService --> InstagramMediaPostModelPolicy
InstagramMediaPostModelService --> InstagramMediaPostModel
class MediaPost {
  +UUID id
  +validate()
}
InstagramMediaPostModel "1" o-- "many" MediaPost
class MediaAsset {
  +UUID id
  +validate()
}
InstagramMediaPostModel "1" o-- "many" MediaAsset
class Caption {
  +UUID id
  +validate()
}
InstagramMediaPostModel "1" o-- "many" Caption
class Like {
  +UUID id
  +validate()
}
InstagramMediaPostModel "1" o-- "many" Like
class MediaId {
  <<value object>>
}
InstagramMediaPostModel ..> MediaId
class UserId {
  <<value object>>
}
InstagramMediaPostModel ..> UserId
class Visibility {
  <<value object>>
}
InstagramMediaPostModel ..> Visibility
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as InstagramMediaPostModelService
participant Repo as InstagramMediaPostModelRepository
participant Policy as InstagramMediaPostModelPolicy
participant Agg as InstagramMediaPostModel
participant Outbox
Client->>Service: createPost(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: createPost(command)
Agg-->>Service: InstagramMediaPostModelCreatePostEvent
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
package lld.instagramlikemediapostmodel;

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

enum InstagramMediaPostModelStatus {
    DRAFT,
    PUBLISHED,
    FLAGGED,
    HIDDEN,
    DELETED,
    ARCHIVED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record InstagramMediaPostModelCreatePostEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record InstagramMediaPostModelAttachMediaEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record InstagramMediaPostModelLikePostEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record InstagramMediaPostModelModeratePostEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface InstagramMediaPostModelCommand permits CreatePostCommand, AttachMediaCommand, LikePostCommand, ModeratePostCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record CreatePostCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements InstagramMediaPostModelCommand {}
record AttachMediaCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements InstagramMediaPostModelCommand {}
record LikePostCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements InstagramMediaPostModelCommand {}
record ModeratePostCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements InstagramMediaPostModelCommand {}

interface InstagramMediaPostModelRepository {
    Optional<InstagramMediaPostModel> findById(UUID id);
    void save(InstagramMediaPostModel aggregate, long expectedVersion);
}

interface InstagramMediaPostModelPolicy {
    Decision evaluate(InstagramMediaPostModel aggregate, InstagramMediaPostModelCommand command);
}

final class MediaPost {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class InstagramMediaPostModel {
    private final UUID id;
    private final List<MediaPost> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private InstagramMediaPostModelStatus status;
    private long version;

    InstagramMediaPostModel(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = InstagramMediaPostModelStatus.DRAFT;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    InstagramMediaPostModelStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void createPost(CreatePostCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run createPost when aggregate is terminal");
    this.status = InstagramMediaPostModelStatus.PUBLISHED;
    this.version++;
    this.domainEvents.add(new InstagramMediaPostModelCreatePostEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void attachMedia(AttachMediaCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run attachMedia when aggregate is terminal");
    this.status = InstagramMediaPostModelStatus.FLAGGED;
    this.version++;
    this.domainEvents.add(new InstagramMediaPostModelAttachMediaEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void likePost(LikePostCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run likePost when aggregate is terminal");
    this.status = InstagramMediaPostModelStatus.HIDDEN;
    this.version++;
    this.domainEvents.add(new InstagramMediaPostModelLikePostEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void moderatePost(ModeratePostCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run moderatePost when aggregate is terminal");
    this.status = InstagramMediaPostModelStatus.DELETED;
    this.version++;
    this.domainEvents.add(new InstagramMediaPostModelModeratePostEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == InstagramMediaPostModelStatus.ARCHIVED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class InstagramMediaPostModelService {
    private final InstagramMediaPostModelRepository repository;
    private final InstagramMediaPostModelPolicy policy;
    private final Outbox outbox;

    InstagramMediaPostModelService(InstagramMediaPostModelRepository repository, InstagramMediaPostModelPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(InstagramMediaPostModelCommand command) {
        InstagramMediaPostModel aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("InstagramMediaPostModel not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof CreatePostCommand c) aggregate.createPost(c);
        if (command instanceof AttachMediaCommand c) aggregate.attachMedia(c);
        if (command instanceof LikePostCommand c) aggregate.likePost(c);
        if (command instanceof ModeratePostCommand c) aggregate.moderatePost(c);
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

- Persist `InstagramMediaPostModel` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `InstagramMediaPostModel` invariants and each command method.
- State-machine test all valid and invalid `InstagramMediaPostModelStatus` transitions.
- Contract test every `InstagramMediaPostModelRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `InstagramMediaPostModel` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `InstagramMediaPostModelService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
