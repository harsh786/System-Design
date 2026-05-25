# 089. Design Review/Rating System

Source problem: `Design review/rating system.`  
Category: `Social/commerce`  
Primary focus: `ratings, aggregates, moderation, fraud checks`  
Archetype: `domain`

## 1. Interview Framing

Design `review rating system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `review rating system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `SUBMITTED, PUBLISHED, FLAGGED, HIDDEN, DELETED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `Reviewer`
- `Merchant`
- `ModerationService`

Primary use cases:

- `submitReview` command on `ReviewRatingSystem`
- `calculateAggregate` command on `ReviewRatingSystem`
- `moderateReview` command on `ReviewRatingSystem`
- `detectFraud` command on `ReviewRatingSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `ReviewRatingSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Review, Rating, ReviewAggregate, ModerationCase, FraudSignal` | Have identity and change over time under the aggregate. |
| Value objects | `Stars, UserId, EntityId, Timestamp` | Immutable concepts compared by value. |
| Policies | `ReviewRatingSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `ReviewRatingSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
SUBMITTED, PUBLISHED, FLAGGED, HIDDEN, DELETED
```

Invariants:

- `ReviewRatingSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `ReviewRatingSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `ReviewRatingSystem` | Composes | Review, Rating, ReviewAggregate | Owns invariants and lifecycle transitions. |
| `ReviewRatingSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `ReviewRatingSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class ReviewRatingSystem {
  +UUID id
  +ReviewRatingSystemStatus status
  +long version
  +validateInvariants()
}
class ReviewRatingSystemService {
  +handle(command)
}
class ReviewRatingSystemRepository {
  <<interface>>
  +findById(UUID id) ReviewRatingSystem
  +save(ReviewRatingSystem aggregate, long expectedVersion)
}
class ReviewRatingSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
ReviewRatingSystemService --> ReviewRatingSystemRepository
ReviewRatingSystemService --> ReviewRatingSystemPolicy
ReviewRatingSystemService --> ReviewRatingSystem
class Review {
  +UUID id
  +validate()
}
ReviewRatingSystem "1" o-- "many" Review
class Rating {
  +UUID id
  +validate()
}
ReviewRatingSystem "1" o-- "many" Rating
class ReviewAggregate {
  +UUID id
  +validate()
}
ReviewRatingSystem "1" o-- "many" ReviewAggregate
class ModerationCase {
  +UUID id
  +validate()
}
ReviewRatingSystem "1" o-- "many" ModerationCase
class Stars {
  <<value object>>
}
ReviewRatingSystem ..> Stars
class UserId {
  <<value object>>
}
ReviewRatingSystem ..> UserId
class EntityId {
  <<value object>>
}
ReviewRatingSystem ..> EntityId
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as ReviewRatingSystemService
participant Repo as ReviewRatingSystemRepository
participant Policy as ReviewRatingSystemPolicy
participant Agg as ReviewRatingSystem
participant Outbox
Client->>Service: submitReview(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: submitReview(command)
Agg-->>Service: ReviewRatingSystemSubmitReviewEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| Specification | Compose business predicates and keep rule evaluation explainable. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.reviewratingsystem;

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

enum ReviewRatingSystemStatus {
    SUBMITTED,
    PUBLISHED,
    FLAGGED,
    HIDDEN,
    DELETED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record ReviewRatingSystemSubmitReviewEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ReviewRatingSystemCalculateAggregateEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ReviewRatingSystemModerateReviewEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ReviewRatingSystemDetectFraudEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface ReviewRatingSystemCommand permits SubmitReviewCommand, CalculateAggregateCommand, ModerateReviewCommand, DetectFraudCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record SubmitReviewCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ReviewRatingSystemCommand {}
record CalculateAggregateCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ReviewRatingSystemCommand {}
record ModerateReviewCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ReviewRatingSystemCommand {}
record DetectFraudCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ReviewRatingSystemCommand {}

interface ReviewRatingSystemRepository {
    Optional<ReviewRatingSystem> findById(UUID id);
    void save(ReviewRatingSystem aggregate, long expectedVersion);
}

interface ReviewRatingSystemPolicy {
    Decision evaluate(ReviewRatingSystem aggregate, ReviewRatingSystemCommand command);
}

final class Review {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class ReviewRatingSystem {
    private final UUID id;
    private final List<Review> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private ReviewRatingSystemStatus status;
    private long version;

    ReviewRatingSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = ReviewRatingSystemStatus.SUBMITTED;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    ReviewRatingSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void submitReview(SubmitReviewCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run submitReview when aggregate is terminal");
    this.status = ReviewRatingSystemStatus.PUBLISHED;
    this.version++;
    this.domainEvents.add(new ReviewRatingSystemSubmitReviewEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void calculateAggregate(CalculateAggregateCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run calculateAggregate when aggregate is terminal");
    this.status = ReviewRatingSystemStatus.FLAGGED;
    this.version++;
    this.domainEvents.add(new ReviewRatingSystemCalculateAggregateEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void moderateReview(ModerateReviewCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run moderateReview when aggregate is terminal");
    this.status = ReviewRatingSystemStatus.HIDDEN;
    this.version++;
    this.domainEvents.add(new ReviewRatingSystemModerateReviewEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void detectFraud(DetectFraudCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run detectFraud when aggregate is terminal");
    this.status = ReviewRatingSystemStatus.DELETED;
    this.version++;
    this.domainEvents.add(new ReviewRatingSystemDetectFraudEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == ReviewRatingSystemStatus.DELETED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class ReviewRatingSystemService {
    private final ReviewRatingSystemRepository repository;
    private final ReviewRatingSystemPolicy policy;
    private final Outbox outbox;

    ReviewRatingSystemService(ReviewRatingSystemRepository repository, ReviewRatingSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(ReviewRatingSystemCommand command) {
        ReviewRatingSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("ReviewRatingSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof SubmitReviewCommand c) aggregate.submitReview(c);
        if (command instanceof CalculateAggregateCommand c) aggregate.calculateAggregate(c);
        if (command instanceof ModerateReviewCommand c) aggregate.moderateReview(c);
        if (command instanceof DetectFraudCommand c) aggregate.detectFraud(c);
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

- Persist `ReviewRatingSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Compose business predicates and keep rule evaluation explainable. | `Specification` |
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `ReviewRatingSystem` invariants and each command method.
- State-machine test all valid and invalid `ReviewRatingSystemStatus` transitions.
- Contract test every `ReviewRatingSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `ReviewRatingSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `ReviewRatingSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
