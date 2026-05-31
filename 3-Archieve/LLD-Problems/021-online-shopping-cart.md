# 021. Design An Online Shopping Cart

Source problem: `Design an online shopping cart.`  
Category: `Commerce`  
Primary focus: `cart aggregate, pricing, coupon strategy, inventory checks`  
Archetype: `domain`

## 1. Interview Framing

Design `online shopping cart` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `online shopping cart` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `ACTIVE, PRICE_STALE, INVENTORY_RESERVED, CHECKED_OUT, ABANDONED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `Customer`
- `InventoryService`
- `PricingService`

Primary use cases:

- `addItem` command on `OnlineShoppingCart`
- `applyCoupon` command on `OnlineShoppingCart`
- `reserveInventory` command on `OnlineShoppingCart`
- `checkout` command on `OnlineShoppingCart`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `OnlineShoppingCart` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Cart, CartLine, Product, InventoryReservation, Coupon` | Have identity and change over time under the aggregate. |
| Value objects | `Money, Quantity, SKU, CustomerId` | Immutable concepts compared by value. |
| Policies | `OnlineShoppingCartPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `OnlineShoppingCartRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
ACTIVE, PRICE_STALE, INVENTORY_RESERVED, CHECKED_OUT, ABANDONED
```

Invariants:

- `OnlineShoppingCart` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `OnlineShoppingCartService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `OnlineShoppingCart` | Composes | Cart, CartLine, Product | Owns invariants and lifecycle transitions. |
| `OnlineShoppingCartRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `OnlineShoppingCartPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class OnlineShoppingCart {
  +UUID id
  +OnlineShoppingCartStatus status
  +long version
  +validateInvariants()
}
class OnlineShoppingCartService {
  +handle(command)
}
class OnlineShoppingCartRepository {
  <<interface>>
  +findById(UUID id) OnlineShoppingCart
  +save(OnlineShoppingCart aggregate, long expectedVersion)
}
class OnlineShoppingCartPolicy {
  <<interface>>
  +evaluate(context) Decision
}
OnlineShoppingCartService --> OnlineShoppingCartRepository
OnlineShoppingCartService --> OnlineShoppingCartPolicy
OnlineShoppingCartService --> OnlineShoppingCart
class Cart {
  +UUID id
  +validate()
}
OnlineShoppingCart "1" o-- "many" Cart
class CartLine {
  +UUID id
  +validate()
}
OnlineShoppingCart "1" o-- "many" CartLine
class Product {
  +UUID id
  +validate()
}
OnlineShoppingCart "1" o-- "many" Product
class InventoryReservation {
  +UUID id
  +validate()
}
OnlineShoppingCart "1" o-- "many" InventoryReservation
class Money {
  <<value object>>
}
OnlineShoppingCart ..> Money
class Quantity {
  <<value object>>
}
OnlineShoppingCart ..> Quantity
class SKU {
  <<value object>>
}
OnlineShoppingCart ..> SKU
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as OnlineShoppingCartService
participant Repo as OnlineShoppingCartRepository
participant Policy as OnlineShoppingCartPolicy
participant Agg as OnlineShoppingCart
participant Outbox
Client->>Service: addItem(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: addItem(command)
Agg-->>Service: OnlineShoppingCartAddItemEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| Strategy | Swap algorithms such as pricing, ranking, scheduling, matching, or retry without changing the aggregate. |
| Specification | Compose business predicates and keep rule evaluation explainable. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.onlineshoppingcart;

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

enum OnlineShoppingCartStatus {
    ACTIVE,
    PRICE_STALE,
    INVENTORY_RESERVED,
    CHECKED_OUT,
    ABANDONED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record OnlineShoppingCartAddItemEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record OnlineShoppingCartApplyCouponEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record OnlineShoppingCartReserveInventoryEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record OnlineShoppingCartCheckoutEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface OnlineShoppingCartCommand permits AddItemCommand, ApplyCouponCommand, ReserveInventoryCommand, CheckoutCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record AddItemCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements OnlineShoppingCartCommand {}
record ApplyCouponCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements OnlineShoppingCartCommand {}
record ReserveInventoryCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements OnlineShoppingCartCommand {}
record CheckoutCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements OnlineShoppingCartCommand {}

interface OnlineShoppingCartRepository {
    Optional<OnlineShoppingCart> findById(UUID id);
    void save(OnlineShoppingCart aggregate, long expectedVersion);
}

interface OnlineShoppingCartPolicy {
    Decision evaluate(OnlineShoppingCart aggregate, OnlineShoppingCartCommand command);
}

final class Cart {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class OnlineShoppingCart {
    private final UUID id;
    private final List<Cart> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private OnlineShoppingCartStatus status;
    private long version;

    OnlineShoppingCart(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = OnlineShoppingCartStatus.ACTIVE;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    OnlineShoppingCartStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void addItem(AddItemCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run addItem when aggregate is terminal");
    this.status = OnlineShoppingCartStatus.PRICE_STALE;
    this.version++;
    this.domainEvents.add(new OnlineShoppingCartAddItemEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void applyCoupon(ApplyCouponCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run applyCoupon when aggregate is terminal");
    this.status = OnlineShoppingCartStatus.INVENTORY_RESERVED;
    this.version++;
    this.domainEvents.add(new OnlineShoppingCartApplyCouponEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void reserveInventory(ReserveInventoryCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run reserveInventory when aggregate is terminal");
    this.status = OnlineShoppingCartStatus.CHECKED_OUT;
    this.version++;
    this.domainEvents.add(new OnlineShoppingCartReserveInventoryEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void checkout(CheckoutCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run checkout when aggregate is terminal");
    this.status = OnlineShoppingCartStatus.ABANDONED;
    this.version++;
    this.domainEvents.add(new OnlineShoppingCartCheckoutEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == OnlineShoppingCartStatus.ABANDONED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class OnlineShoppingCartService {
    private final OnlineShoppingCartRepository repository;
    private final OnlineShoppingCartPolicy policy;
    private final Outbox outbox;

    OnlineShoppingCartService(OnlineShoppingCartRepository repository, OnlineShoppingCartPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(OnlineShoppingCartCommand command) {
        OnlineShoppingCart aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("OnlineShoppingCart not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof AddItemCommand c) aggregate.addItem(c);
        if (command instanceof ApplyCouponCommand c) aggregate.applyCoupon(c);
        if (command instanceof ReserveInventoryCommand c) aggregate.reserveInventory(c);
        if (command instanceof CheckoutCommand c) aggregate.checkout(c);
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

- Persist `OnlineShoppingCart` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Swap algorithms such as pricing, ranking, scheduling, matching, or retry without changing the aggregate. | `Strategy` |
| Compose business predicates and keep rule evaluation explainable. | `Specification` |
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `OnlineShoppingCart` invariants and each command method.
- State-machine test all valid and invalid `OnlineShoppingCartStatus` transitions.
- Contract test every `OnlineShoppingCartRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `OnlineShoppingCart` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `OnlineShoppingCartService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
