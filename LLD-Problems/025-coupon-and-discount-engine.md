# 025. Design Coupon And Discount Engine

Source problem: `Design coupon and discount engine.`  
Category: `Rules/pricing`  
Primary focus: `Strategy, Specification, policy composition, priority`  
Archetype: `rules`

## 1. Interview Framing

Design `coupon and discount engine` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `coupon and discount engine` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `DRAFT, ACTIVE, APPLIED, EXPIRED, DISABLED`.
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
- `Merchant`
- `PricingService`

Primary use cases:

- `validateCoupon` command on `CouponDiscountEngine`
- `calculateDiscount` command on `CouponDiscountEngine`
- `composeAdjustments` command on `CouponDiscountEngine`
- `recordRedemption` command on `CouponDiscountEngine`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `CouponDiscountEngine` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Coupon, DiscountRule, CartContext, Promotion, PriceAdjustment` | Have identity and change over time under the aggregate. |
| Value objects | `Money, Percentage, CouponCode, Priority` | Immutable concepts compared by value. |
| Policies | `CouponDiscountEnginePolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `CouponDiscountEngineRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
DRAFT, ACTIVE, APPLIED, EXPIRED, DISABLED
```

Invariants:

- `CouponDiscountEngine` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `CouponDiscountEngineService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `CouponDiscountEngine` | Composes | Coupon, DiscountRule, CartContext | Owns invariants and lifecycle transitions. |
| `CouponDiscountEngineRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `CouponDiscountEnginePolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class CouponDiscountEngine {
  +UUID id
  +CouponDiscountEngineStatus status
  +long version
  +validateInvariants()
}
class CouponDiscountEngineService {
  +handle(command)
}
class CouponDiscountEngineRepository {
  <<interface>>
  +findById(UUID id) CouponDiscountEngine
  +save(CouponDiscountEngine aggregate, long expectedVersion)
}
class CouponDiscountEnginePolicy {
  <<interface>>
  +evaluate(context) Decision
}
CouponDiscountEngineService --> CouponDiscountEngineRepository
CouponDiscountEngineService --> CouponDiscountEnginePolicy
CouponDiscountEngineService --> CouponDiscountEngine
class Coupon {
  +UUID id
  +validate()
}
CouponDiscountEngine "1" o-- "many" Coupon
class DiscountRule {
  +UUID id
  +validate()
}
CouponDiscountEngine "1" o-- "many" DiscountRule
class CartContext {
  +UUID id
  +validate()
}
CouponDiscountEngine "1" o-- "many" CartContext
class Promotion {
  +UUID id
  +validate()
}
CouponDiscountEngine "1" o-- "many" Promotion
class Money {
  <<value object>>
}
CouponDiscountEngine ..> Money
class Percentage {
  <<value object>>
}
CouponDiscountEngine ..> Percentage
class CouponCode {
  <<value object>>
}
CouponDiscountEngine ..> CouponCode
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as CouponDiscountEngineService
participant Repo as CouponDiscountEngineRepository
participant Policy as CouponDiscountEnginePolicy
participant Agg as CouponDiscountEngine
participant Outbox
Client->>Service: validateCoupon(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: validateCoupon(command)
Agg-->>Service: CouponDiscountEngineValidateCouponEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| Strategy | Swap algorithms such as pricing, ranking, scheduling, matching, or retry without changing the aggregate. |
| Specification | Compose business predicates and keep rule evaluation explainable. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.couponanddiscountengine;

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

enum CouponDiscountEngineStatus {
    DRAFT,
    ACTIVE,
    APPLIED,
    EXPIRED,
    DISABLED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record CouponDiscountEngineValidateCouponEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record CouponDiscountEngineCalculateDiscountEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record CouponDiscountEngineComposeAdjustmentsEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record CouponDiscountEngineRecordRedemptionEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface CouponDiscountEngineCommand permits ValidateCouponCommand, CalculateDiscountCommand, ComposeAdjustmentsCommand, RecordRedemptionCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record ValidateCouponCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CouponDiscountEngineCommand {}
record CalculateDiscountCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CouponDiscountEngineCommand {}
record ComposeAdjustmentsCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CouponDiscountEngineCommand {}
record RecordRedemptionCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CouponDiscountEngineCommand {}

interface CouponDiscountEngineRepository {
    Optional<CouponDiscountEngine> findById(UUID id);
    void save(CouponDiscountEngine aggregate, long expectedVersion);
}

interface CouponDiscountEnginePolicy {
    Decision evaluate(CouponDiscountEngine aggregate, CouponDiscountEngineCommand command);
}

final class Coupon {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class CouponDiscountEngine {
    private final UUID id;
    private final List<Coupon> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private CouponDiscountEngineStatus status;
    private long version;

    CouponDiscountEngine(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = CouponDiscountEngineStatus.DRAFT;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    CouponDiscountEngineStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void validateCoupon(ValidateCouponCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run validateCoupon when aggregate is terminal");
    this.status = CouponDiscountEngineStatus.ACTIVE;
    this.version++;
    this.domainEvents.add(new CouponDiscountEngineValidateCouponEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void calculateDiscount(CalculateDiscountCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run calculateDiscount when aggregate is terminal");
    this.status = CouponDiscountEngineStatus.APPLIED;
    this.version++;
    this.domainEvents.add(new CouponDiscountEngineCalculateDiscountEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void composeAdjustments(ComposeAdjustmentsCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run composeAdjustments when aggregate is terminal");
    this.status = CouponDiscountEngineStatus.EXPIRED;
    this.version++;
    this.domainEvents.add(new CouponDiscountEngineComposeAdjustmentsEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void recordRedemption(RecordRedemptionCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run recordRedemption when aggregate is terminal");
    this.status = CouponDiscountEngineStatus.DISABLED;
    this.version++;
    this.domainEvents.add(new CouponDiscountEngineRecordRedemptionEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == CouponDiscountEngineStatus.DISABLED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class CouponDiscountEngineService {
    private final CouponDiscountEngineRepository repository;
    private final CouponDiscountEnginePolicy policy;
    private final Outbox outbox;

    CouponDiscountEngineService(CouponDiscountEngineRepository repository, CouponDiscountEnginePolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(CouponDiscountEngineCommand command) {
        CouponDiscountEngine aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("CouponDiscountEngine not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof ValidateCouponCommand c) aggregate.validateCoupon(c);
        if (command instanceof CalculateDiscountCommand c) aggregate.calculateDiscount(c);
        if (command instanceof ComposeAdjustmentsCommand c) aggregate.composeAdjustments(c);
        if (command instanceof RecordRedemptionCommand c) aggregate.recordRedemption(c);
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

- Persist `CouponDiscountEngine` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `CouponDiscountEngine` invariants and each command method.
- State-machine test all valid and invalid `CouponDiscountEngineStatus` transitions.
- Contract test every `CouponDiscountEngineRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `CouponDiscountEngine` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `CouponDiscountEngineService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
