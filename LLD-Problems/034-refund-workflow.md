# 034. Design Refund Workflow

Source problem: `Design refund workflow.`  
Category: `Fintech workflow`  
Primary focus: `process manager, state machine, compensation`  
Archetype: `finance`

## 1. Interview Framing

Design `refund workflow` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `refund workflow` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `REQUESTED, APPROVED, PROCESSING, SUCCEEDED, FAILED`.
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

- `Customer`
- `SupportAgent`
- `PaymentProvider`

Primary use cases:

- `requestRefund` command on `RefundWorkflow`
- `approveRefund` command on `RefundWorkflow`
- `executeRefund` command on `RefundWorkflow`
- `compensateFailure` command on `RefundWorkflow`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `RefundWorkflow` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `RefundRequest, PaymentCapture, CompensationStep, Approval, RefundAttempt` | Have identity and change over time under the aggregate. |
| Value objects | `Money, ReasonCode, IdempotencyKey, ProviderReference` | Immutable concepts compared by value. |
| Policies | `RefundWorkflowPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `RefundWorkflowRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
REQUESTED, APPROVED, PROCESSING, SUCCEEDED, FAILED, REJECTED
```

Invariants:

- `RefundWorkflow` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.
- Money and capacity changes are atomic within the transaction boundary.
- A repeated idempotency key returns the original result and never double-applies side effects.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `RefundWorkflowService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `RefundWorkflow` | Composes | RefundRequest, PaymentCapture, CompensationStep | Owns invariants and lifecycle transitions. |
| `RefundWorkflowRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `RefundWorkflowPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class RefundWorkflow {
  +UUID id
  +RefundWorkflowStatus status
  +long version
  +validateInvariants()
}
class RefundWorkflowService {
  +handle(command)
}
class RefundWorkflowRepository {
  <<interface>>
  +findById(UUID id) RefundWorkflow
  +save(RefundWorkflow aggregate, long expectedVersion)
}
class RefundWorkflowPolicy {
  <<interface>>
  +evaluate(context) Decision
}
RefundWorkflowService --> RefundWorkflowRepository
RefundWorkflowService --> RefundWorkflowPolicy
RefundWorkflowService --> RefundWorkflow
class RefundRequest {
  +UUID id
  +validate()
}
RefundWorkflow "1" o-- "many" RefundRequest
class PaymentCapture {
  +UUID id
  +validate()
}
RefundWorkflow "1" o-- "many" PaymentCapture
class CompensationStep {
  +UUID id
  +validate()
}
RefundWorkflow "1" o-- "many" CompensationStep
class Approval {
  +UUID id
  +validate()
}
RefundWorkflow "1" o-- "many" Approval
class Money {
  <<value object>>
}
RefundWorkflow ..> Money
class ReasonCode {
  <<value object>>
}
RefundWorkflow ..> ReasonCode
class IdempotencyKey {
  <<value object>>
}
RefundWorkflow ..> IdempotencyKey
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as RefundWorkflowService
participant Repo as RefundWorkflowRepository
participant Policy as RefundWorkflowPolicy
participant Agg as RefundWorkflow
participant Outbox
Client->>Service: requestRefund(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: requestRefund(command)
Agg-->>Service: RefundWorkflowRequestRefundEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |
| Saga / Process Manager | Coordinate multi-step workflows and compensation across payment, inventory, delivery, or approvals. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.refundworkflow;

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

enum RefundWorkflowStatus {
    REQUESTED,
    APPROVED,
    PROCESSING,
    SUCCEEDED,
    FAILED,
    REJECTED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record RefundWorkflowRequestRefundEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record RefundWorkflowApproveRefundEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record RefundWorkflowExecuteRefundEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record RefundWorkflowCompensateFailureEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface RefundWorkflowCommand permits RequestRefundCommand, ApproveRefundCommand, ExecuteRefundCommand, CompensateFailureCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record RequestRefundCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RefundWorkflowCommand {}
record ApproveRefundCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RefundWorkflowCommand {}
record ExecuteRefundCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RefundWorkflowCommand {}
record CompensateFailureCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RefundWorkflowCommand {}

interface RefundWorkflowRepository {
    Optional<RefundWorkflow> findById(UUID id);
    void save(RefundWorkflow aggregate, long expectedVersion);
}

interface RefundWorkflowPolicy {
    Decision evaluate(RefundWorkflow aggregate, RefundWorkflowCommand command);
}

final class RefundRequest {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class RefundWorkflow {
    private final UUID id;
    private final List<RefundRequest> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private RefundWorkflowStatus status;
    private long version;

    RefundWorkflow(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = RefundWorkflowStatus.REQUESTED;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    RefundWorkflowStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void requestRefund(RequestRefundCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run requestRefund when aggregate is terminal");
    this.status = RefundWorkflowStatus.APPROVED;
    this.version++;
    this.domainEvents.add(new RefundWorkflowRequestRefundEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void approveRefund(ApproveRefundCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run approveRefund when aggregate is terminal");
    this.status = RefundWorkflowStatus.PROCESSING;
    this.version++;
    this.domainEvents.add(new RefundWorkflowApproveRefundEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void executeRefund(ExecuteRefundCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run executeRefund when aggregate is terminal");
    this.status = RefundWorkflowStatus.SUCCEEDED;
    this.version++;
    this.domainEvents.add(new RefundWorkflowExecuteRefundEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void compensateFailure(CompensateFailureCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run compensateFailure when aggregate is terminal");
    this.status = RefundWorkflowStatus.FAILED;
    this.version++;
    this.domainEvents.add(new RefundWorkflowCompensateFailureEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == RefundWorkflowStatus.REJECTED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class RefundWorkflowService {
    private final RefundWorkflowRepository repository;
    private final RefundWorkflowPolicy policy;
    private final Outbox outbox;

    RefundWorkflowService(RefundWorkflowRepository repository, RefundWorkflowPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(RefundWorkflowCommand command) {
        RefundWorkflow aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("RefundWorkflow not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof RequestRefundCommand c) aggregate.requestRefund(c);
        if (command instanceof ApproveRefundCommand c) aggregate.approveRefund(c);
        if (command instanceof ExecuteRefundCommand c) aggregate.executeRefund(c);
        if (command instanceof CompensateFailureCommand c) aggregate.compensateFailure(c);
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

- Persist `RefundWorkflow` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Coordinate multi-step workflows and compensation across payment, inventory, delivery, or approvals. | `Saga / Process Manager` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `RefundWorkflow` invariants and each command method.
- State-machine test all valid and invalid `RefundWorkflowStatus` transitions.
- Contract test every `RefundWorkflowRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `RefundWorkflow` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `RefundWorkflowService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
