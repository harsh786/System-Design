# 090. Design Recommendation Rule Configuration

Source problem: `Design recommendation rule configuration.`  
Category: `Product/ML`  
Primary focus: `policy objects, feature flags, experiment variants`  
Archetype: `rules`

## 1. Interview Framing

Design `recommendation rule configuration` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `recommendation rule configuration` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `DRAFT, ACTIVE, EXPERIMENTING, PAUSED, RETIRED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `ProductManager`
- `ExperimentService`
- `Recommender`

Primary use cases:

- `createRule` command on `RecommendationRuleConfiguration`
- `activateVariant` command on `RecommendationRuleConfiguration`
- `evaluatePolicy` command on `RecommendationRuleConfiguration`
- `rollbackRule` command on `RecommendationRuleConfiguration`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `RecommendationRuleConfiguration` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `RecommendationRule, ExperimentVariant, FeatureFlag, RankingPolicy, Segment` | Have identity and change over time under the aggregate. |
| Value objects | `RuleId, VariantId, Weight, SegmentId` | Immutable concepts compared by value. |
| Policies | `RecommendationRuleConfigurationPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `RecommendationRuleConfigurationRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
DRAFT, ACTIVE, EXPERIMENTING, PAUSED, RETIRED
```

Invariants:

- `RecommendationRuleConfiguration` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `RecommendationRuleConfigurationService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `RecommendationRuleConfiguration` | Composes | RecommendationRule, ExperimentVariant, FeatureFlag | Owns invariants and lifecycle transitions. |
| `RecommendationRuleConfigurationRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `RecommendationRuleConfigurationPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class RecommendationRuleConfiguration {
  +UUID id
  +RecommendationRuleConfigurationStatus status
  +long version
  +validateInvariants()
}
class RecommendationRuleConfigurationService {
  +handle(command)
}
class RecommendationRuleConfigurationRepository {
  <<interface>>
  +findById(UUID id) RecommendationRuleConfiguration
  +save(RecommendationRuleConfiguration aggregate, long expectedVersion)
}
class RecommendationRuleConfigurationPolicy {
  <<interface>>
  +evaluate(context) Decision
}
RecommendationRuleConfigurationService --> RecommendationRuleConfigurationRepository
RecommendationRuleConfigurationService --> RecommendationRuleConfigurationPolicy
RecommendationRuleConfigurationService --> RecommendationRuleConfiguration
class RecommendationRule {
  +UUID id
  +validate()
}
RecommendationRuleConfiguration "1" o-- "many" RecommendationRule
class ExperimentVariant {
  +UUID id
  +validate()
}
RecommendationRuleConfiguration "1" o-- "many" ExperimentVariant
class FeatureFlag {
  +UUID id
  +validate()
}
RecommendationRuleConfiguration "1" o-- "many" FeatureFlag
class RankingPolicy {
  +UUID id
  +validate()
}
RecommendationRuleConfiguration "1" o-- "many" RankingPolicy
class RuleId {
  <<value object>>
}
RecommendationRuleConfiguration ..> RuleId
class VariantId {
  <<value object>>
}
RecommendationRuleConfiguration ..> VariantId
class Weight {
  <<value object>>
}
RecommendationRuleConfiguration ..> Weight
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as RecommendationRuleConfigurationService
participant Repo as RecommendationRuleConfigurationRepository
participant Policy as RecommendationRuleConfigurationPolicy
participant Agg as RecommendationRuleConfiguration
participant Outbox
Client->>Service: createRule(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: createRule(command)
Agg-->>Service: RecommendationRuleConfigurationCreateRuleEvent
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
package lld.recommendationruleconfiguration;

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

enum RecommendationRuleConfigurationStatus {
    DRAFT,
    ACTIVE,
    EXPERIMENTING,
    PAUSED,
    RETIRED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record RecommendationRuleConfigurationCreateRuleEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record RecommendationRuleConfigurationActivateVariantEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record RecommendationRuleConfigurationEvaluatePolicyEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record RecommendationRuleConfigurationRollbackRuleEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface RecommendationRuleConfigurationCommand permits CreateRuleCommand, ActivateVariantCommand, EvaluatePolicyCommand, RollbackRuleCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record CreateRuleCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RecommendationRuleConfigurationCommand {}
record ActivateVariantCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RecommendationRuleConfigurationCommand {}
record EvaluatePolicyCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RecommendationRuleConfigurationCommand {}
record RollbackRuleCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements RecommendationRuleConfigurationCommand {}

interface RecommendationRuleConfigurationRepository {
    Optional<RecommendationRuleConfiguration> findById(UUID id);
    void save(RecommendationRuleConfiguration aggregate, long expectedVersion);
}

interface RecommendationRuleConfigurationPolicy {
    Decision evaluate(RecommendationRuleConfiguration aggregate, RecommendationRuleConfigurationCommand command);
}

final class RecommendationRule {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class RecommendationRuleConfiguration {
    private final UUID id;
    private final List<RecommendationRule> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private RecommendationRuleConfigurationStatus status;
    private long version;

    RecommendationRuleConfiguration(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = RecommendationRuleConfigurationStatus.DRAFT;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    RecommendationRuleConfigurationStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void createRule(CreateRuleCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run createRule when aggregate is terminal");
    this.status = RecommendationRuleConfigurationStatus.ACTIVE;
    this.version++;
    this.domainEvents.add(new RecommendationRuleConfigurationCreateRuleEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void activateVariant(ActivateVariantCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run activateVariant when aggregate is terminal");
    this.status = RecommendationRuleConfigurationStatus.EXPERIMENTING;
    this.version++;
    this.domainEvents.add(new RecommendationRuleConfigurationActivateVariantEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void evaluatePolicy(EvaluatePolicyCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run evaluatePolicy when aggregate is terminal");
    this.status = RecommendationRuleConfigurationStatus.PAUSED;
    this.version++;
    this.domainEvents.add(new RecommendationRuleConfigurationEvaluatePolicyEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void rollbackRule(RollbackRuleCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run rollbackRule when aggregate is terminal");
    this.status = RecommendationRuleConfigurationStatus.RETIRED;
    this.version++;
    this.domainEvents.add(new RecommendationRuleConfigurationRollbackRuleEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == RecommendationRuleConfigurationStatus.RETIRED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class RecommendationRuleConfigurationService {
    private final RecommendationRuleConfigurationRepository repository;
    private final RecommendationRuleConfigurationPolicy policy;
    private final Outbox outbox;

    RecommendationRuleConfigurationService(RecommendationRuleConfigurationRepository repository, RecommendationRuleConfigurationPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(RecommendationRuleConfigurationCommand command) {
        RecommendationRuleConfiguration aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("RecommendationRuleConfiguration not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof CreateRuleCommand c) aggregate.createRule(c);
        if (command instanceof ActivateVariantCommand c) aggregate.activateVariant(c);
        if (command instanceof EvaluatePolicyCommand c) aggregate.evaluatePolicy(c);
        if (command instanceof RollbackRuleCommand c) aggregate.rollbackRule(c);
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

- Persist `RecommendationRuleConfiguration` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `RecommendationRuleConfiguration` invariants and each command method.
- State-machine test all valid and invalid `RecommendationRuleConfigurationStatus` transitions.
- Contract test every `RecommendationRuleConfigurationRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `RecommendationRuleConfiguration` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `RecommendationRuleConfigurationService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
