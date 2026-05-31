# 037. Design Subscription Management

Source problem: `Design subscription management.`  
Category: `SaaS billing`  
Primary focus: `plan changes, trial, renewal, cancellation, entitlements`  
Archetype: `finance`

## 1. Interview Framing

Design `subscription management` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `subscription management` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `TRIALING, ACTIVE, PAST_DUE, CANCELLED, PAUSED`.
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

- `Subscriber`
- `BillingSystem`
- `EntitlementService`

Primary use cases:

- `startTrial` command on `SubscriptionManagement`
- `changePlan` command on `SubscriptionManagement`
- `renewSubscription` command on `SubscriptionManagement`
- `cancelSubscription` command on `SubscriptionManagement`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `SubscriptionManagement` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Subscription, Plan, PlanChange, Entitlement, Renewal` | Have identity and change over time under the aggregate. |
| Value objects | `Money, BillingCycle, TrialPeriod, CustomerId` | Immutable concepts compared by value. |
| Policies | `SubscriptionManagementPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `SubscriptionManagementRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
TRIALING, ACTIVE, PAST_DUE, CANCELLED, PAUSED, EXPIRED
```

Invariants:

- `SubscriptionManagement` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.
- Money and capacity changes are atomic within the transaction boundary.
- A repeated idempotency key returns the original result and never double-applies side effects.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `SubscriptionManagementService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `SubscriptionManagement` | Composes | Subscription, Plan, PlanChange | Owns invariants and lifecycle transitions. |
| `SubscriptionManagementRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `SubscriptionManagementPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class SubscriptionManagement {
  +UUID id
  +SubscriptionManagementStatus status
  +long version
  +validateInvariants()
}
class SubscriptionManagementService {
  +handle(command)
}
class SubscriptionManagementRepository {
  <<interface>>
  +findById(UUID id) SubscriptionManagement
  +save(SubscriptionManagement aggregate, long expectedVersion)
}
class SubscriptionManagementPolicy {
  <<interface>>
  +evaluate(context) Decision
}
SubscriptionManagementService --> SubscriptionManagementRepository
SubscriptionManagementService --> SubscriptionManagementPolicy
SubscriptionManagementService --> SubscriptionManagement
class Subscription {
  +UUID id
  +validate()
}
SubscriptionManagement "1" o-- "many" Subscription
class Plan {
  +UUID id
  +validate()
}
SubscriptionManagement "1" o-- "many" Plan
class PlanChange {
  +UUID id
  +validate()
}
SubscriptionManagement "1" o-- "many" PlanChange
class Entitlement {
  +UUID id
  +validate()
}
SubscriptionManagement "1" o-- "many" Entitlement
class Money {
  <<value object>>
}
SubscriptionManagement ..> Money
class BillingCycle {
  <<value object>>
}
SubscriptionManagement ..> BillingCycle
class TrialPeriod {
  <<value object>>
}
SubscriptionManagement ..> TrialPeriod
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as SubscriptionManagementService
participant Repo as SubscriptionManagementRepository
participant Policy as SubscriptionManagementPolicy
participant Agg as SubscriptionManagement
participant Outbox
Client->>Service: startTrial(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: startTrial(command)
Agg-->>Service: SubscriptionManagementStartTrialEvent
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
package lld.subscriptionmanagement;

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

enum SubscriptionManagementStatus {
    TRIALING,
    ACTIVE,
    PAST_DUE,
    CANCELLED,
    PAUSED,
    EXPIRED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record SubscriptionManagementStartTrialEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record SubscriptionManagementChangePlanEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record SubscriptionManagementRenewSubscriptionEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record SubscriptionManagementCancelSubscriptionEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface SubscriptionManagementCommand permits StartTrialCommand, ChangePlanCommand, RenewSubscriptionCommand, CancelSubscriptionCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record StartTrialCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SubscriptionManagementCommand {}
record ChangePlanCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SubscriptionManagementCommand {}
record RenewSubscriptionCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SubscriptionManagementCommand {}
record CancelSubscriptionCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SubscriptionManagementCommand {}

interface SubscriptionManagementRepository {
    Optional<SubscriptionManagement> findById(UUID id);
    void save(SubscriptionManagement aggregate, long expectedVersion);
}

interface SubscriptionManagementPolicy {
    Decision evaluate(SubscriptionManagement aggregate, SubscriptionManagementCommand command);
}

final class Subscription {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class SubscriptionManagement {
    private final UUID id;
    private final List<Subscription> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private SubscriptionManagementStatus status;
    private long version;

    SubscriptionManagement(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = SubscriptionManagementStatus.TRIALING;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    SubscriptionManagementStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void startTrial(StartTrialCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run startTrial when aggregate is terminal");
    this.status = SubscriptionManagementStatus.ACTIVE;
    this.version++;
    this.domainEvents.add(new SubscriptionManagementStartTrialEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void changePlan(ChangePlanCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run changePlan when aggregate is terminal");
    this.status = SubscriptionManagementStatus.PAST_DUE;
    this.version++;
    this.domainEvents.add(new SubscriptionManagementChangePlanEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void renewSubscription(RenewSubscriptionCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run renewSubscription when aggregate is terminal");
    this.status = SubscriptionManagementStatus.CANCELLED;
    this.version++;
    this.domainEvents.add(new SubscriptionManagementRenewSubscriptionEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void cancelSubscription(CancelSubscriptionCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run cancelSubscription when aggregate is terminal");
    this.status = SubscriptionManagementStatus.PAUSED;
    this.version++;
    this.domainEvents.add(new SubscriptionManagementCancelSubscriptionEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == SubscriptionManagementStatus.EXPIRED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class SubscriptionManagementService {
    private final SubscriptionManagementRepository repository;
    private final SubscriptionManagementPolicy policy;
    private final Outbox outbox;

    SubscriptionManagementService(SubscriptionManagementRepository repository, SubscriptionManagementPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(SubscriptionManagementCommand command) {
        SubscriptionManagement aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("SubscriptionManagement not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof StartTrialCommand c) aggregate.startTrial(c);
        if (command instanceof ChangePlanCommand c) aggregate.changePlan(c);
        if (command instanceof RenewSubscriptionCommand c) aggregate.renewSubscription(c);
        if (command instanceof CancelSubscriptionCommand c) aggregate.cancelSubscription(c);
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

- Persist `SubscriptionManagement` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `SubscriptionManagement` invariants and each command method.
- State-machine test all valid and invalid `SubscriptionManagementStatus` transitions.
- Contract test every `SubscriptionManagementRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `SubscriptionManagement` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `SubscriptionManagementService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
