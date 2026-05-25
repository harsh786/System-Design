# 003. Design A Vending Machine

Source problem: `Design a vending machine.`  
Category: `State machine`  
Primary focus: `State, inventory, payment, refunds, error states`  
Archetype: `state-workflow`

## 1. Interview Framing

Design `vending machine` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `vending machine` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `IDLE, PRODUCT_SELECTED, ACCEPTING_PAYMENT, PAID, DISPENSING`.
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
- `Operator`
- `PaymentProvider`

Primary use cases:

- `selectProduct` command on `VendingMachine`
- `acceptPayment` command on `VendingMachine`
- `dispenseProduct` command on `VendingMachine`
- `refund` command on `VendingMachine`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `VendingMachine` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Slot, Product, InventoryBin, PaymentSession, DispenseTray` | Have identity and change over time under the aggregate. |
| Value objects | `Money, ProductCode, Quantity, Refund` | Immutable concepts compared by value. |
| Policies | `VendingMachinePolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `VendingMachineRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
IDLE, PRODUCT_SELECTED, ACCEPTING_PAYMENT, PAID, DISPENSING, OUT_OF_SERVICE
```

Invariants:

- `VendingMachine` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `VendingMachineService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `VendingMachine` | Composes | Slot, Product, InventoryBin | Owns invariants and lifecycle transitions. |
| `VendingMachineRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `VendingMachinePolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class VendingMachine {
  +UUID id
  +VendingMachineStatus status
  +long version
  +validateInvariants()
}
class VendingMachineService {
  +handle(command)
}
class VendingMachineRepository {
  <<interface>>
  +findById(UUID id) VendingMachine
  +save(VendingMachine aggregate, long expectedVersion)
}
class VendingMachinePolicy {
  <<interface>>
  +evaluate(context) Decision
}
VendingMachineService --> VendingMachineRepository
VendingMachineService --> VendingMachinePolicy
VendingMachineService --> VendingMachine
class Slot {
  +UUID id
  +validate()
}
VendingMachine "1" o-- "many" Slot
class Product {
  +UUID id
  +validate()
}
VendingMachine "1" o-- "many" Product
class InventoryBin {
  +UUID id
  +validate()
}
VendingMachine "1" o-- "many" InventoryBin
class PaymentSession {
  +UUID id
  +validate()
}
VendingMachine "1" o-- "many" PaymentSession
class Money {
  <<value object>>
}
VendingMachine ..> Money
class ProductCode {
  <<value object>>
}
VendingMachine ..> ProductCode
class Quantity {
  <<value object>>
}
VendingMachine ..> Quantity
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as VendingMachineService
participant Repo as VendingMachineRepository
participant Policy as VendingMachinePolicy
participant Agg as VendingMachine
participant Outbox
Client->>Service: selectProduct(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: selectProduct(command)
Agg-->>Service: VendingMachineSelectProductEvent
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
package lld.vendingmachine;

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

enum VendingMachineStatus {
    IDLE,
    PRODUCT_SELECTED,
    ACCEPTING_PAYMENT,
    PAID,
    DISPENSING,
    OUT_OF_SERVICE
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record VendingMachineSelectProductEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record VendingMachineAcceptPaymentEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record VendingMachineDispenseProductEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record VendingMachineRefundEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface VendingMachineCommand permits SelectProductCommand, AcceptPaymentCommand, DispenseProductCommand, RefundCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record SelectProductCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements VendingMachineCommand {}
record AcceptPaymentCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements VendingMachineCommand {}
record DispenseProductCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements VendingMachineCommand {}
record RefundCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements VendingMachineCommand {}

interface VendingMachineRepository {
    Optional<VendingMachine> findById(UUID id);
    void save(VendingMachine aggregate, long expectedVersion);
}

interface VendingMachinePolicy {
    Decision evaluate(VendingMachine aggregate, VendingMachineCommand command);
}

final class Slot {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class VendingMachine {
    private final UUID id;
    private final List<Slot> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private VendingMachineStatus status;
    private long version;

    VendingMachine(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = VendingMachineStatus.IDLE;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    VendingMachineStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void selectProduct(SelectProductCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run selectProduct when aggregate is terminal");
    this.status = VendingMachineStatus.PRODUCT_SELECTED;
    this.version++;
    this.domainEvents.add(new VendingMachineSelectProductEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void acceptPayment(AcceptPaymentCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run acceptPayment when aggregate is terminal");
    this.status = VendingMachineStatus.ACCEPTING_PAYMENT;
    this.version++;
    this.domainEvents.add(new VendingMachineAcceptPaymentEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void dispenseProduct(DispenseProductCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run dispenseProduct when aggregate is terminal");
    this.status = VendingMachineStatus.PAID;
    this.version++;
    this.domainEvents.add(new VendingMachineDispenseProductEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void refund(RefundCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run refund when aggregate is terminal");
    this.status = VendingMachineStatus.DISPENSING;
    this.version++;
    this.domainEvents.add(new VendingMachineRefundEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == VendingMachineStatus.OUT_OF_SERVICE;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class VendingMachineService {
    private final VendingMachineRepository repository;
    private final VendingMachinePolicy policy;
    private final Outbox outbox;

    VendingMachineService(VendingMachineRepository repository, VendingMachinePolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(VendingMachineCommand command) {
        VendingMachine aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("VendingMachine not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof SelectProductCommand c) aggregate.selectProduct(c);
        if (command instanceof AcceptPaymentCommand c) aggregate.acceptPayment(c);
        if (command instanceof DispenseProductCommand c) aggregate.dispenseProduct(c);
        if (command instanceof RefundCommand c) aggregate.refund(c);
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

- Persist `VendingMachine` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `VendingMachine` invariants and each command method.
- State-machine test all valid and invalid `VendingMachineStatus` transitions.
- Contract test every `VendingMachineRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `VendingMachine` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `VendingMachineService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
