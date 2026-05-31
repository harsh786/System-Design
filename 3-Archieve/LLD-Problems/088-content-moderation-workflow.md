# 088. Design Content Moderation Workflow

Source problem: `Design content moderation workflow.`  
Category: `Trust/safety`  
Primary focus: `review states, policies, escalation, appeals`  
Archetype: `state-workflow`

## 1. Interview Framing

Design `content moderation workflow` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `content moderation workflow` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `REPORTED, QUEUED, UNDER_REVIEW, ACTIONED, APPEALED`.
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

- `Reporter`
- `Moderator`
- `AppealsReviewer`

Primary use cases:

- `submitReport` command on `ContentModerationWorkflow`
- `assignReview` command on `ContentModerationWorkflow`
- `applyDecision` command on `ContentModerationWorkflow`
- `handleAppeal` command on `ContentModerationWorkflow`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `ContentModerationWorkflow` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `ContentItem, Report, ReviewTask, PolicyDecision, Appeal` | Have identity and change over time under the aggregate. |
| Value objects | `ContentId, ReasonCode, Severity, ReviewerId` | Immutable concepts compared by value. |
| Policies | `ContentModerationWorkflowPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `ContentModerationWorkflowRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
REPORTED, QUEUED, UNDER_REVIEW, ACTIONED, APPEALED, RESTORED
```

Invariants:

- `ContentModerationWorkflow` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `ContentModerationWorkflowService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `ContentModerationWorkflow` | Composes | ContentItem, Report, ReviewTask | Owns invariants and lifecycle transitions. |
| `ContentModerationWorkflowRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `ContentModerationWorkflowPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class ContentModerationWorkflow {
  +UUID id
  +ContentModerationWorkflowStatus status
  +long version
  +validateInvariants()
}
class ContentModerationWorkflowService {
  +handle(command)
}
class ContentModerationWorkflowRepository {
  <<interface>>
  +findById(UUID id) ContentModerationWorkflow
  +save(ContentModerationWorkflow aggregate, long expectedVersion)
}
class ContentModerationWorkflowPolicy {
  <<interface>>
  +evaluate(context) Decision
}
ContentModerationWorkflowService --> ContentModerationWorkflowRepository
ContentModerationWorkflowService --> ContentModerationWorkflowPolicy
ContentModerationWorkflowService --> ContentModerationWorkflow
class ContentItem {
  +UUID id
  +validate()
}
ContentModerationWorkflow "1" o-- "many" ContentItem
class Report {
  +UUID id
  +validate()
}
ContentModerationWorkflow "1" o-- "many" Report
class ReviewTask {
  +UUID id
  +validate()
}
ContentModerationWorkflow "1" o-- "many" ReviewTask
class PolicyDecision {
  +UUID id
  +validate()
}
ContentModerationWorkflow "1" o-- "many" PolicyDecision
class ContentId {
  <<value object>>
}
ContentModerationWorkflow ..> ContentId
class ReasonCode {
  <<value object>>
}
ContentModerationWorkflow ..> ReasonCode
class Severity {
  <<value object>>
}
ContentModerationWorkflow ..> Severity
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as ContentModerationWorkflowService
participant Repo as ContentModerationWorkflowRepository
participant Policy as ContentModerationWorkflowPolicy
participant Agg as ContentModerationWorkflow
participant Outbox
Client->>Service: submitReport(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: submitReport(command)
Agg-->>Service: ContentModerationWorkflowSubmitReportEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.contentmoderationworkflow;

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

enum ContentModerationWorkflowStatus {
    REPORTED,
    QUEUED,
    UNDER_REVIEW,
    ACTIONED,
    APPEALED,
    RESTORED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record ContentModerationWorkflowSubmitReportEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ContentModerationWorkflowAssignReviewEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ContentModerationWorkflowApplyDecisionEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ContentModerationWorkflowHandleAppealEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface ContentModerationWorkflowCommand permits SubmitReportCommand, AssignReviewCommand, ApplyDecisionCommand, HandleAppealCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record SubmitReportCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ContentModerationWorkflowCommand {}
record AssignReviewCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ContentModerationWorkflowCommand {}
record ApplyDecisionCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ContentModerationWorkflowCommand {}
record HandleAppealCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ContentModerationWorkflowCommand {}

interface ContentModerationWorkflowRepository {
    Optional<ContentModerationWorkflow> findById(UUID id);
    void save(ContentModerationWorkflow aggregate, long expectedVersion);
}

interface ContentModerationWorkflowPolicy {
    Decision evaluate(ContentModerationWorkflow aggregate, ContentModerationWorkflowCommand command);
}

final class ContentItem {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class ContentModerationWorkflow {
    private final UUID id;
    private final List<ContentItem> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private ContentModerationWorkflowStatus status;
    private long version;

    ContentModerationWorkflow(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = ContentModerationWorkflowStatus.REPORTED;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    ContentModerationWorkflowStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void submitReport(SubmitReportCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run submitReport when aggregate is terminal");
    this.status = ContentModerationWorkflowStatus.QUEUED;
    this.version++;
    this.domainEvents.add(new ContentModerationWorkflowSubmitReportEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void assignReview(AssignReviewCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run assignReview when aggregate is terminal");
    this.status = ContentModerationWorkflowStatus.UNDER_REVIEW;
    this.version++;
    this.domainEvents.add(new ContentModerationWorkflowAssignReviewEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void applyDecision(ApplyDecisionCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run applyDecision when aggregate is terminal");
    this.status = ContentModerationWorkflowStatus.ACTIONED;
    this.version++;
    this.domainEvents.add(new ContentModerationWorkflowApplyDecisionEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void handleAppeal(HandleAppealCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run handleAppeal when aggregate is terminal");
    this.status = ContentModerationWorkflowStatus.APPEALED;
    this.version++;
    this.domainEvents.add(new ContentModerationWorkflowHandleAppealEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == ContentModerationWorkflowStatus.RESTORED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class ContentModerationWorkflowService {
    private final ContentModerationWorkflowRepository repository;
    private final ContentModerationWorkflowPolicy policy;
    private final Outbox outbox;

    ContentModerationWorkflowService(ContentModerationWorkflowRepository repository, ContentModerationWorkflowPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(ContentModerationWorkflowCommand command) {
        ContentModerationWorkflow aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("ContentModerationWorkflow not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof SubmitReportCommand c) aggregate.submitReport(c);
        if (command instanceof AssignReviewCommand c) aggregate.assignReview(c);
        if (command instanceof ApplyDecisionCommand c) aggregate.applyDecision(c);
        if (command instanceof HandleAppealCommand c) aggregate.handleAppeal(c);
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

- Persist `ContentModerationWorkflow` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `ContentModerationWorkflow` invariants and each command method.
- State-machine test all valid and invalid `ContentModerationWorkflowStatus` transitions.
- Contract test every `ContentModerationWorkflowRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `ContentModerationWorkflow` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `ContentModerationWorkflowService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
