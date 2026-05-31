# 077. Design Email Client Model

Source problem: `Design email client model.`  
Category: `Productivity`  
Primary focus: `folders, labels, threads, search, sync state`  
Archetype: `state-workflow`

## 1. Interview Framing

Design `email client model` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `email client model` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `SYNCING, READY, READ, ARCHIVED, DELETED`.
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

- `User`
- `MailServer`
- `SyncWorker`

Primary use cases:

- `syncMailbox` command on `EmailClientModel`
- `moveMessage` command on `EmailClientModel`
- `applyLabel` command on `EmailClientModel`
- `searchMessages` command on `EmailClientModel`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `EmailClientModel` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Mailbox, Folder, Message, Thread, Label` | Have identity and change over time under the aggregate. |
| Value objects | `MessageId, FolderId, SearchQuery, SyncToken` | Immutable concepts compared by value. |
| Policies | `EmailClientModelPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `EmailClientModelRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
SYNCING, READY, READ, ARCHIVED, DELETED, CONFLICTED
```

Invariants:

- `EmailClientModel` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `EmailClientModelService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `EmailClientModel` | Composes | Mailbox, Folder, Message | Owns invariants and lifecycle transitions. |
| `EmailClientModelRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `EmailClientModelPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class EmailClientModel {
  +UUID id
  +EmailClientModelStatus status
  +long version
  +validateInvariants()
}
class EmailClientModelService {
  +handle(command)
}
class EmailClientModelRepository {
  <<interface>>
  +findById(UUID id) EmailClientModel
  +save(EmailClientModel aggregate, long expectedVersion)
}
class EmailClientModelPolicy {
  <<interface>>
  +evaluate(context) Decision
}
EmailClientModelService --> EmailClientModelRepository
EmailClientModelService --> EmailClientModelPolicy
EmailClientModelService --> EmailClientModel
class Mailbox {
  +UUID id
  +validate()
}
EmailClientModel "1" o-- "many" Mailbox
class Folder {
  +UUID id
  +validate()
}
EmailClientModel "1" o-- "many" Folder
class Message {
  +UUID id
  +validate()
}
EmailClientModel "1" o-- "many" Message
class Thread {
  +UUID id
  +validate()
}
EmailClientModel "1" o-- "many" Thread
class MessageId {
  <<value object>>
}
EmailClientModel ..> MessageId
class FolderId {
  <<value object>>
}
EmailClientModel ..> FolderId
class SearchQuery {
  <<value object>>
}
EmailClientModel ..> SearchQuery
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as EmailClientModelService
participant Repo as EmailClientModelRepository
participant Policy as EmailClientModelPolicy
participant Agg as EmailClientModel
participant Outbox
Client->>Service: syncMailbox(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: syncMailbox(command)
Agg-->>Service: EmailClientModelSyncMailboxEvent
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
package lld.emailclientmodel;

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

enum EmailClientModelStatus {
    SYNCING,
    READY,
    READ,
    ARCHIVED,
    DELETED,
    CONFLICTED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record EmailClientModelSyncMailboxEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record EmailClientModelMoveMessageEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record EmailClientModelApplyLabelEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record EmailClientModelSearchMessagesEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface EmailClientModelCommand permits SyncMailboxCommand, MoveMessageCommand, ApplyLabelCommand, SearchMessagesCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record SyncMailboxCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements EmailClientModelCommand {}
record MoveMessageCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements EmailClientModelCommand {}
record ApplyLabelCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements EmailClientModelCommand {}
record SearchMessagesCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements EmailClientModelCommand {}

interface EmailClientModelRepository {
    Optional<EmailClientModel> findById(UUID id);
    void save(EmailClientModel aggregate, long expectedVersion);
}

interface EmailClientModelPolicy {
    Decision evaluate(EmailClientModel aggregate, EmailClientModelCommand command);
}

final class Mailbox {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class EmailClientModel {
    private final UUID id;
    private final List<Mailbox> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private EmailClientModelStatus status;
    private long version;

    EmailClientModel(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = EmailClientModelStatus.SYNCING;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    EmailClientModelStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void syncMailbox(SyncMailboxCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run syncMailbox when aggregate is terminal");
    this.status = EmailClientModelStatus.READY;
    this.version++;
    this.domainEvents.add(new EmailClientModelSyncMailboxEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void moveMessage(MoveMessageCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run moveMessage when aggregate is terminal");
    this.status = EmailClientModelStatus.READ;
    this.version++;
    this.domainEvents.add(new EmailClientModelMoveMessageEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void applyLabel(ApplyLabelCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run applyLabel when aggregate is terminal");
    this.status = EmailClientModelStatus.ARCHIVED;
    this.version++;
    this.domainEvents.add(new EmailClientModelApplyLabelEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void searchMessages(SearchMessagesCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run searchMessages when aggregate is terminal");
    this.status = EmailClientModelStatus.DELETED;
    this.version++;
    this.domainEvents.add(new EmailClientModelSearchMessagesEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == EmailClientModelStatus.CONFLICTED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class EmailClientModelService {
    private final EmailClientModelRepository repository;
    private final EmailClientModelPolicy policy;
    private final Outbox outbox;

    EmailClientModelService(EmailClientModelRepository repository, EmailClientModelPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(EmailClientModelCommand command) {
        EmailClientModel aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("EmailClientModel not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof SyncMailboxCommand c) aggregate.syncMailbox(c);
        if (command instanceof MoveMessageCommand c) aggregate.moveMessage(c);
        if (command instanceof ApplyLabelCommand c) aggregate.applyLabel(c);
        if (command instanceof SearchMessagesCommand c) aggregate.searchMessages(c);
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

- Persist `EmailClientModel` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `EmailClientModel` invariants and each command method.
- State-machine test all valid and invalid `EmailClientModelStatus` transitions.
- Contract test every `EmailClientModelRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `EmailClientModel` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `EmailClientModelService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
