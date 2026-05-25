# 038. Design Tax Calculation Service

Source problem: `Design tax calculation service.`  
Category: `Finance rules`  
Primary focus: `jurisdiction strategy, rule versioning, rounding`  
Archetype: `finance`

## 1. Interview Framing

Design `tax calculation service` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `tax calculation service` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `DRAFT_RULE, ACTIVE_RULE, QUOTE_CREATED, QUOTE_EXPIRED, RETIRED_RULE`.
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

- `CheckoutService`
- `TaxAdmin`
- `JurisdictionProvider`

Primary use cases:

- `resolveJurisdiction` command on `TaxCalculationService`
- `calculateTax` command on `TaxCalculationService`
- `roundTax` command on `TaxCalculationService`
- `publishRuleVersion` command on `TaxCalculationService`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `TaxCalculationService` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `TaxRule, Jurisdiction, TaxLine, TaxQuote, RateVersion` | Have identity and change over time under the aggregate. |
| Value objects | `Money, Address, TaxRate, EffectiveDate` | Immutable concepts compared by value. |
| Policies | `TaxCalculationServicePolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `TaxCalculationServiceRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
DRAFT_RULE, ACTIVE_RULE, QUOTE_CREATED, QUOTE_EXPIRED, RETIRED_RULE
```

Invariants:

- `TaxCalculationService` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.
- Money and capacity changes are atomic within the transaction boundary.
- A repeated idempotency key returns the original result and never double-applies side effects.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `TaxCalculationServiceService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `TaxCalculationService` | Composes | TaxRule, Jurisdiction, TaxLine | Owns invariants and lifecycle transitions. |
| `TaxCalculationServiceRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `TaxCalculationServicePolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class TaxCalculationService {
  +UUID id
  +TaxCalculationServiceStatus status
  +long version
  +validateInvariants()
}
class TaxCalculationServiceService {
  +handle(command)
}
class TaxCalculationServiceRepository {
  <<interface>>
  +findById(UUID id) TaxCalculationService
  +save(TaxCalculationService aggregate, long expectedVersion)
}
class TaxCalculationServicePolicy {
  <<interface>>
  +evaluate(context) Decision
}
TaxCalculationServiceService --> TaxCalculationServiceRepository
TaxCalculationServiceService --> TaxCalculationServicePolicy
TaxCalculationServiceService --> TaxCalculationService
class TaxRule {
  +UUID id
  +validate()
}
TaxCalculationService "1" o-- "many" TaxRule
class Jurisdiction {
  +UUID id
  +validate()
}
TaxCalculationService "1" o-- "many" Jurisdiction
class TaxLine {
  +UUID id
  +validate()
}
TaxCalculationService "1" o-- "many" TaxLine
class TaxQuote {
  +UUID id
  +validate()
}
TaxCalculationService "1" o-- "many" TaxQuote
class Money {
  <<value object>>
}
TaxCalculationService ..> Money
class Address {
  <<value object>>
}
TaxCalculationService ..> Address
class TaxRate {
  <<value object>>
}
TaxCalculationService ..> TaxRate
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as TaxCalculationServiceService
participant Repo as TaxCalculationServiceRepository
participant Policy as TaxCalculationServicePolicy
participant Agg as TaxCalculationService
participant Outbox
Client->>Service: resolveJurisdiction(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: resolveJurisdiction(command)
Agg-->>Service: TaxCalculationServiceResolveJurisdictionEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |
| Strategy | Swap algorithms such as pricing, ranking, scheduling, matching, or retry without changing the aggregate. |
| Specification | Compose business predicates and keep rule evaluation explainable. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.taxcalculationservice;

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

enum TaxCalculationServiceStatus {
    DRAFT_RULE,
    ACTIVE_RULE,
    QUOTE_CREATED,
    QUOTE_EXPIRED,
    RETIRED_RULE
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record TaxCalculationServiceResolveJurisdictionEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record TaxCalculationServiceCalculateTaxEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record TaxCalculationServiceRoundTaxEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record TaxCalculationServicePublishRuleVersionEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface TaxCalculationServiceCommand permits ResolveJurisdictionCommand, CalculateTaxCommand, RoundTaxCommand, PublishRuleVersionCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record ResolveJurisdictionCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements TaxCalculationServiceCommand {}
record CalculateTaxCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements TaxCalculationServiceCommand {}
record RoundTaxCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements TaxCalculationServiceCommand {}
record PublishRuleVersionCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements TaxCalculationServiceCommand {}

interface TaxCalculationServiceRepository {
    Optional<TaxCalculationService> findById(UUID id);
    void save(TaxCalculationService aggregate, long expectedVersion);
}

interface TaxCalculationServicePolicy {
    Decision evaluate(TaxCalculationService aggregate, TaxCalculationServiceCommand command);
}

final class TaxRule {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class TaxCalculationService {
    private final UUID id;
    private final List<TaxRule> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private TaxCalculationServiceStatus status;
    private long version;

    TaxCalculationService(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = TaxCalculationServiceStatus.DRAFT_RULE;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    TaxCalculationServiceStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void resolveJurisdiction(ResolveJurisdictionCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run resolveJurisdiction when aggregate is terminal");
    this.status = TaxCalculationServiceStatus.ACTIVE_RULE;
    this.version++;
    this.domainEvents.add(new TaxCalculationServiceResolveJurisdictionEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void calculateTax(CalculateTaxCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run calculateTax when aggregate is terminal");
    this.status = TaxCalculationServiceStatus.QUOTE_CREATED;
    this.version++;
    this.domainEvents.add(new TaxCalculationServiceCalculateTaxEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void roundTax(RoundTaxCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run roundTax when aggregate is terminal");
    this.status = TaxCalculationServiceStatus.QUOTE_EXPIRED;
    this.version++;
    this.domainEvents.add(new TaxCalculationServiceRoundTaxEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void publishRuleVersion(PublishRuleVersionCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run publishRuleVersion when aggregate is terminal");
    this.status = TaxCalculationServiceStatus.RETIRED_RULE;
    this.version++;
    this.domainEvents.add(new TaxCalculationServicePublishRuleVersionEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == TaxCalculationServiceStatus.RETIRED_RULE;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class TaxCalculationServiceService {
    private final TaxCalculationServiceRepository repository;
    private final TaxCalculationServicePolicy policy;
    private final Outbox outbox;

    TaxCalculationServiceService(TaxCalculationServiceRepository repository, TaxCalculationServicePolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(TaxCalculationServiceCommand command) {
        TaxCalculationService aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("TaxCalculationService not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof ResolveJurisdictionCommand c) aggregate.resolveJurisdiction(c);
        if (command instanceof CalculateTaxCommand c) aggregate.calculateTax(c);
        if (command instanceof RoundTaxCommand c) aggregate.roundTax(c);
        if (command instanceof PublishRuleVersionCommand c) aggregate.publishRuleVersion(c);
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

- Persist `TaxCalculationService` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Compose business predicates and keep rule evaluation explainable. | `Specification` |
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `TaxCalculationService` invariants and each command method.
- State-machine test all valid and invalid `TaxCalculationServiceStatus` transitions.
- Contract test every `TaxCalculationServiceRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `TaxCalculationService` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `TaxCalculationServiceService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
