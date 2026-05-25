# 036. Design Invoice And Billing System

Source problem: `Design invoice and billing system.`  
Category: `SaaS billing`  
Primary focus: `invoice state, proration, retries, dunning policy`  
Archetype: `finance`

## 1. Interview Framing

Design `invoice and billing system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `invoice and billing system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `DRAFT, ISSUED, PAID, OVERDUE, VOID`.
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
- `BillingAdmin`
- `PaymentProvider`

Primary use cases:

- `generateInvoice` command on `InvoiceBillingSystem`
- `applyPayment` command on `InvoiceBillingSystem`
- `markOverdue` command on `InvoiceBillingSystem`
- `voidInvoice` command on `InvoiceBillingSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `InvoiceBillingSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Invoice, InvoiceLine, Charge, PaymentAttempt, DunningSchedule` | Have identity and change over time under the aggregate. |
| Value objects | `Money, BillingPeriod, TaxRate, InvoiceNumber` | Immutable concepts compared by value. |
| Policies | `InvoiceBillingSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `InvoiceBillingSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
DRAFT, ISSUED, PAID, OVERDUE, VOID, UNCOLLECTIBLE
```

Invariants:

- `InvoiceBillingSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.
- Money and capacity changes are atomic within the transaction boundary.
- A repeated idempotency key returns the original result and never double-applies side effects.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `InvoiceBillingSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `InvoiceBillingSystem` | Composes | Invoice, InvoiceLine, Charge | Owns invariants and lifecycle transitions. |
| `InvoiceBillingSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `InvoiceBillingSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class InvoiceBillingSystem {
  +UUID id
  +InvoiceBillingSystemStatus status
  +long version
  +validateInvariants()
}
class InvoiceBillingSystemService {
  +handle(command)
}
class InvoiceBillingSystemRepository {
  <<interface>>
  +findById(UUID id) InvoiceBillingSystem
  +save(InvoiceBillingSystem aggregate, long expectedVersion)
}
class InvoiceBillingSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
InvoiceBillingSystemService --> InvoiceBillingSystemRepository
InvoiceBillingSystemService --> InvoiceBillingSystemPolicy
InvoiceBillingSystemService --> InvoiceBillingSystem
class Invoice {
  +UUID id
  +validate()
}
InvoiceBillingSystem "1" o-- "many" Invoice
class InvoiceLine {
  +UUID id
  +validate()
}
InvoiceBillingSystem "1" o-- "many" InvoiceLine
class Charge {
  +UUID id
  +validate()
}
InvoiceBillingSystem "1" o-- "many" Charge
class PaymentAttempt {
  +UUID id
  +validate()
}
InvoiceBillingSystem "1" o-- "many" PaymentAttempt
class Money {
  <<value object>>
}
InvoiceBillingSystem ..> Money
class BillingPeriod {
  <<value object>>
}
InvoiceBillingSystem ..> BillingPeriod
class TaxRate {
  <<value object>>
}
InvoiceBillingSystem ..> TaxRate
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as InvoiceBillingSystemService
participant Repo as InvoiceBillingSystemRepository
participant Policy as InvoiceBillingSystemPolicy
participant Agg as InvoiceBillingSystem
participant Outbox
Client->>Service: generateInvoice(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: generateInvoice(command)
Agg-->>Service: InvoiceBillingSystemGenerateInvoiceEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |
| Strategy | Swap algorithms such as pricing, ranking, scheduling, matching, or retry without changing the aggregate. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.invoiceandbillingsystem;

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

enum InvoiceBillingSystemStatus {
    DRAFT,
    ISSUED,
    PAID,
    OVERDUE,
    VOID,
    UNCOLLECTIBLE
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record InvoiceBillingSystemGenerateInvoiceEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record InvoiceBillingSystemApplyPaymentEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record InvoiceBillingSystemMarkOverdueEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record InvoiceBillingSystemVoidInvoiceEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface InvoiceBillingSystemCommand permits GenerateInvoiceCommand, ApplyPaymentCommand, MarkOverdueCommand, VoidInvoiceCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record GenerateInvoiceCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements InvoiceBillingSystemCommand {}
record ApplyPaymentCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements InvoiceBillingSystemCommand {}
record MarkOverdueCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements InvoiceBillingSystemCommand {}
record VoidInvoiceCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements InvoiceBillingSystemCommand {}

interface InvoiceBillingSystemRepository {
    Optional<InvoiceBillingSystem> findById(UUID id);
    void save(InvoiceBillingSystem aggregate, long expectedVersion);
}

interface InvoiceBillingSystemPolicy {
    Decision evaluate(InvoiceBillingSystem aggregate, InvoiceBillingSystemCommand command);
}

final class Invoice {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class InvoiceBillingSystem {
    private final UUID id;
    private final List<Invoice> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private InvoiceBillingSystemStatus status;
    private long version;

    InvoiceBillingSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = InvoiceBillingSystemStatus.DRAFT;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    InvoiceBillingSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void generateInvoice(GenerateInvoiceCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run generateInvoice when aggregate is terminal");
    this.status = InvoiceBillingSystemStatus.ISSUED;
    this.version++;
    this.domainEvents.add(new InvoiceBillingSystemGenerateInvoiceEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void applyPayment(ApplyPaymentCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run applyPayment when aggregate is terminal");
    this.status = InvoiceBillingSystemStatus.PAID;
    this.version++;
    this.domainEvents.add(new InvoiceBillingSystemApplyPaymentEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void markOverdue(MarkOverdueCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run markOverdue when aggregate is terminal");
    this.status = InvoiceBillingSystemStatus.OVERDUE;
    this.version++;
    this.domainEvents.add(new InvoiceBillingSystemMarkOverdueEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void voidInvoice(VoidInvoiceCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run voidInvoice when aggregate is terminal");
    this.status = InvoiceBillingSystemStatus.VOID;
    this.version++;
    this.domainEvents.add(new InvoiceBillingSystemVoidInvoiceEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == InvoiceBillingSystemStatus.UNCOLLECTIBLE;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class InvoiceBillingSystemService {
    private final InvoiceBillingSystemRepository repository;
    private final InvoiceBillingSystemPolicy policy;
    private final Outbox outbox;

    InvoiceBillingSystemService(InvoiceBillingSystemRepository repository, InvoiceBillingSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(InvoiceBillingSystemCommand command) {
        InvoiceBillingSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("InvoiceBillingSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof GenerateInvoiceCommand c) aggregate.generateInvoice(c);
        if (command instanceof ApplyPaymentCommand c) aggregate.applyPayment(c);
        if (command instanceof MarkOverdueCommand c) aggregate.markOverdue(c);
        if (command instanceof VoidInvoiceCommand c) aggregate.voidInvoice(c);
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

- Persist `InvoiceBillingSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `InvoiceBillingSystem` invariants and each command method.
- State-machine test all valid and invalid `InvoiceBillingSystemStatus` transitions.
- Contract test every `InvoiceBillingSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `InvoiceBillingSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `InvoiceBillingSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
