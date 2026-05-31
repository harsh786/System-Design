# 098. Design Approval Workflow System

Source problem: `Design approval workflow system.`  
Category: `Enterprise workflow`  
Primary focus: `stages, delegates, escalation, audit`  
Archetype: `domain`

## 1. Interview Framing

Design `approval workflow system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `approval workflow system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `DRAFT, SUBMITTED, WAITING_APPROVAL, APPROVED, REJECTED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `Requester`
- `Approver`
- `WorkflowAdmin`

Primary use cases:

- `submitRequest` command on `ApprovalWorkflowSystem`
- `approveStage` command on `ApprovalWorkflowSystem`
- `delegateStage` command on `ApprovalWorkflowSystem`
- `escalate` command on `ApprovalWorkflowSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `ApprovalWorkflowSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `ApprovalRequest, ApprovalStage, Delegate, Escalation, AuditTrail` | Have identity and change over time under the aggregate. |
| Value objects | `RequestId, UserId, Deadline, Decision` | Immutable concepts compared by value. |
| Policies | `ApprovalWorkflowSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `ApprovalWorkflowSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
DRAFT, SUBMITTED, WAITING_APPROVAL, APPROVED, REJECTED, ESCALATED
```

Invariants:

- `ApprovalWorkflowSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `ApprovalWorkflowSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `ApprovalWorkflowSystem` | Composes | ApprovalRequest, ApprovalStage, Delegate | Owns invariants and lifecycle transitions. |
| `ApprovalWorkflowSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `ApprovalWorkflowSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class ApprovalWorkflowSystem {
  +UUID id
  +ApprovalWorkflowSystemStatus status
  +long version
  +validateInvariants()
}
class ApprovalWorkflowSystemService {
  +handle(command)
}
class ApprovalWorkflowSystemRepository {
  <<interface>>
  +findById(UUID id) ApprovalWorkflowSystem
  +save(ApprovalWorkflowSystem aggregate, long expectedVersion)
}
class ApprovalWorkflowSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
ApprovalWorkflowSystemService --> ApprovalWorkflowSystemRepository
ApprovalWorkflowSystemService --> ApprovalWorkflowSystemPolicy
ApprovalWorkflowSystemService --> ApprovalWorkflowSystem
class ApprovalRequest {
  +UUID id
  +validate()
}
ApprovalWorkflowSystem "1" o-- "many" ApprovalRequest
class ApprovalStage {
  +UUID id
  +validate()
}
ApprovalWorkflowSystem "1" o-- "many" ApprovalStage
class Delegate {
  +UUID id
  +validate()
}
ApprovalWorkflowSystem "1" o-- "many" Delegate
class Escalation {
  +UUID id
  +validate()
}
ApprovalWorkflowSystem "1" o-- "many" Escalation
class RequestId {
  <<value object>>
}
ApprovalWorkflowSystem ..> RequestId
class UserId {
  <<value object>>
}
ApprovalWorkflowSystem ..> UserId
class Deadline {
  <<value object>>
}
ApprovalWorkflowSystem ..> Deadline
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as ApprovalWorkflowSystemService
participant Repo as ApprovalWorkflowSystemRepository
participant Policy as ApprovalWorkflowSystemPolicy
participant Agg as ApprovalWorkflowSystem
participant Outbox
Client->>Service: submitRequest(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: submitRequest(command)
Agg-->>Service: ApprovalWorkflowSystemSubmitRequestEvent
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
package lld.approvalworkflowsystem;

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

enum ApprovalWorkflowSystemStatus {
    DRAFT,
    SUBMITTED,
    WAITING_APPROVAL,
    APPROVED,
    REJECTED,
    ESCALATED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record ApprovalWorkflowSystemSubmitRequestEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ApprovalWorkflowSystemApproveStageEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ApprovalWorkflowSystemDelegateStageEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ApprovalWorkflowSystemEscalateEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface ApprovalWorkflowSystemCommand permits SubmitRequestCommand, ApproveStageCommand, DelegateStageCommand, EscalateCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record SubmitRequestCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ApprovalWorkflowSystemCommand {}
record ApproveStageCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ApprovalWorkflowSystemCommand {}
record DelegateStageCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ApprovalWorkflowSystemCommand {}
record EscalateCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ApprovalWorkflowSystemCommand {}

interface ApprovalWorkflowSystemRepository {
    Optional<ApprovalWorkflowSystem> findById(UUID id);
    void save(ApprovalWorkflowSystem aggregate, long expectedVersion);
}

interface ApprovalWorkflowSystemPolicy {
    Decision evaluate(ApprovalWorkflowSystem aggregate, ApprovalWorkflowSystemCommand command);
}

final class ApprovalRequest {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class ApprovalWorkflowSystem {
    private final UUID id;
    private final List<ApprovalRequest> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private ApprovalWorkflowSystemStatus status;
    private long version;

    ApprovalWorkflowSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = ApprovalWorkflowSystemStatus.DRAFT;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    ApprovalWorkflowSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void submitRequest(SubmitRequestCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run submitRequest when aggregate is terminal");
    this.status = ApprovalWorkflowSystemStatus.SUBMITTED;
    this.version++;
    this.domainEvents.add(new ApprovalWorkflowSystemSubmitRequestEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void approveStage(ApproveStageCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run approveStage when aggregate is terminal");
    this.status = ApprovalWorkflowSystemStatus.WAITING_APPROVAL;
    this.version++;
    this.domainEvents.add(new ApprovalWorkflowSystemApproveStageEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void delegateStage(DelegateStageCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run delegateStage when aggregate is terminal");
    this.status = ApprovalWorkflowSystemStatus.APPROVED;
    this.version++;
    this.domainEvents.add(new ApprovalWorkflowSystemDelegateStageEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void escalate(EscalateCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run escalate when aggregate is terminal");
    this.status = ApprovalWorkflowSystemStatus.REJECTED;
    this.version++;
    this.domainEvents.add(new ApprovalWorkflowSystemEscalateEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == ApprovalWorkflowSystemStatus.ESCALATED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class ApprovalWorkflowSystemService {
    private final ApprovalWorkflowSystemRepository repository;
    private final ApprovalWorkflowSystemPolicy policy;
    private final Outbox outbox;

    ApprovalWorkflowSystemService(ApprovalWorkflowSystemRepository repository, ApprovalWorkflowSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(ApprovalWorkflowSystemCommand command) {
        ApprovalWorkflowSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("ApprovalWorkflowSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof SubmitRequestCommand c) aggregate.submitRequest(c);
        if (command instanceof ApproveStageCommand c) aggregate.approveStage(c);
        if (command instanceof DelegateStageCommand c) aggregate.delegateStage(c);
        if (command instanceof EscalateCommand c) aggregate.escalate(c);
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

- Persist `ApprovalWorkflowSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `ApprovalWorkflowSystem` invariants and each command method.
- State-machine test all valid and invalid `ApprovalWorkflowSystemStatus` transitions.
- Contract test every `ApprovalWorkflowSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `ApprovalWorkflowSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `ApprovalWorkflowSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
