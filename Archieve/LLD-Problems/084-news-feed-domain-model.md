# 084. Design News Feed Domain Model

Source problem: `Design news feed domain model.`  
Category: `Social/feed`  
Primary focus: `post aggregate, ranking policy, visibility rules`  
Archetype: `rules`

## 1. Interview Framing

Design `news feed domain model` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `news feed domain model` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `GENERATING, RANKED, FILTERED, DELIVERED, STALE`.
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
- `FeedService`
- `RankingService`

Primary use cases:

- `publishPost` command on `NewsFeedDomainModel`
- `rankFeed` command on `NewsFeedDomainModel`
- `filterVisibility` command on `NewsFeedDomainModel`
- `pageFeed` command on `NewsFeedDomainModel`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `NewsFeedDomainModel` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Feed, Post, FeedItem, RankingSignal, VisibilityRule` | Have identity and change over time under the aggregate. |
| Value objects | `UserId, Score, Cursor, Visibility` | Immutable concepts compared by value. |
| Policies | `NewsFeedDomainModelPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `NewsFeedDomainModelRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
GENERATING, RANKED, FILTERED, DELIVERED, STALE
```

Invariants:

- `NewsFeedDomainModel` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `NewsFeedDomainModelService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `NewsFeedDomainModel` | Composes | Feed, Post, FeedItem | Owns invariants and lifecycle transitions. |
| `NewsFeedDomainModelRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `NewsFeedDomainModelPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class NewsFeedDomainModel {
  +UUID id
  +NewsFeedDomainModelStatus status
  +long version
  +validateInvariants()
}
class NewsFeedDomainModelService {
  +handle(command)
}
class NewsFeedDomainModelRepository {
  <<interface>>
  +findById(UUID id) NewsFeedDomainModel
  +save(NewsFeedDomainModel aggregate, long expectedVersion)
}
class NewsFeedDomainModelPolicy {
  <<interface>>
  +evaluate(context) Decision
}
NewsFeedDomainModelService --> NewsFeedDomainModelRepository
NewsFeedDomainModelService --> NewsFeedDomainModelPolicy
NewsFeedDomainModelService --> NewsFeedDomainModel
class Feed {
  +UUID id
  +validate()
}
NewsFeedDomainModel "1" o-- "many" Feed
class Post {
  +UUID id
  +validate()
}
NewsFeedDomainModel "1" o-- "many" Post
class FeedItem {
  +UUID id
  +validate()
}
NewsFeedDomainModel "1" o-- "many" FeedItem
class RankingSignal {
  +UUID id
  +validate()
}
NewsFeedDomainModel "1" o-- "many" RankingSignal
class UserId {
  <<value object>>
}
NewsFeedDomainModel ..> UserId
class Score {
  <<value object>>
}
NewsFeedDomainModel ..> Score
class Cursor {
  <<value object>>
}
NewsFeedDomainModel ..> Cursor
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as NewsFeedDomainModelService
participant Repo as NewsFeedDomainModelRepository
participant Policy as NewsFeedDomainModelPolicy
participant Agg as NewsFeedDomainModel
participant Outbox
Client->>Service: publishPost(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: publishPost(command)
Agg-->>Service: NewsFeedDomainModelPublishPostEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| Strategy | Swap algorithms such as pricing, ranking, scheduling, matching, or retry without changing the aggregate. |
| Specification | Compose business predicates and keep rule evaluation explainable. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.newsfeeddomainmodel;

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

enum NewsFeedDomainModelStatus {
    GENERATING,
    RANKED,
    FILTERED,
    DELIVERED,
    STALE
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record NewsFeedDomainModelPublishPostEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record NewsFeedDomainModelRankFeedEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record NewsFeedDomainModelFilterVisibilityEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record NewsFeedDomainModelPageFeedEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface NewsFeedDomainModelCommand permits PublishPostCommand, RankFeedCommand, FilterVisibilityCommand, PageFeedCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record PublishPostCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements NewsFeedDomainModelCommand {}
record RankFeedCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements NewsFeedDomainModelCommand {}
record FilterVisibilityCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements NewsFeedDomainModelCommand {}
record PageFeedCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements NewsFeedDomainModelCommand {}

interface NewsFeedDomainModelRepository {
    Optional<NewsFeedDomainModel> findById(UUID id);
    void save(NewsFeedDomainModel aggregate, long expectedVersion);
}

interface NewsFeedDomainModelPolicy {
    Decision evaluate(NewsFeedDomainModel aggregate, NewsFeedDomainModelCommand command);
}

final class Feed {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class NewsFeedDomainModel {
    private final UUID id;
    private final List<Feed> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private NewsFeedDomainModelStatus status;
    private long version;

    NewsFeedDomainModel(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = NewsFeedDomainModelStatus.GENERATING;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    NewsFeedDomainModelStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void publishPost(PublishPostCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run publishPost when aggregate is terminal");
    this.status = NewsFeedDomainModelStatus.RANKED;
    this.version++;
    this.domainEvents.add(new NewsFeedDomainModelPublishPostEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void rankFeed(RankFeedCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run rankFeed when aggregate is terminal");
    this.status = NewsFeedDomainModelStatus.FILTERED;
    this.version++;
    this.domainEvents.add(new NewsFeedDomainModelRankFeedEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void filterVisibility(FilterVisibilityCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run filterVisibility when aggregate is terminal");
    this.status = NewsFeedDomainModelStatus.DELIVERED;
    this.version++;
    this.domainEvents.add(new NewsFeedDomainModelFilterVisibilityEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void pageFeed(PageFeedCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run pageFeed when aggregate is terminal");
    this.status = NewsFeedDomainModelStatus.STALE;
    this.version++;
    this.domainEvents.add(new NewsFeedDomainModelPageFeedEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == NewsFeedDomainModelStatus.STALE;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class NewsFeedDomainModelService {
    private final NewsFeedDomainModelRepository repository;
    private final NewsFeedDomainModelPolicy policy;
    private final Outbox outbox;

    NewsFeedDomainModelService(NewsFeedDomainModelRepository repository, NewsFeedDomainModelPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(NewsFeedDomainModelCommand command) {
        NewsFeedDomainModel aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("NewsFeedDomainModel not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof PublishPostCommand c) aggregate.publishPost(c);
        if (command instanceof RankFeedCommand c) aggregate.rankFeed(c);
        if (command instanceof FilterVisibilityCommand c) aggregate.filterVisibility(c);
        if (command instanceof PageFeedCommand c) aggregate.pageFeed(c);
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

- Persist `NewsFeedDomainModel` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Compose business predicates and keep rule evaluation explainable. | `Specification` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `NewsFeedDomainModel` invariants and each command method.
- State-machine test all valid and invalid `NewsFeedDomainModelStatus` transitions.
- Contract test every `NewsFeedDomainModelRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `NewsFeedDomainModel` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `NewsFeedDomainModelService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
