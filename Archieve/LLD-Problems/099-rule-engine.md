# 099. Design Rule Engine

Source problem: `Design rule engine.`  
Category: `Enterprise rules`  
Primary focus: `parser/expression model, specification, versioning`  
Archetype: `rules`

## 1. Interview Framing

Design `rule engine` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `rule engine` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `DRAFT, VALIDATED, ACTIVE, EVALUATING, DECIDED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `RuleAuthor`
- `Application`
- `Evaluator`

Primary use cases:

- `parseRule` command on `RuleEngine`
- `validateRule` command on `RuleEngine`
- `evaluateFacts` command on `RuleEngine`
- `explainDecision` command on `RuleEngine`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `RuleEngine` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Rule, Expression, Fact, EvaluationContext, Decision` | Have identity and change over time under the aggregate. |
| Value objects | `RuleId, Version, Operator, Value` | Immutable concepts compared by value. |
| Policies | `RuleEnginePolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `RuleEngineRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
DRAFT, VALIDATED, ACTIVE, EVALUATING, DECIDED, RETIRED
```

Invariants:

- `RuleEngine` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `RuleEngineService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `RuleEngine` | Composes | Rule, Expression, Fact | Owns invariants and lifecycle transitions. |
| `RuleEngineRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `RuleEnginePolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class RuleEngine {
  +UUID id
  +RuleEngineStatus status
  +long version
  +validateInvariants()
}
class RuleEngineService {
  +handle(command)
}
class RuleEngineRepository {
  <<interface>>
  +findById(UUID id) RuleEngine
  +save(RuleEngine aggregate, long expectedVersion)
}
class RuleEnginePolicy {
  <<interface>>
  +evaluate(context) Decision
}
RuleEngineService --> RuleEngineRepository
RuleEngineService --> RuleEnginePolicy
RuleEngineService --> RuleEngine
class Rule {
  +UUID id
  +validate()
}
RuleEngine "1" o-- "many" Rule
class Expression {
  +UUID id
  +validate()
}
RuleEngine "1" o-- "many" Expression
class Fact {
  +UUID id
  +validate()
}
RuleEngine "1" o-- "many" Fact
class EvaluationContext {
  +UUID id
  +validate()
}
RuleEngine "1" o-- "many" EvaluationContext
class RuleId {
  <<value object>>
}
RuleEngine ..> RuleId
class Version {
  <<value object>>
}
RuleEngine ..> Version
class Operator {
  <<value object>>
}
RuleEngine ..> Operator
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as RuleEngineService
participant Repo as RuleEngineRepository
participant Policy as RuleEnginePolicy
participant Agg as RuleEngine
participant Outbox
Client->>Service: parseRule(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: parseRule(command)
Agg-->>Service: RuleEngineParseRuleEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| Specification | Compose business predicates and keep rule evaluation explainable. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.ruleengine;

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

enum RuleEngineStatus {
    DRAFT,
    VALIDATED,
    ACTIVE,
    EVALUATING,
    DECIDED,
    RETIRED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record RuleEngineParseRuleEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record RuleEngineValidateRuleEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record RuleEngineEvaluateFactsEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record RuleEngineExplainDecisionEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface RuleEngineCommand permits ParseRuleCommand, ValidateRuleCommand, EvaluateFactsCommand, ExplainDecisionCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record ParseRuleCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RuleEngineCommand {}
record ValidateRuleCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RuleEngineCommand {}
record EvaluateFactsCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RuleEngineCommand {}
record ExplainDecisionCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RuleEngineCommand {}

interface RuleEngineRepository {
    Optional<RuleEngine> findById(UUID id);
    void save(RuleEngine aggregate, long expectedVersion);
}

interface RuleEnginePolicy {
    Decision evaluate(RuleEngine aggregate, RuleEngineCommand command);
}

final class Rule {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class RuleEngine {
    private final UUID id;
    private final List<Rule> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private RuleEngineStatus status;
    private long version;

    RuleEngine(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = RuleEngineStatus.DRAFT;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    RuleEngineStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void parseRule(ParseRuleCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run parseRule when aggregate is terminal");
    this.status = RuleEngineStatus.VALIDATED;
    this.version++;
    this.domainEvents.add(new RuleEngineParseRuleEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void validateRule(ValidateRuleCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run validateRule when aggregate is terminal");
    this.status = RuleEngineStatus.ACTIVE;
    this.version++;
    this.domainEvents.add(new RuleEngineValidateRuleEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void evaluateFacts(EvaluateFactsCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run evaluateFacts when aggregate is terminal");
    this.status = RuleEngineStatus.EVALUATING;
    this.version++;
    this.domainEvents.add(new RuleEngineEvaluateFactsEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void explainDecision(ExplainDecisionCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run explainDecision when aggregate is terminal");
    this.status = RuleEngineStatus.DECIDED;
    this.version++;
    this.domainEvents.add(new RuleEngineExplainDecisionEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == RuleEngineStatus.RETIRED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class RuleEngineService {
    private final RuleEngineRepository repository;
    private final RuleEnginePolicy policy;
    private final Outbox outbox;

    RuleEngineService(RuleEngineRepository repository, RuleEnginePolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(RuleEngineCommand command) {
        RuleEngine aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("RuleEngine not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof ParseRuleCommand c) aggregate.parseRule(c);
        if (command instanceof ValidateRuleCommand c) aggregate.validateRule(c);
        if (command instanceof EvaluateFactsCommand c) aggregate.evaluateFacts(c);
        if (command instanceof ExplainDecisionCommand c) aggregate.explainDecision(c);
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

- Persist `RuleEngine` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Compose business predicates and keep rule evaluation explainable. | `Specification` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `RuleEngine` invariants and each command method.
- State-machine test all valid and invalid `RuleEngineStatus` transitions.
- Contract test every `RuleEngineRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `RuleEngine` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `RuleEngineService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
