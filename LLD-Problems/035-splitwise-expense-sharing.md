# 035. Design Splitwise Expense Sharing

Source problem: `Design splitwise expense sharing.`  
Category: `Fintech/social`  
Primary focus: `debt graph, simplification, settlements, invariants`  
Archetype: `finance`

## 1. Interview Framing

Design `splitwise expense sharing` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `splitwise expense sharing` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `OPEN, SIMPLIFIED, SETTLEMENT_PENDING, SETTLED, CANCELLED`.
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

- `Payer`
- `Participant`
- `SettlementService`

Primary use cases:

- `addExpense` command on `SplitwiseExpenseSharing`
- `simplifyDebts` command on `SplitwiseExpenseSharing`
- `recordSettlement` command on `SplitwiseExpenseSharing`
- `closeGroup` command on `SplitwiseExpenseSharing`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `SplitwiseExpenseSharing` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Group, Expense, Split, DebtEdge, Settlement` | Have identity and change over time under the aggregate. |
| Value objects | `Money, UserId, Ratio, ExpenseId` | Immutable concepts compared by value. |
| Policies | `SplitwiseExpenseSharingPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `SplitwiseExpenseSharingRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
OPEN, SIMPLIFIED, SETTLEMENT_PENDING, SETTLED, CANCELLED
```

Invariants:

- `SplitwiseExpenseSharing` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.
- Money and capacity changes are atomic within the transaction boundary.
- A repeated idempotency key returns the original result and never double-applies side effects.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `SplitwiseExpenseSharingService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `SplitwiseExpenseSharing` | Composes | Group, Expense, Split | Owns invariants and lifecycle transitions. |
| `SplitwiseExpenseSharingRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `SplitwiseExpenseSharingPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class SplitwiseExpenseSharing {
  +UUID id
  +SplitwiseExpenseSharingStatus status
  +long version
  +validateInvariants()
}
class SplitwiseExpenseSharingService {
  +handle(command)
}
class SplitwiseExpenseSharingRepository {
  <<interface>>
  +findById(UUID id) SplitwiseExpenseSharing
  +save(SplitwiseExpenseSharing aggregate, long expectedVersion)
}
class SplitwiseExpenseSharingPolicy {
  <<interface>>
  +evaluate(context) Decision
}
SplitwiseExpenseSharingService --> SplitwiseExpenseSharingRepository
SplitwiseExpenseSharingService --> SplitwiseExpenseSharingPolicy
SplitwiseExpenseSharingService --> SplitwiseExpenseSharing
class Group {
  +UUID id
  +validate()
}
SplitwiseExpenseSharing "1" o-- "many" Group
class Expense {
  +UUID id
  +validate()
}
SplitwiseExpenseSharing "1" o-- "many" Expense
class Split {
  +UUID id
  +validate()
}
SplitwiseExpenseSharing "1" o-- "many" Split
class DebtEdge {
  +UUID id
  +validate()
}
SplitwiseExpenseSharing "1" o-- "many" DebtEdge
class Money {
  <<value object>>
}
SplitwiseExpenseSharing ..> Money
class UserId {
  <<value object>>
}
SplitwiseExpenseSharing ..> UserId
class Ratio {
  <<value object>>
}
SplitwiseExpenseSharing ..> Ratio
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as SplitwiseExpenseSharingService
participant Repo as SplitwiseExpenseSharingRepository
participant Policy as SplitwiseExpenseSharingPolicy
participant Agg as SplitwiseExpenseSharing
participant Outbox
Client->>Service: addExpense(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: addExpense(command)
Agg-->>Service: SplitwiseExpenseSharingAddExpenseEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.splitwiseexpensesharing;

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

enum SplitwiseExpenseSharingStatus {
    OPEN,
    SIMPLIFIED,
    SETTLEMENT_PENDING,
    SETTLED,
    CANCELLED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record SplitwiseExpenseSharingAddExpenseEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record SplitwiseExpenseSharingSimplifyDebtsEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record SplitwiseExpenseSharingRecordSettlementEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record SplitwiseExpenseSharingCloseGroupEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface SplitwiseExpenseSharingCommand permits AddExpenseCommand, SimplifyDebtsCommand, RecordSettlementCommand, CloseGroupCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record AddExpenseCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SplitwiseExpenseSharingCommand {}
record SimplifyDebtsCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SplitwiseExpenseSharingCommand {}
record RecordSettlementCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SplitwiseExpenseSharingCommand {}
record CloseGroupCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SplitwiseExpenseSharingCommand {}

interface SplitwiseExpenseSharingRepository {
    Optional<SplitwiseExpenseSharing> findById(UUID id);
    void save(SplitwiseExpenseSharing aggregate, long expectedVersion);
}

interface SplitwiseExpenseSharingPolicy {
    Decision evaluate(SplitwiseExpenseSharing aggregate, SplitwiseExpenseSharingCommand command);
}

final class Group {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class SplitwiseExpenseSharing {
    private final UUID id;
    private final List<Group> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private SplitwiseExpenseSharingStatus status;
    private long version;

    SplitwiseExpenseSharing(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = SplitwiseExpenseSharingStatus.OPEN;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    SplitwiseExpenseSharingStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void addExpense(AddExpenseCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run addExpense when aggregate is terminal");
    this.status = SplitwiseExpenseSharingStatus.SIMPLIFIED;
    this.version++;
    this.domainEvents.add(new SplitwiseExpenseSharingAddExpenseEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void simplifyDebts(SimplifyDebtsCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run simplifyDebts when aggregate is terminal");
    this.status = SplitwiseExpenseSharingStatus.SETTLEMENT_PENDING;
    this.version++;
    this.domainEvents.add(new SplitwiseExpenseSharingSimplifyDebtsEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void recordSettlement(RecordSettlementCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run recordSettlement when aggregate is terminal");
    this.status = SplitwiseExpenseSharingStatus.SETTLED;
    this.version++;
    this.domainEvents.add(new SplitwiseExpenseSharingRecordSettlementEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void closeGroup(CloseGroupCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run closeGroup when aggregate is terminal");
    this.status = SplitwiseExpenseSharingStatus.CANCELLED;
    this.version++;
    this.domainEvents.add(new SplitwiseExpenseSharingCloseGroupEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == SplitwiseExpenseSharingStatus.CANCELLED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class SplitwiseExpenseSharingService {
    private final SplitwiseExpenseSharingRepository repository;
    private final SplitwiseExpenseSharingPolicy policy;
    private final Outbox outbox;

    SplitwiseExpenseSharingService(SplitwiseExpenseSharingRepository repository, SplitwiseExpenseSharingPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(SplitwiseExpenseSharingCommand command) {
        SplitwiseExpenseSharing aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("SplitwiseExpenseSharing not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof AddExpenseCommand c) aggregate.addExpense(c);
        if (command instanceof SimplifyDebtsCommand c) aggregate.simplifyDebts(c);
        if (command instanceof RecordSettlementCommand c) aggregate.recordSettlement(c);
        if (command instanceof CloseGroupCommand c) aggregate.closeGroup(c);
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

- Persist `SplitwiseExpenseSharing` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `SplitwiseExpenseSharing` invariants and each command method.
- State-machine test all valid and invalid `SplitwiseExpenseSharingStatus` transitions.
- Contract test every `SplitwiseExpenseSharingRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `SplitwiseExpenseSharing` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `SplitwiseExpenseSharingService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
