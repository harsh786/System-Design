# 031. Design Payment Processing System

Source problem: `Design payment processing system.`  
Category: `Fintech`  
Primary focus: `idempotency, provider adapter, retries, reconciliation`  
Archetype: `finance`

## 1. Interview Framing

Design `payment processing system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `payment processing system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `CREATED, AUTHORIZED, CAPTURED, FAILED, REFUNDED`.
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

- `Merchant`
- `Customer`
- `PaymentProvider`
- `RiskService`

Primary use cases:

- `createIntent` command on `PaymentProcessingSystem`
- `authorizePayment` command on `PaymentProcessingSystem`
- `capturePayment` command on `PaymentProcessingSystem`
- `reconcile` command on `PaymentProcessingSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `PaymentProcessingSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `PaymentIntent, PaymentAttempt, ProviderCharge, Refund, ReconciliationRecord` | Have identity and change over time under the aggregate. |
| Value objects | `Money, IdempotencyKey, ProviderReference, CorrelationId` | Immutable concepts compared by value. |
| Policies | `PaymentProcessingSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `PaymentProcessingSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
CREATED, AUTHORIZED, CAPTURED, FAILED, REFUNDED, RECONCILED
```

Invariants:

- `PaymentProcessingSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.
- Money and capacity changes are atomic within the transaction boundary.
- A repeated idempotency key returns the original result and never double-applies side effects.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `PaymentProcessingSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `PaymentProcessingSystem` | Composes | PaymentIntent, PaymentAttempt, ProviderCharge | Owns invariants and lifecycle transitions. |
| `PaymentProcessingSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `PaymentProcessingSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class PaymentProcessingSystem {
  +UUID id
  +PaymentProcessingSystemStatus status
  +long version
  +validateInvariants()
}
class PaymentProcessingSystemService {
  +handle(command)
}
class PaymentProcessingSystemRepository {
  <<interface>>
  +findById(UUID id) PaymentProcessingSystem
  +save(PaymentProcessingSystem aggregate, long expectedVersion)
}
class PaymentProcessingSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
PaymentProcessingSystemService --> PaymentProcessingSystemRepository
PaymentProcessingSystemService --> PaymentProcessingSystemPolicy
PaymentProcessingSystemService --> PaymentProcessingSystem
class PaymentIntent {
  +UUID id
  +validate()
}
PaymentProcessingSystem "1" o-- "many" PaymentIntent
class PaymentAttempt {
  +UUID id
  +validate()
}
PaymentProcessingSystem "1" o-- "many" PaymentAttempt
class ProviderCharge {
  +UUID id
  +validate()
}
PaymentProcessingSystem "1" o-- "many" ProviderCharge
class Refund {
  +UUID id
  +validate()
}
PaymentProcessingSystem "1" o-- "many" Refund
class Money {
  <<value object>>
}
PaymentProcessingSystem ..> Money
class IdempotencyKey {
  <<value object>>
}
PaymentProcessingSystem ..> IdempotencyKey
class ProviderReference {
  <<value object>>
}
PaymentProcessingSystem ..> ProviderReference
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as PaymentProcessingSystemService
participant Repo as PaymentProcessingSystemRepository
participant Policy as PaymentProcessingSystemPolicy
participant Agg as PaymentProcessingSystem
participant Outbox
Client->>Service: createIntent(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: createIntent(command)
Agg-->>Service: PaymentProcessingSystemCreateIntentEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |
| Factory / Builder | Create valid aggregates and command objects while keeping constructors small and invariant-safe. |
| Adapter | Hide vendor or infrastructure differences behind stable ports. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.paymentprocessingsystem;

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

enum PaymentProcessingSystemStatus {
    CREATED,
    AUTHORIZED,
    CAPTURED,
    FAILED,
    REFUNDED,
    RECONCILED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record PaymentProcessingSystemCreateIntentEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record PaymentProcessingSystemAuthorizePaymentEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record PaymentProcessingSystemCapturePaymentEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record PaymentProcessingSystemReconcileEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface PaymentProcessingSystemCommand permits CreateIntentCommand, AuthorizePaymentCommand, CapturePaymentCommand, ReconcileCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record CreateIntentCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements PaymentProcessingSystemCommand {}
record AuthorizePaymentCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements PaymentProcessingSystemCommand {}
record CapturePaymentCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements PaymentProcessingSystemCommand {}
record ReconcileCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements PaymentProcessingSystemCommand {}

interface PaymentProcessingSystemRepository {
    Optional<PaymentProcessingSystem> findById(UUID id);
    void save(PaymentProcessingSystem aggregate, long expectedVersion);
}

interface PaymentProcessingSystemPolicy {
    Decision evaluate(PaymentProcessingSystem aggregate, PaymentProcessingSystemCommand command);
}

final class PaymentIntent {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class PaymentProcessingSystem {
    private final UUID id;
    private final List<PaymentIntent> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private PaymentProcessingSystemStatus status;
    private long version;

    PaymentProcessingSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = PaymentProcessingSystemStatus.CREATED;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    PaymentProcessingSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void createIntent(CreateIntentCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run createIntent when aggregate is terminal");
    this.status = PaymentProcessingSystemStatus.AUTHORIZED;
    this.version++;
    this.domainEvents.add(new PaymentProcessingSystemCreateIntentEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void authorizePayment(AuthorizePaymentCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run authorizePayment when aggregate is terminal");
    this.status = PaymentProcessingSystemStatus.CAPTURED;
    this.version++;
    this.domainEvents.add(new PaymentProcessingSystemAuthorizePaymentEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void capturePayment(CapturePaymentCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run capturePayment when aggregate is terminal");
    this.status = PaymentProcessingSystemStatus.FAILED;
    this.version++;
    this.domainEvents.add(new PaymentProcessingSystemCapturePaymentEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void reconcile(ReconcileCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run reconcile when aggregate is terminal");
    this.status = PaymentProcessingSystemStatus.REFUNDED;
    this.version++;
    this.domainEvents.add(new PaymentProcessingSystemReconcileEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == PaymentProcessingSystemStatus.RECONCILED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class PaymentProcessingSystemService {
    private final PaymentProcessingSystemRepository repository;
    private final PaymentProcessingSystemPolicy policy;
    private final Outbox outbox;

    PaymentProcessingSystemService(PaymentProcessingSystemRepository repository, PaymentProcessingSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(PaymentProcessingSystemCommand command) {
        PaymentProcessingSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("PaymentProcessingSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof CreateIntentCommand c) aggregate.createIntent(c);
        if (command instanceof AuthorizePaymentCommand c) aggregate.authorizePayment(c);
        if (command instanceof CapturePaymentCommand c) aggregate.capturePayment(c);
        if (command instanceof ReconcileCommand c) aggregate.reconcile(c);
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

- Persist `PaymentProcessingSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Create valid aggregates and command objects while keeping constructors small and invariant-safe. | `Factory / Builder` |
| Hide vendor or infrastructure differences behind stable ports. | `Adapter` |
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `PaymentProcessingSystem` invariants and each command method.
- State-machine test all valid and invalid `PaymentProcessingSystemStatus` transitions.
- Contract test every `PaymentProcessingSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `PaymentProcessingSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `PaymentProcessingSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
