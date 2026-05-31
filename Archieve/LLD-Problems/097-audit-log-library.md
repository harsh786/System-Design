# 097. Design Audit Log Library

Source problem: `Design audit log library.`  
Category: `Security/compliance`  
Primary focus: `immutable events, redaction, retention, query`  
Archetype: `domain`

## 1. Interview Framing

Design `audit log library` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `audit log library` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `ACCEPTING, APPENDED, SEALED, REDACTED, EXPIRED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `Application`
- `Auditor`
- `RetentionWorker`

Primary use cases:

- `appendEvent` command on `AuditLogLibrary`
- `redactSensitiveFields` command on `AuditLogLibrary`
- `queryEvents` command on `AuditLogLibrary`
- `applyRetention` command on `AuditLogLibrary`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `AuditLogLibrary` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `AuditEvent, AuditStream, RedactionPolicy, RetentionPolicy, Query` | Have identity and change over time under the aggregate. |
| Value objects | `EventId, ActorId, ResourceId, Timestamp` | Immutable concepts compared by value. |
| Policies | `AuditLogLibraryPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `AuditLogLibraryRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
ACCEPTING, APPENDED, SEALED, REDACTED, EXPIRED
```

Invariants:

- `AuditLogLibrary` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `AuditLogLibraryService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `AuditLogLibrary` | Composes | AuditEvent, AuditStream, RedactionPolicy | Owns invariants and lifecycle transitions. |
| `AuditLogLibraryRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `AuditLogLibraryPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class AuditLogLibrary {
  +UUID id
  +AuditLogLibraryStatus status
  +long version
  +validateInvariants()
}
class AuditLogLibraryService {
  +handle(command)
}
class AuditLogLibraryRepository {
  <<interface>>
  +findById(UUID id) AuditLogLibrary
  +save(AuditLogLibrary aggregate, long expectedVersion)
}
class AuditLogLibraryPolicy {
  <<interface>>
  +evaluate(context) Decision
}
AuditLogLibraryService --> AuditLogLibraryRepository
AuditLogLibraryService --> AuditLogLibraryPolicy
AuditLogLibraryService --> AuditLogLibrary
class AuditEvent {
  +UUID id
  +validate()
}
AuditLogLibrary "1" o-- "many" AuditEvent
class AuditStream {
  +UUID id
  +validate()
}
AuditLogLibrary "1" o-- "many" AuditStream
class RedactionPolicy {
  +UUID id
  +validate()
}
AuditLogLibrary "1" o-- "many" RedactionPolicy
class RetentionPolicy {
  +UUID id
  +validate()
}
AuditLogLibrary "1" o-- "many" RetentionPolicy
class EventId {
  <<value object>>
}
AuditLogLibrary ..> EventId
class ActorId {
  <<value object>>
}
AuditLogLibrary ..> ActorId
class ResourceId {
  <<value object>>
}
AuditLogLibrary ..> ResourceId
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as AuditLogLibraryService
participant Repo as AuditLogLibraryRepository
participant Policy as AuditLogLibraryPolicy
participant Agg as AuditLogLibrary
participant Outbox
Client->>Service: appendEvent(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: appendEvent(command)
Agg-->>Service: AuditLogLibraryAppendEventEvent
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
package lld.auditloglibrary;

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

enum AuditLogLibraryStatus {
    ACCEPTING,
    APPENDED,
    SEALED,
    REDACTED,
    EXPIRED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record AuditLogLibraryAppendEventEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record AuditLogLibraryRedactSensitiveFieldsEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record AuditLogLibraryQueryEventsEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record AuditLogLibraryApplyRetentionEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface AuditLogLibraryCommand permits AppendEventCommand, RedactSensitiveFieldsCommand, QueryEventsCommand, ApplyRetentionCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record AppendEventCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements AuditLogLibraryCommand {}
record RedactSensitiveFieldsCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements AuditLogLibraryCommand {}
record QueryEventsCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements AuditLogLibraryCommand {}
record ApplyRetentionCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements AuditLogLibraryCommand {}

interface AuditLogLibraryRepository {
    Optional<AuditLogLibrary> findById(UUID id);
    void save(AuditLogLibrary aggregate, long expectedVersion);
}

interface AuditLogLibraryPolicy {
    Decision evaluate(AuditLogLibrary aggregate, AuditLogLibraryCommand command);
}

final class AuditEvent {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class AuditLogLibrary {
    private final UUID id;
    private final List<AuditEvent> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private AuditLogLibraryStatus status;
    private long version;

    AuditLogLibrary(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = AuditLogLibraryStatus.ACCEPTING;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    AuditLogLibraryStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void appendEvent(AppendEventCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run appendEvent when aggregate is terminal");
    this.status = AuditLogLibraryStatus.APPENDED;
    this.version++;
    this.domainEvents.add(new AuditLogLibraryAppendEventEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void redactSensitiveFields(RedactSensitiveFieldsCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run redactSensitiveFields when aggregate is terminal");
    this.status = AuditLogLibraryStatus.SEALED;
    this.version++;
    this.domainEvents.add(new AuditLogLibraryRedactSensitiveFieldsEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void queryEvents(QueryEventsCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run queryEvents when aggregate is terminal");
    this.status = AuditLogLibraryStatus.REDACTED;
    this.version++;
    this.domainEvents.add(new AuditLogLibraryQueryEventsEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void applyRetention(ApplyRetentionCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run applyRetention when aggregate is terminal");
    this.status = AuditLogLibraryStatus.EXPIRED;
    this.version++;
    this.domainEvents.add(new AuditLogLibraryApplyRetentionEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == AuditLogLibraryStatus.EXPIRED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class AuditLogLibraryService {
    private final AuditLogLibraryRepository repository;
    private final AuditLogLibraryPolicy policy;
    private final Outbox outbox;

    AuditLogLibraryService(AuditLogLibraryRepository repository, AuditLogLibraryPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(AuditLogLibraryCommand command) {
        AuditLogLibrary aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("AuditLogLibrary not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof AppendEventCommand c) aggregate.appendEvent(c);
        if (command instanceof RedactSensitiveFieldsCommand c) aggregate.redactSensitiveFields(c);
        if (command instanceof QueryEventsCommand c) aggregate.queryEvents(c);
        if (command instanceof ApplyRetentionCommand c) aggregate.applyRetention(c);
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

- Persist `AuditLogLibrary` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `AuditLogLibrary` invariants and each command method.
- State-machine test all valid and invalid `AuditLogLibraryStatus` transitions.
- Contract test every `AuditLogLibraryRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `AuditLogLibrary` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `AuditLogLibraryService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
