# 073. Design Spreadsheet

Source problem: `Design spreadsheet.`  
Category: `Productivity`  
Primary focus: `formula graph, dependency evaluation, cycle detection`  
Archetype: `domain`

## 1. Interview Framing

Design `spreadsheet` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `spreadsheet` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `READY, EDITING, RECALCULATING, CYCLE_DETECTED, SAVED`.
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
- `FormulaEngine`
- `StorageProvider`

Primary use cases:

- `setCell` command on `Spreadsheet`
- `evaluateFormula` command on `Spreadsheet`
- `recalculateDependents` command on `Spreadsheet`
- `detectCycle` command on `Spreadsheet`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `Spreadsheet` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Workbook, Sheet, Cell, Formula, DependencyGraph` | Have identity and change over time under the aggregate. |
| Value objects | `CellAddress, FormulaText, Value, Version` | Immutable concepts compared by value. |
| Policies | `SpreadsheetPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `SpreadsheetRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
READY, EDITING, RECALCULATING, CYCLE_DETECTED, SAVED
```

Invariants:

- `Spreadsheet` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `SpreadsheetService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `Spreadsheet` | Composes | Workbook, Sheet, Cell | Owns invariants and lifecycle transitions. |
| `SpreadsheetRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `SpreadsheetPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class Spreadsheet {
  +UUID id
  +SpreadsheetStatus status
  +long version
  +validateInvariants()
}
class SpreadsheetService {
  +handle(command)
}
class SpreadsheetRepository {
  <<interface>>
  +findById(UUID id) Spreadsheet
  +save(Spreadsheet aggregate, long expectedVersion)
}
class SpreadsheetPolicy {
  <<interface>>
  +evaluate(context) Decision
}
SpreadsheetService --> SpreadsheetRepository
SpreadsheetService --> SpreadsheetPolicy
SpreadsheetService --> Spreadsheet
class Workbook {
  +UUID id
  +validate()
}
Spreadsheet "1" o-- "many" Workbook
class Sheet {
  +UUID id
  +validate()
}
Spreadsheet "1" o-- "many" Sheet
class Cell {
  +UUID id
  +validate()
}
Spreadsheet "1" o-- "many" Cell
class Formula {
  +UUID id
  +validate()
}
Spreadsheet "1" o-- "many" Formula
class CellAddress {
  <<value object>>
}
Spreadsheet ..> CellAddress
class FormulaText {
  <<value object>>
}
Spreadsheet ..> FormulaText
class Value {
  <<value object>>
}
Spreadsheet ..> Value
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as SpreadsheetService
participant Repo as SpreadsheetRepository
participant Policy as SpreadsheetPolicy
participant Agg as Spreadsheet
participant Outbox
Client->>Service: setCell(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: setCell(command)
Agg-->>Service: SpreadsheetSetCellEvent
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
package lld.spreadsheet;

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

enum SpreadsheetStatus {
    READY,
    EDITING,
    RECALCULATING,
    CYCLE_DETECTED,
    SAVED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record SpreadsheetSetCellEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record SpreadsheetEvaluateFormulaEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record SpreadsheetRecalculateDependentsEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record SpreadsheetDetectCycleEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface SpreadsheetCommand permits SetCellCommand, EvaluateFormulaCommand, RecalculateDependentsCommand, DetectCycleCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record SetCellCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SpreadsheetCommand {}
record EvaluateFormulaCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SpreadsheetCommand {}
record RecalculateDependentsCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SpreadsheetCommand {}
record DetectCycleCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SpreadsheetCommand {}

interface SpreadsheetRepository {
    Optional<Spreadsheet> findById(UUID id);
    void save(Spreadsheet aggregate, long expectedVersion);
}

interface SpreadsheetPolicy {
    Decision evaluate(Spreadsheet aggregate, SpreadsheetCommand command);
}

final class Workbook {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class Spreadsheet {
    private final UUID id;
    private final List<Workbook> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private SpreadsheetStatus status;
    private long version;

    Spreadsheet(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = SpreadsheetStatus.READY;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    SpreadsheetStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void setCell(SetCellCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run setCell when aggregate is terminal");
    this.status = SpreadsheetStatus.EDITING;
    this.version++;
    this.domainEvents.add(new SpreadsheetSetCellEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void evaluateFormula(EvaluateFormulaCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run evaluateFormula when aggregate is terminal");
    this.status = SpreadsheetStatus.RECALCULATING;
    this.version++;
    this.domainEvents.add(new SpreadsheetEvaluateFormulaEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void recalculateDependents(RecalculateDependentsCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run recalculateDependents when aggregate is terminal");
    this.status = SpreadsheetStatus.CYCLE_DETECTED;
    this.version++;
    this.domainEvents.add(new SpreadsheetRecalculateDependentsEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void detectCycle(DetectCycleCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run detectCycle when aggregate is terminal");
    this.status = SpreadsheetStatus.SAVED;
    this.version++;
    this.domainEvents.add(new SpreadsheetDetectCycleEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == SpreadsheetStatus.SAVED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class SpreadsheetService {
    private final SpreadsheetRepository repository;
    private final SpreadsheetPolicy policy;
    private final Outbox outbox;

    SpreadsheetService(SpreadsheetRepository repository, SpreadsheetPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(SpreadsheetCommand command) {
        Spreadsheet aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("Spreadsheet not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof SetCellCommand c) aggregate.setCell(c);
        if (command instanceof EvaluateFormulaCommand c) aggregate.evaluateFormula(c);
        if (command instanceof RecalculateDependentsCommand c) aggregate.recalculateDependents(c);
        if (command instanceof DetectCycleCommand c) aggregate.detectCycle(c);
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

- Persist `Spreadsheet` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `Spreadsheet` invariants and each command method.
- State-machine test all valid and invalid `SpreadsheetStatus` transitions.
- Contract test every `SpreadsheetRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `Spreadsheet` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `SpreadsheetService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
