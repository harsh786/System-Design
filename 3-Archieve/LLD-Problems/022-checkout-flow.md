# 022. Design Checkout Flow

Source problem: `Design checkout flow.`  
Category: `Commerce workflow`  
Primary focus: `facade, saga, payment, inventory, order state machine`  
Archetype: `state-workflow`

## 1. Interview Framing

Design `checkout flow` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `checkout flow` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `STARTED, VALIDATED, INVENTORY_HELD, PAYMENT_AUTHORIZED, ORDER_CREATED`.
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
- `PaymentProvider`
- `InventoryService`

Primary use cases:

- `validateCart` command on `CheckoutFlow`
- `holdInventory` command on `CheckoutFlow`
- `authorizePayment` command on `CheckoutFlow`
- `createOrder` command on `CheckoutFlow`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `CheckoutFlow` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `CheckoutSession, Cart, Order, PaymentAttempt, InventoryHold` | Have identity and change over time under the aggregate. |
| Value objects | `Money, Address, IdempotencyKey, CorrelationId` | Immutable concepts compared by value. |
| Policies | `CheckoutFlowPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `CheckoutFlowRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
STARTED, VALIDATED, INVENTORY_HELD, PAYMENT_AUTHORIZED, ORDER_CREATED, FAILED
```

Invariants:

- `CheckoutFlow` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `CheckoutFlowService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `CheckoutFlow` | Composes | CheckoutSession, Cart, Order | Owns invariants and lifecycle transitions. |
| `CheckoutFlowRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `CheckoutFlowPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class CheckoutFlow {
  +UUID id
  +CheckoutFlowStatus status
  +long version
  +validateInvariants()
}
class CheckoutFlowService {
  +handle(command)
}
class CheckoutFlowRepository {
  <<interface>>
  +findById(UUID id) CheckoutFlow
  +save(CheckoutFlow aggregate, long expectedVersion)
}
class CheckoutFlowPolicy {
  <<interface>>
  +evaluate(context) Decision
}
CheckoutFlowService --> CheckoutFlowRepository
CheckoutFlowService --> CheckoutFlowPolicy
CheckoutFlowService --> CheckoutFlow
class CheckoutSession {
  +UUID id
  +validate()
}
CheckoutFlow "1" o-- "many" CheckoutSession
class Cart {
  +UUID id
  +validate()
}
CheckoutFlow "1" o-- "many" Cart
class Order {
  +UUID id
  +validate()
}
CheckoutFlow "1" o-- "many" Order
class PaymentAttempt {
  +UUID id
  +validate()
}
CheckoutFlow "1" o-- "many" PaymentAttempt
class Money {
  <<value object>>
}
CheckoutFlow ..> Money
class Address {
  <<value object>>
}
CheckoutFlow ..> Address
class IdempotencyKey {
  <<value object>>
}
CheckoutFlow ..> IdempotencyKey
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as CheckoutFlowService
participant Repo as CheckoutFlowRepository
participant Policy as CheckoutFlowPolicy
participant Agg as CheckoutFlow
participant Outbox
Client->>Service: validateCart(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: validateCart(command)
Agg-->>Service: CheckoutFlowValidateCartEvent
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
package lld.checkoutflow;

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

enum CheckoutFlowStatus {
    STARTED,
    VALIDATED,
    INVENTORY_HELD,
    PAYMENT_AUTHORIZED,
    ORDER_CREATED,
    FAILED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record CheckoutFlowValidateCartEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record CheckoutFlowHoldInventoryEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record CheckoutFlowAuthorizePaymentEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record CheckoutFlowCreateOrderEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface CheckoutFlowCommand permits ValidateCartCommand, HoldInventoryCommand, AuthorizePaymentCommand, CreateOrderCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record ValidateCartCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CheckoutFlowCommand {}
record HoldInventoryCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CheckoutFlowCommand {}
record AuthorizePaymentCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CheckoutFlowCommand {}
record CreateOrderCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CheckoutFlowCommand {}

interface CheckoutFlowRepository {
    Optional<CheckoutFlow> findById(UUID id);
    void save(CheckoutFlow aggregate, long expectedVersion);
}

interface CheckoutFlowPolicy {
    Decision evaluate(CheckoutFlow aggregate, CheckoutFlowCommand command);
}

final class CheckoutSession {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class CheckoutFlow {
    private final UUID id;
    private final List<CheckoutSession> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private CheckoutFlowStatus status;
    private long version;

    CheckoutFlow(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = CheckoutFlowStatus.STARTED;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    CheckoutFlowStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void validateCart(ValidateCartCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run validateCart when aggregate is terminal");
    this.status = CheckoutFlowStatus.VALIDATED;
    this.version++;
    this.domainEvents.add(new CheckoutFlowValidateCartEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void holdInventory(HoldInventoryCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run holdInventory when aggregate is terminal");
    this.status = CheckoutFlowStatus.INVENTORY_HELD;
    this.version++;
    this.domainEvents.add(new CheckoutFlowHoldInventoryEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void authorizePayment(AuthorizePaymentCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run authorizePayment when aggregate is terminal");
    this.status = CheckoutFlowStatus.PAYMENT_AUTHORIZED;
    this.version++;
    this.domainEvents.add(new CheckoutFlowAuthorizePaymentEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void createOrder(CreateOrderCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run createOrder when aggregate is terminal");
    this.status = CheckoutFlowStatus.ORDER_CREATED;
    this.version++;
    this.domainEvents.add(new CheckoutFlowCreateOrderEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == CheckoutFlowStatus.FAILED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class CheckoutFlowService {
    private final CheckoutFlowRepository repository;
    private final CheckoutFlowPolicy policy;
    private final Outbox outbox;

    CheckoutFlowService(CheckoutFlowRepository repository, CheckoutFlowPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(CheckoutFlowCommand command) {
        CheckoutFlow aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("CheckoutFlow not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof ValidateCartCommand c) aggregate.validateCart(c);
        if (command instanceof HoldInventoryCommand c) aggregate.holdInventory(c);
        if (command instanceof AuthorizePaymentCommand c) aggregate.authorizePayment(c);
        if (command instanceof CreateOrderCommand c) aggregate.createOrder(c);
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

- Persist `CheckoutFlow` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `CheckoutFlow` invariants and each command method.
- State-machine test all valid and invalid `CheckoutFlowStatus` transitions.
- Contract test every `CheckoutFlowRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `CheckoutFlow` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `CheckoutFlowService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
