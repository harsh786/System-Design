# 100. Design Form Builder And Validation Engine

Source problem: `Design form builder and validation engine.`  
Category: `Enterprise app`  
Primary focus: `schema, fields, validators, conditional logic`  
Archetype: `domain`

## 1. Interview Framing

Design `form builder and validation engine` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `form builder and validation engine` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `DRAFT, PUBLISHED, FILLING, VALIDATING, SUBMITTED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `FormAuthor`
- `EndUser`
- `Validator`

Primary use cases:

- `buildForm` command on `FormBuilderValidationEngine`
- `renderForm` command on `FormBuilderValidationEngine`
- `validateSubmission` command on `FormBuilderValidationEngine`
- `applyConditionalLogic` command on `FormBuilderValidationEngine`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `FormBuilderValidationEngine` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `FormSchema, Field, ValidatorRule, ConditionalLogic, Submission` | Have identity and change over time under the aggregate. |
| Value objects | `FieldId, FieldType, Value, ErrorCode` | Immutable concepts compared by value. |
| Policies | `FormBuilderValidationEnginePolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `FormBuilderValidationEngineRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
DRAFT, PUBLISHED, FILLING, VALIDATING, SUBMITTED, REJECTED
```

Invariants:

- `FormBuilderValidationEngine` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `FormBuilderValidationEngineService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `FormBuilderValidationEngine` | Composes | FormSchema, Field, ValidatorRule | Owns invariants and lifecycle transitions. |
| `FormBuilderValidationEngineRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `FormBuilderValidationEnginePolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class FormBuilderValidationEngine {
  +UUID id
  +FormBuilderValidationEngineStatus status
  +long version
  +validateInvariants()
}
class FormBuilderValidationEngineService {
  +handle(command)
}
class FormBuilderValidationEngineRepository {
  <<interface>>
  +findById(UUID id) FormBuilderValidationEngine
  +save(FormBuilderValidationEngine aggregate, long expectedVersion)
}
class FormBuilderValidationEnginePolicy {
  <<interface>>
  +evaluate(context) Decision
}
FormBuilderValidationEngineService --> FormBuilderValidationEngineRepository
FormBuilderValidationEngineService --> FormBuilderValidationEnginePolicy
FormBuilderValidationEngineService --> FormBuilderValidationEngine
class FormSchema {
  +UUID id
  +validate()
}
FormBuilderValidationEngine "1" o-- "many" FormSchema
class Field {
  +UUID id
  +validate()
}
FormBuilderValidationEngine "1" o-- "many" Field
class ValidatorRule {
  +UUID id
  +validate()
}
FormBuilderValidationEngine "1" o-- "many" ValidatorRule
class ConditionalLogic {
  +UUID id
  +validate()
}
FormBuilderValidationEngine "1" o-- "many" ConditionalLogic
class FieldId {
  <<value object>>
}
FormBuilderValidationEngine ..> FieldId
class FieldType {
  <<value object>>
}
FormBuilderValidationEngine ..> FieldType
class Value {
  <<value object>>
}
FormBuilderValidationEngine ..> Value
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as FormBuilderValidationEngineService
participant Repo as FormBuilderValidationEngineRepository
participant Policy as FormBuilderValidationEnginePolicy
participant Agg as FormBuilderValidationEngine
participant Outbox
Client->>Service: buildForm(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: buildForm(command)
Agg-->>Service: FormBuilderValidationEngineBuildFormEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.formbuilderandvalidationengine;

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

enum FormBuilderValidationEngineStatus {
    DRAFT,
    PUBLISHED,
    FILLING,
    VALIDATING,
    SUBMITTED,
    REJECTED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record FormBuilderValidationEngineBuildFormEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record FormBuilderValidationEngineRenderFormEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record FormBuilderValidationEngineValidateSubmissionEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record FormBuilderValidationEngineApplyConditionalLogicEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface FormBuilderValidationEngineCommand permits BuildFormCommand, RenderFormCommand, ValidateSubmissionCommand, ApplyConditionalLogicCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record BuildFormCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements FormBuilderValidationEngineCommand {}
record RenderFormCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements FormBuilderValidationEngineCommand {}
record ValidateSubmissionCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements FormBuilderValidationEngineCommand {}
record ApplyConditionalLogicCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements FormBuilderValidationEngineCommand {}

interface FormBuilderValidationEngineRepository {
    Optional<FormBuilderValidationEngine> findById(UUID id);
    void save(FormBuilderValidationEngine aggregate, long expectedVersion);
}

interface FormBuilderValidationEnginePolicy {
    Decision evaluate(FormBuilderValidationEngine aggregate, FormBuilderValidationEngineCommand command);
}

final class FormSchema {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class FormBuilderValidationEngine {
    private final UUID id;
    private final List<FormSchema> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private FormBuilderValidationEngineStatus status;
    private long version;

    FormBuilderValidationEngine(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = FormBuilderValidationEngineStatus.DRAFT;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    FormBuilderValidationEngineStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void buildForm(BuildFormCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run buildForm when aggregate is terminal");
    this.status = FormBuilderValidationEngineStatus.PUBLISHED;
    this.version++;
    this.domainEvents.add(new FormBuilderValidationEngineBuildFormEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void renderForm(RenderFormCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run renderForm when aggregate is terminal");
    this.status = FormBuilderValidationEngineStatus.FILLING;
    this.version++;
    this.domainEvents.add(new FormBuilderValidationEngineRenderFormEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void validateSubmission(ValidateSubmissionCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run validateSubmission when aggregate is terminal");
    this.status = FormBuilderValidationEngineStatus.VALIDATING;
    this.version++;
    this.domainEvents.add(new FormBuilderValidationEngineValidateSubmissionEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void applyConditionalLogic(ApplyConditionalLogicCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run applyConditionalLogic when aggregate is terminal");
    this.status = FormBuilderValidationEngineStatus.SUBMITTED;
    this.version++;
    this.domainEvents.add(new FormBuilderValidationEngineApplyConditionalLogicEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == FormBuilderValidationEngineStatus.REJECTED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class FormBuilderValidationEngineService {
    private final FormBuilderValidationEngineRepository repository;
    private final FormBuilderValidationEnginePolicy policy;
    private final Outbox outbox;

    FormBuilderValidationEngineService(FormBuilderValidationEngineRepository repository, FormBuilderValidationEnginePolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(FormBuilderValidationEngineCommand command) {
        FormBuilderValidationEngine aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("FormBuilderValidationEngine not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof BuildFormCommand c) aggregate.buildForm(c);
        if (command instanceof RenderFormCommand c) aggregate.renderForm(c);
        if (command instanceof ValidateSubmissionCommand c) aggregate.validateSubmission(c);
        if (command instanceof ApplyConditionalLogicCommand c) aggregate.applyConditionalLogic(c);
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

- Persist `FormBuilderValidationEngine` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `FormBuilderValidationEngine` invariants and each command method.
- State-machine test all valid and invalid `FormBuilderValidationEngineStatus` transitions.
- Contract test every `FormBuilderValidationEngineRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `FormBuilderValidationEngine` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `FormBuilderValidationEngineService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
