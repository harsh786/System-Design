# 072. Design Text Editor

Source problem: `Design text editor.`  
Category: `Editor`  
Primary focus: `buffer, cursor, undo/redo, command pattern`  
Archetype: `domain`

## 1. Interview Framing

Design `text editor` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `text editor` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `CLEAN, DIRTY, EDITING, UNDOING, REDOING`.
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
- `CommandInvoker`
- `StorageProvider`

Primary use cases:

- `insertText` command on `TextEditor`
- `deleteRange` command on `TextEditor`
- `undo` command on `TextEditor`
- `redo` command on `TextEditor`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `TextEditor` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Document, Buffer, Cursor, Selection, UndoStack` | Have identity and change over time under the aggregate. |
| Value objects | `Position, Range, Text, Revision` | Immutable concepts compared by value. |
| Policies | `TextEditorPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `TextEditorRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
CLEAN, DIRTY, EDITING, UNDOING, REDOING, SAVED
```

Invariants:

- `TextEditor` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `TextEditorService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `TextEditor` | Composes | Document, Buffer, Cursor | Owns invariants and lifecycle transitions. |
| `TextEditorRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `TextEditorPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class TextEditor {
  +UUID id
  +TextEditorStatus status
  +long version
  +validateInvariants()
}
class TextEditorService {
  +handle(command)
}
class TextEditorRepository {
  <<interface>>
  +findById(UUID id) TextEditor
  +save(TextEditor aggregate, long expectedVersion)
}
class TextEditorPolicy {
  <<interface>>
  +evaluate(context) Decision
}
TextEditorService --> TextEditorRepository
TextEditorService --> TextEditorPolicy
TextEditorService --> TextEditor
class Document {
  +UUID id
  +validate()
}
TextEditor "1" o-- "many" Document
class Buffer {
  +UUID id
  +validate()
}
TextEditor "1" o-- "many" Buffer
class Cursor {
  +UUID id
  +validate()
}
TextEditor "1" o-- "many" Cursor
class Selection {
  +UUID id
  +validate()
}
TextEditor "1" o-- "many" Selection
class Position {
  <<value object>>
}
TextEditor ..> Position
class Range {
  <<value object>>
}
TextEditor ..> Range
class Text {
  <<value object>>
}
TextEditor ..> Text
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as TextEditorService
participant Repo as TextEditorRepository
participant Policy as TextEditorPolicy
participant Agg as TextEditor
participant Outbox
Client->>Service: insertText(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: insertText(command)
Agg-->>Service: TextEditorInsertTextEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| Command | Represent user or system intent as retryable, auditable, and optionally undoable objects. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.texteditor;

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

enum TextEditorStatus {
    CLEAN,
    DIRTY,
    EDITING,
    UNDOING,
    REDOING,
    SAVED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record TextEditorInsertTextEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record TextEditorDeleteRangeEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record TextEditorUndoEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record TextEditorRedoEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface TextEditorCommand permits InsertTextCommand, DeleteRangeCommand, UndoCommand, RedoCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record InsertTextCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements TextEditorCommand {}
record DeleteRangeCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements TextEditorCommand {}
record UndoCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements TextEditorCommand {}
record RedoCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements TextEditorCommand {}

interface TextEditorRepository {
    Optional<TextEditor> findById(UUID id);
    void save(TextEditor aggregate, long expectedVersion);
}

interface TextEditorPolicy {
    Decision evaluate(TextEditor aggregate, TextEditorCommand command);
}

final class Document {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class TextEditor {
    private final UUID id;
    private final List<Document> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private TextEditorStatus status;
    private long version;

    TextEditor(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = TextEditorStatus.CLEAN;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    TextEditorStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void insertText(InsertTextCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run insertText when aggregate is terminal");
    this.status = TextEditorStatus.DIRTY;
    this.version++;
    this.domainEvents.add(new TextEditorInsertTextEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void deleteRange(DeleteRangeCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run deleteRange when aggregate is terminal");
    this.status = TextEditorStatus.EDITING;
    this.version++;
    this.domainEvents.add(new TextEditorDeleteRangeEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void undo(UndoCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run undo when aggregate is terminal");
    this.status = TextEditorStatus.UNDOING;
    this.version++;
    this.domainEvents.add(new TextEditorUndoEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void redo(RedoCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run redo when aggregate is terminal");
    this.status = TextEditorStatus.REDOING;
    this.version++;
    this.domainEvents.add(new TextEditorRedoEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == TextEditorStatus.SAVED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class TextEditorService {
    private final TextEditorRepository repository;
    private final TextEditorPolicy policy;
    private final Outbox outbox;

    TextEditorService(TextEditorRepository repository, TextEditorPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(TextEditorCommand command) {
        TextEditor aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("TextEditor not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof InsertTextCommand c) aggregate.insertText(c);
        if (command instanceof DeleteRangeCommand c) aggregate.deleteRange(c);
        if (command instanceof UndoCommand c) aggregate.undo(c);
        if (command instanceof RedoCommand c) aggregate.redo(c);
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

- Persist `TextEditor` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Represent user or system intent as retryable, auditable, and optionally undoable objects. | `Command` |
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `TextEditor` invariants and each command method.
- State-machine test all valid and invalid `TextEditorStatus` transitions.
- Contract test every `TextEditorRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `TextEditor` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `TextEditorService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
