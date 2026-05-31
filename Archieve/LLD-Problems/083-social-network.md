# 083. Design Social Network LLD

Source problem: `Design social network LLD.`  
Category: `Social`  
Primary focus: `profiles, friendships, posts, comments, privacy`  
Archetype: `domain`

## 1. Interview Framing

Design `social network LLD` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `social network LLD` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `ACTIVE, FRIEND_REQUESTED, FRIENDS, BLOCKED, DEACTIVATED`.
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
- `Friend`
- `PrivacyService`

Primary use cases:

- `sendFriendRequest` command on `SocialNetwork`
- `acceptFriendRequest` command on `SocialNetwork`
- `createPost` command on `SocialNetwork`
- `commentOnPost` command on `SocialNetwork`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `SocialNetwork` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Profile, Friendship, Post, Comment, PrivacySetting` | Have identity and change over time under the aggregate. |
| Value objects | `UserId, PostId, Visibility, Timestamp` | Immutable concepts compared by value. |
| Policies | `SocialNetworkPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `SocialNetworkRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
ACTIVE, FRIEND_REQUESTED, FRIENDS, BLOCKED, DEACTIVATED
```

Invariants:

- `SocialNetwork` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `SocialNetworkService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `SocialNetwork` | Composes | Profile, Friendship, Post | Owns invariants and lifecycle transitions. |
| `SocialNetworkRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `SocialNetworkPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class SocialNetwork {
  +UUID id
  +SocialNetworkStatus status
  +long version
  +validateInvariants()
}
class SocialNetworkService {
  +handle(command)
}
class SocialNetworkRepository {
  <<interface>>
  +findById(UUID id) SocialNetwork
  +save(SocialNetwork aggregate, long expectedVersion)
}
class SocialNetworkPolicy {
  <<interface>>
  +evaluate(context) Decision
}
SocialNetworkService --> SocialNetworkRepository
SocialNetworkService --> SocialNetworkPolicy
SocialNetworkService --> SocialNetwork
class Profile {
  +UUID id
  +validate()
}
SocialNetwork "1" o-- "many" Profile
class Friendship {
  +UUID id
  +validate()
}
SocialNetwork "1" o-- "many" Friendship
class Post {
  +UUID id
  +validate()
}
SocialNetwork "1" o-- "many" Post
class Comment {
  +UUID id
  +validate()
}
SocialNetwork "1" o-- "many" Comment
class UserId {
  <<value object>>
}
SocialNetwork ..> UserId
class PostId {
  <<value object>>
}
SocialNetwork ..> PostId
class Visibility {
  <<value object>>
}
SocialNetwork ..> Visibility
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as SocialNetworkService
participant Repo as SocialNetworkRepository
participant Policy as SocialNetworkPolicy
participant Agg as SocialNetwork
participant Outbox
Client->>Service: sendFriendRequest(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: sendFriendRequest(command)
Agg-->>Service: SocialNetworkSendFriendRequestEvent
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
package lld.socialnetwork;

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

enum SocialNetworkStatus {
    ACTIVE,
    FRIEND_REQUESTED,
    FRIENDS,
    BLOCKED,
    DEACTIVATED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record SocialNetworkSendFriendRequestEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record SocialNetworkAcceptFriendRequestEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record SocialNetworkCreatePostEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record SocialNetworkCommentOnPostEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface SocialNetworkCommand permits SendFriendRequestCommand, AcceptFriendRequestCommand, CreatePostCommand, CommentOnPostCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record SendFriendRequestCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SocialNetworkCommand {}
record AcceptFriendRequestCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SocialNetworkCommand {}
record CreatePostCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SocialNetworkCommand {}
record CommentOnPostCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SocialNetworkCommand {}

interface SocialNetworkRepository {
    Optional<SocialNetwork> findById(UUID id);
    void save(SocialNetwork aggregate, long expectedVersion);
}

interface SocialNetworkPolicy {
    Decision evaluate(SocialNetwork aggregate, SocialNetworkCommand command);
}

final class Profile {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class SocialNetwork {
    private final UUID id;
    private final List<Profile> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private SocialNetworkStatus status;
    private long version;

    SocialNetwork(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = SocialNetworkStatus.ACTIVE;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    SocialNetworkStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void sendFriendRequest(SendFriendRequestCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run sendFriendRequest when aggregate is terminal");
    this.status = SocialNetworkStatus.FRIEND_REQUESTED;
    this.version++;
    this.domainEvents.add(new SocialNetworkSendFriendRequestEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void acceptFriendRequest(AcceptFriendRequestCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run acceptFriendRequest when aggregate is terminal");
    this.status = SocialNetworkStatus.FRIENDS;
    this.version++;
    this.domainEvents.add(new SocialNetworkAcceptFriendRequestEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void createPost(CreatePostCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run createPost when aggregate is terminal");
    this.status = SocialNetworkStatus.BLOCKED;
    this.version++;
    this.domainEvents.add(new SocialNetworkCreatePostEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void commentOnPost(CommentOnPostCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run commentOnPost when aggregate is terminal");
    this.status = SocialNetworkStatus.DEACTIVATED;
    this.version++;
    this.domainEvents.add(new SocialNetworkCommentOnPostEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == SocialNetworkStatus.DEACTIVATED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class SocialNetworkService {
    private final SocialNetworkRepository repository;
    private final SocialNetworkPolicy policy;
    private final Outbox outbox;

    SocialNetworkService(SocialNetworkRepository repository, SocialNetworkPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(SocialNetworkCommand command) {
        SocialNetwork aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("SocialNetwork not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof SendFriendRequestCommand c) aggregate.sendFriendRequest(c);
        if (command instanceof AcceptFriendRequestCommand c) aggregate.acceptFriendRequest(c);
        if (command instanceof CreatePostCommand c) aggregate.createPost(c);
        if (command instanceof CommentOnPostCommand c) aggregate.commentOnPost(c);
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

- Persist `SocialNetwork` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `SocialNetwork` invariants and each command method.
- State-machine test all valid and invalid `SocialNetworkStatus` transitions.
- Contract test every `SocialNetworkRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `SocialNetwork` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `SocialNetworkService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
