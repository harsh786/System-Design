# 096. Design Secrets Manager LLD

Source problem: `Design secrets manager LLD.`  
Category: `Security`  
Primary focus: `encryption, rotation, versioning, access policy`  
Archetype: `rules`

## 1. Interview Framing

Design `secrets manager LLD` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `secrets manager LLD` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `CREATED, ACTIVE, ROTATING, DISABLED, DESTROYED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `Application`
- `SecurityAdmin`
- `KMSProvider`

Primary use cases:

- `createSecret` command on `SecretsManager`
- `readSecret` command on `SecretsManager`
- `rotateSecret` command on `SecretsManager`
- `revokeAccess` command on `SecretsManager`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `SecretsManager` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Secret, SecretVersion, RotationPolicy, AccessGrant, AuditRecord` | Have identity and change over time under the aggregate. |
| Value objects | `SecretId, Version, EncryptedBytes, PrincipalId` | Immutable concepts compared by value. |
| Policies | `SecretsManagerPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `SecretsManagerRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
CREATED, ACTIVE, ROTATING, DISABLED, DESTROYED
```

Invariants:

- `SecretsManager` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `SecretsManagerService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `SecretsManager` | Composes | Secret, SecretVersion, RotationPolicy | Owns invariants and lifecycle transitions. |
| `SecretsManagerRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `SecretsManagerPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class SecretsManager {
  +UUID id
  +SecretsManagerStatus status
  +long version
  +validateInvariants()
}
class SecretsManagerService {
  +handle(command)
}
class SecretsManagerRepository {
  <<interface>>
  +findById(UUID id) SecretsManager
  +save(SecretsManager aggregate, long expectedVersion)
}
class SecretsManagerPolicy {
  <<interface>>
  +evaluate(context) Decision
}
SecretsManagerService --> SecretsManagerRepository
SecretsManagerService --> SecretsManagerPolicy
SecretsManagerService --> SecretsManager
class Secret {
  +UUID id
  +validate()
}
SecretsManager "1" o-- "many" Secret
class SecretVersion {
  +UUID id
  +validate()
}
SecretsManager "1" o-- "many" SecretVersion
class RotationPolicy {
  +UUID id
  +validate()
}
SecretsManager "1" o-- "many" RotationPolicy
class AccessGrant {
  +UUID id
  +validate()
}
SecretsManager "1" o-- "many" AccessGrant
class SecretId {
  <<value object>>
}
SecretsManager ..> SecretId
class Version {
  <<value object>>
}
SecretsManager ..> Version
class EncryptedBytes {
  <<value object>>
}
SecretsManager ..> EncryptedBytes
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as SecretsManagerService
participant Repo as SecretsManagerRepository
participant Policy as SecretsManagerPolicy
participant Agg as SecretsManager
participant Outbox
Client->>Service: createSecret(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: createSecret(command)
Agg-->>Service: SecretsManagerCreateSecretEvent
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
package lld.secretsmanager;

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

enum SecretsManagerStatus {
    CREATED,
    ACTIVE,
    ROTATING,
    DISABLED,
    DESTROYED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record SecretsManagerCreateSecretEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record SecretsManagerReadSecretEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record SecretsManagerRotateSecretEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record SecretsManagerRevokeAccessEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface SecretsManagerCommand permits CreateSecretCommand, ReadSecretCommand, RotateSecretCommand, RevokeAccessCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record CreateSecretCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SecretsManagerCommand {}
record ReadSecretCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SecretsManagerCommand {}
record RotateSecretCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SecretsManagerCommand {}
record RevokeAccessCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements SecretsManagerCommand {}

interface SecretsManagerRepository {
    Optional<SecretsManager> findById(UUID id);
    void save(SecretsManager aggregate, long expectedVersion);
}

interface SecretsManagerPolicy {
    Decision evaluate(SecretsManager aggregate, SecretsManagerCommand command);
}

final class Secret {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class SecretsManager {
    private final UUID id;
    private final List<Secret> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private SecretsManagerStatus status;
    private long version;

    SecretsManager(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = SecretsManagerStatus.CREATED;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    SecretsManagerStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void createSecret(CreateSecretCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run createSecret when aggregate is terminal");
    this.status = SecretsManagerStatus.ACTIVE;
    this.version++;
    this.domainEvents.add(new SecretsManagerCreateSecretEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void readSecret(ReadSecretCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run readSecret when aggregate is terminal");
    this.status = SecretsManagerStatus.ROTATING;
    this.version++;
    this.domainEvents.add(new SecretsManagerReadSecretEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void rotateSecret(RotateSecretCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run rotateSecret when aggregate is terminal");
    this.status = SecretsManagerStatus.DISABLED;
    this.version++;
    this.domainEvents.add(new SecretsManagerRotateSecretEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void revokeAccess(RevokeAccessCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run revokeAccess when aggregate is terminal");
    this.status = SecretsManagerStatus.DESTROYED;
    this.version++;
    this.domainEvents.add(new SecretsManagerRevokeAccessEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == SecretsManagerStatus.DESTROYED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class SecretsManagerService {
    private final SecretsManagerRepository repository;
    private final SecretsManagerPolicy policy;
    private final Outbox outbox;

    SecretsManagerService(SecretsManagerRepository repository, SecretsManagerPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(SecretsManagerCommand command) {
        SecretsManager aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("SecretsManager not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof CreateSecretCommand c) aggregate.createSecret(c);
        if (command instanceof ReadSecretCommand c) aggregate.readSecret(c);
        if (command instanceof RotateSecretCommand c) aggregate.rotateSecret(c);
        if (command instanceof RevokeAccessCommand c) aggregate.revokeAccess(c);
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

- Persist `SecretsManager` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `SecretsManager` invariants and each command method.
- State-machine test all valid and invalid `SecretsManagerStatus` transitions.
- Contract test every `SecretsManagerRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `SecretsManager` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `SecretsManagerService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
