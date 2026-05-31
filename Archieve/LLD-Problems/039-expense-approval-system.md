# 039. Design Expense Approval System

Source problem: `Design expense approval system.`  
Category: `Enterprise finance`  
Primary focus: `policy engine, workflow, delegation, audit`  
Archetype: `finance`

## 1. Interview Framing

Design `expense approval system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `expense approval system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `DRAFT, SUBMITTED, MANAGER_APPROVED, FINANCE_APPROVED, REJECTED`.
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

- `Employee`
- `Manager`
- `FinanceApprover`

Primary use cases:

- `submitReport` command on `ExpenseApprovalSystem`
- `approveStep` command on `ExpenseApprovalSystem`
- `delegateApproval` command on `ExpenseApprovalSystem`
- `reimburse` command on `ExpenseApprovalSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `ExpenseApprovalSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `ExpenseReport, ExpenseLine, ApprovalStep, Delegation, AuditTrail` | Have identity and change over time under the aggregate. |
| Value objects | `Money, PolicyCode, ReceiptId, UserId` | Immutable concepts compared by value. |
| Policies | `ExpenseApprovalSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `ExpenseApprovalSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
DRAFT, SUBMITTED, MANAGER_APPROVED, FINANCE_APPROVED, REJECTED, PAID
```

Invariants:

- `ExpenseApprovalSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.
- Money and capacity changes are atomic within the transaction boundary.
- A repeated idempotency key returns the original result and never double-applies side effects.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `ExpenseApprovalSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `ExpenseApprovalSystem` | Composes | ExpenseReport, ExpenseLine, ApprovalStep | Owns invariants and lifecycle transitions. |
| `ExpenseApprovalSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `ExpenseApprovalSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class ExpenseApprovalSystem {
  +UUID id
  +ExpenseApprovalSystemStatus status
  +long version
  +validateInvariants()
}
class ExpenseApprovalSystemService {
  +handle(command)
}
class ExpenseApprovalSystemRepository {
  <<interface>>
  +findById(UUID id) ExpenseApprovalSystem
  +save(ExpenseApprovalSystem aggregate, long expectedVersion)
}
class ExpenseApprovalSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
ExpenseApprovalSystemService --> ExpenseApprovalSystemRepository
ExpenseApprovalSystemService --> ExpenseApprovalSystemPolicy
ExpenseApprovalSystemService --> ExpenseApprovalSystem
class ExpenseReport {
  +UUID id
  +validate()
}
ExpenseApprovalSystem "1" o-- "many" ExpenseReport
class ExpenseLine {
  +UUID id
  +validate()
}
ExpenseApprovalSystem "1" o-- "many" ExpenseLine
class ApprovalStep {
  +UUID id
  +validate()
}
ExpenseApprovalSystem "1" o-- "many" ApprovalStep
class Delegation {
  +UUID id
  +validate()
}
ExpenseApprovalSystem "1" o-- "many" Delegation
class Money {
  <<value object>>
}
ExpenseApprovalSystem ..> Money
class PolicyCode {
  <<value object>>
}
ExpenseApprovalSystem ..> PolicyCode
class ReceiptId {
  <<value object>>
}
ExpenseApprovalSystem ..> ReceiptId
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as ExpenseApprovalSystemService
participant Repo as ExpenseApprovalSystemRepository
participant Policy as ExpenseApprovalSystemPolicy
participant Agg as ExpenseApprovalSystem
participant Outbox
Client->>Service: submitReport(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: submitReport(command)
Agg-->>Service: ExpenseApprovalSystemSubmitReportEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |
| Strategy | Swap algorithms such as pricing, ranking, scheduling, matching, or retry without changing the aggregate. |
| Command | Represent user or system intent as retryable, auditable, and optionally undoable objects. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |
| Saga / Process Manager | Coordinate multi-step workflows and compensation across payment, inventory, delivery, or approvals. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.expenseapprovalsystem;

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

enum ExpenseApprovalSystemStatus {
    DRAFT,
    SUBMITTED,
    MANAGER_APPROVED,
    FINANCE_APPROVED,
    REJECTED,
    PAID
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record ExpenseApprovalSystemSubmitReportEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ExpenseApprovalSystemApproveStepEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ExpenseApprovalSystemDelegateApprovalEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ExpenseApprovalSystemReimburseEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface ExpenseApprovalSystemCommand permits SubmitReportCommand, ApproveStepCommand, DelegateApprovalCommand, ReimburseCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record SubmitReportCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ExpenseApprovalSystemCommand {}
record ApproveStepCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ExpenseApprovalSystemCommand {}
record DelegateApprovalCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ExpenseApprovalSystemCommand {}
record ReimburseCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ExpenseApprovalSystemCommand {}

interface ExpenseApprovalSystemRepository {
    Optional<ExpenseApprovalSystem> findById(UUID id);
    void save(ExpenseApprovalSystem aggregate, long expectedVersion);
}

interface ExpenseApprovalSystemPolicy {
    Decision evaluate(ExpenseApprovalSystem aggregate, ExpenseApprovalSystemCommand command);
}

final class ExpenseReport {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class ExpenseApprovalSystem {
    private final UUID id;
    private final List<ExpenseReport> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private ExpenseApprovalSystemStatus status;
    private long version;

    ExpenseApprovalSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = ExpenseApprovalSystemStatus.DRAFT;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    ExpenseApprovalSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void submitReport(SubmitReportCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run submitReport when aggregate is terminal");
    this.status = ExpenseApprovalSystemStatus.SUBMITTED;
    this.version++;
    this.domainEvents.add(new ExpenseApprovalSystemSubmitReportEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void approveStep(ApproveStepCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run approveStep when aggregate is terminal");
    this.status = ExpenseApprovalSystemStatus.MANAGER_APPROVED;
    this.version++;
    this.domainEvents.add(new ExpenseApprovalSystemApproveStepEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void delegateApproval(DelegateApprovalCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run delegateApproval when aggregate is terminal");
    this.status = ExpenseApprovalSystemStatus.FINANCE_APPROVED;
    this.version++;
    this.domainEvents.add(new ExpenseApprovalSystemDelegateApprovalEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void reimburse(ReimburseCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run reimburse when aggregate is terminal");
    this.status = ExpenseApprovalSystemStatus.REJECTED;
    this.version++;
    this.domainEvents.add(new ExpenseApprovalSystemReimburseEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == ExpenseApprovalSystemStatus.PAID;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class ExpenseApprovalSystemService {
    private final ExpenseApprovalSystemRepository repository;
    private final ExpenseApprovalSystemPolicy policy;
    private final Outbox outbox;

    ExpenseApprovalSystemService(ExpenseApprovalSystemRepository repository, ExpenseApprovalSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(ExpenseApprovalSystemCommand command) {
        ExpenseApprovalSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("ExpenseApprovalSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof SubmitReportCommand c) aggregate.submitReport(c);
        if (command instanceof ApproveStepCommand c) aggregate.approveStep(c);
        if (command instanceof DelegateApprovalCommand c) aggregate.delegateApproval(c);
        if (command instanceof ReimburseCommand c) aggregate.reimburse(c);
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

- Persist `ExpenseApprovalSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Swap algorithms such as pricing, ranking, scheduling, matching, or retry without changing the aggregate. | `Strategy` |
| Represent user or system intent as retryable, auditable, and optionally undoable objects. | `Command` |
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| Coordinate multi-step workflows and compensation across payment, inventory, delivery, or approvals. | `Saga / Process Manager` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `ExpenseApprovalSystem` invariants and each command method.
- State-machine test all valid and invalid `ExpenseApprovalSystemStatus` transitions.
- Contract test every `ExpenseApprovalSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `ExpenseApprovalSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `ExpenseApprovalSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
