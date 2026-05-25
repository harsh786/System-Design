# 040. Design Fraud Rule Engine

Source problem: `Design fraud rule engine.`  
Category: `Risk`  
Primary focus: `Specification, rule composition, explainability, versioning`  
Archetype: `finance`

## 1. Interview Framing

Design `fraud rule engine` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `fraud rule engine` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `DRAFT, ACTIVE, EVALUATED, FLAGGED, APPROVED`.
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

- `RiskAnalyst`
- `TransactionService`
- `Reviewer`

Primary use cases:

- `publishRule` command on `FraudRuleEngine`
- `evaluateTransaction` command on `FraudRuleEngine`
- `explainDecision` command on `FraudRuleEngine`
- `openCase` command on `FraudRuleEngine`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `FraudRuleEngine` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `FraudRule, RuleSet, Signal, Decision, Case` | Have identity and change over time under the aggregate. |
| Value objects | `Score, RuleId, Version, ReasonCode` | Immutable concepts compared by value. |
| Policies | `FraudRuleEnginePolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `FraudRuleEngineRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
DRAFT, ACTIVE, EVALUATED, FLAGGED, APPROVED, BLOCKED
```

Invariants:

- `FraudRuleEngine` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.
- Money and capacity changes are atomic within the transaction boundary.
- A repeated idempotency key returns the original result and never double-applies side effects.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `FraudRuleEngineService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `FraudRuleEngine` | Composes | FraudRule, RuleSet, Signal | Owns invariants and lifecycle transitions. |
| `FraudRuleEngineRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `FraudRuleEnginePolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class FraudRuleEngine {
  +UUID id
  +FraudRuleEngineStatus status
  +long version
  +validateInvariants()
}
class FraudRuleEngineService {
  +handle(command)
}
class FraudRuleEngineRepository {
  <<interface>>
  +findById(UUID id) FraudRuleEngine
  +save(FraudRuleEngine aggregate, long expectedVersion)
}
class FraudRuleEnginePolicy {
  <<interface>>
  +evaluate(context) Decision
}
FraudRuleEngineService --> FraudRuleEngineRepository
FraudRuleEngineService --> FraudRuleEnginePolicy
FraudRuleEngineService --> FraudRuleEngine
class FraudRule {
  +UUID id
  +validate()
}
FraudRuleEngine "1" o-- "many" FraudRule
class RuleSet {
  +UUID id
  +validate()
}
FraudRuleEngine "1" o-- "many" RuleSet
class Signal {
  +UUID id
  +validate()
}
FraudRuleEngine "1" o-- "many" Signal
class Decision {
  +UUID id
  +validate()
}
FraudRuleEngine "1" o-- "many" Decision
class Score {
  <<value object>>
}
FraudRuleEngine ..> Score
class RuleId {
  <<value object>>
}
FraudRuleEngine ..> RuleId
class Version {
  <<value object>>
}
FraudRuleEngine ..> Version
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as FraudRuleEngineService
participant Repo as FraudRuleEngineRepository
participant Policy as FraudRuleEnginePolicy
participant Agg as FraudRuleEngine
participant Outbox
Client->>Service: publishRule(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: publishRule(command)
Agg-->>Service: FraudRuleEnginePublishRuleEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |
| Specification | Compose business predicates and keep rule evaluation explainable. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.fraudruleengine;

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

enum FraudRuleEngineStatus {
    DRAFT,
    ACTIVE,
    EVALUATED,
    FLAGGED,
    APPROVED,
    BLOCKED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record FraudRuleEnginePublishRuleEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record FraudRuleEngineEvaluateTransactionEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record FraudRuleEngineExplainDecisionEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record FraudRuleEngineOpenCaseEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface FraudRuleEngineCommand permits PublishRuleCommand, EvaluateTransactionCommand, ExplainDecisionCommand, OpenCaseCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record PublishRuleCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements FraudRuleEngineCommand {}
record EvaluateTransactionCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements FraudRuleEngineCommand {}
record ExplainDecisionCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements FraudRuleEngineCommand {}
record OpenCaseCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements FraudRuleEngineCommand {}

interface FraudRuleEngineRepository {
    Optional<FraudRuleEngine> findById(UUID id);
    void save(FraudRuleEngine aggregate, long expectedVersion);
}

interface FraudRuleEnginePolicy {
    Decision evaluate(FraudRuleEngine aggregate, FraudRuleEngineCommand command);
}

final class FraudRule {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class FraudRuleEngine {
    private final UUID id;
    private final List<FraudRule> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private FraudRuleEngineStatus status;
    private long version;

    FraudRuleEngine(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = FraudRuleEngineStatus.DRAFT;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    FraudRuleEngineStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void publishRule(PublishRuleCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run publishRule when aggregate is terminal");
    this.status = FraudRuleEngineStatus.ACTIVE;
    this.version++;
    this.domainEvents.add(new FraudRuleEnginePublishRuleEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void evaluateTransaction(EvaluateTransactionCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run evaluateTransaction when aggregate is terminal");
    this.status = FraudRuleEngineStatus.EVALUATED;
    this.version++;
    this.domainEvents.add(new FraudRuleEngineEvaluateTransactionEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void explainDecision(ExplainDecisionCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run explainDecision when aggregate is terminal");
    this.status = FraudRuleEngineStatus.FLAGGED;
    this.version++;
    this.domainEvents.add(new FraudRuleEngineExplainDecisionEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void openCase(OpenCaseCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run openCase when aggregate is terminal");
    this.status = FraudRuleEngineStatus.APPROVED;
    this.version++;
    this.domainEvents.add(new FraudRuleEngineOpenCaseEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == FraudRuleEngineStatus.BLOCKED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class FraudRuleEngineService {
    private final FraudRuleEngineRepository repository;
    private final FraudRuleEnginePolicy policy;
    private final Outbox outbox;

    FraudRuleEngineService(FraudRuleEngineRepository repository, FraudRuleEnginePolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(FraudRuleEngineCommand command) {
        FraudRuleEngine aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("FraudRuleEngine not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof PublishRuleCommand c) aggregate.publishRule(c);
        if (command instanceof EvaluateTransactionCommand c) aggregate.evaluateTransaction(c);
        if (command instanceof ExplainDecisionCommand c) aggregate.explainDecision(c);
        if (command instanceof OpenCaseCommand c) aggregate.openCase(c);
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

- Persist `FraudRuleEngine` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Compose business predicates and keep rule evaluation explainable. | `Specification` |
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `FraudRuleEngine` invariants and each command method.
- State-machine test all valid and invalid `FraudRuleEngineStatus` transitions.
- Contract test every `FraudRuleEngineRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `FraudRuleEngine` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `FraudRuleEngineService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
