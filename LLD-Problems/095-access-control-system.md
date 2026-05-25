# 095. Design Access Control System

Source problem: `Design access control system.`  
Category: `Security`  
Primary focus: `RBAC/ABAC, policies, resources, audit`  
Archetype: `domain`

## 1. Interview Framing

Design `access control system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `access control system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `POLICY_DRAFT, POLICY_ACTIVE, AUTHORIZED, DENIED, REVOKED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `Subject`
- `ResourceOwner`
- `PolicyAdmin`

Primary use cases:

- `assignRole` command on `AccessControlSystem`
- `definePolicy` command on `AccessControlSystem`
- `authorize` command on `AccessControlSystem`
- `recordAudit` command on `AccessControlSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `AccessControlSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Subject, Resource, Role, Policy, AccessDecision` | Have identity and change over time under the aggregate. |
| Value objects | `Permission, ResourceId, PrincipalId, ContextAttribute` | Immutable concepts compared by value. |
| Policies | `AccessControlSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `AccessControlSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
POLICY_DRAFT, POLICY_ACTIVE, AUTHORIZED, DENIED, REVOKED
```

Invariants:

- `AccessControlSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `AccessControlSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `AccessControlSystem` | Composes | Subject, Resource, Role | Owns invariants and lifecycle transitions. |
| `AccessControlSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `AccessControlSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class AccessControlSystem {
  +UUID id
  +AccessControlSystemStatus status
  +long version
  +validateInvariants()
}
class AccessControlSystemService {
  +handle(command)
}
class AccessControlSystemRepository {
  <<interface>>
  +findById(UUID id) AccessControlSystem
  +save(AccessControlSystem aggregate, long expectedVersion)
}
class AccessControlSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
AccessControlSystemService --> AccessControlSystemRepository
AccessControlSystemService --> AccessControlSystemPolicy
AccessControlSystemService --> AccessControlSystem
class Subject {
  +UUID id
  +validate()
}
AccessControlSystem "1" o-- "many" Subject
class Resource {
  +UUID id
  +validate()
}
AccessControlSystem "1" o-- "many" Resource
class Role {
  +UUID id
  +validate()
}
AccessControlSystem "1" o-- "many" Role
class Policy {
  +UUID id
  +validate()
}
AccessControlSystem "1" o-- "many" Policy
class Permission {
  <<value object>>
}
AccessControlSystem ..> Permission
class ResourceId {
  <<value object>>
}
AccessControlSystem ..> ResourceId
class PrincipalId {
  <<value object>>
}
AccessControlSystem ..> PrincipalId
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as AccessControlSystemService
participant Repo as AccessControlSystemRepository
participant Policy as AccessControlSystemPolicy
participant Agg as AccessControlSystem
participant Outbox
Client->>Service: assignRole(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: assignRole(command)
Agg-->>Service: AccessControlSystemAssignRoleEvent
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
package lld.accesscontrolsystem;

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

enum AccessControlSystemStatus {
    POLICY_DRAFT,
    POLICY_ACTIVE,
    AUTHORIZED,
    DENIED,
    REVOKED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record AccessControlSystemAssignRoleEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record AccessControlSystemDefinePolicyEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record AccessControlSystemAuthorizeEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record AccessControlSystemRecordAuditEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface AccessControlSystemCommand permits AssignRoleCommand, DefinePolicyCommand, AuthorizeCommand, RecordAuditCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record AssignRoleCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements AccessControlSystemCommand {}
record DefinePolicyCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements AccessControlSystemCommand {}
record AuthorizeCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements AccessControlSystemCommand {}
record RecordAuditCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements AccessControlSystemCommand {}

interface AccessControlSystemRepository {
    Optional<AccessControlSystem> findById(UUID id);
    void save(AccessControlSystem aggregate, long expectedVersion);
}

interface AccessControlSystemPolicy {
    Decision evaluate(AccessControlSystem aggregate, AccessControlSystemCommand command);
}

final class Subject {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class AccessControlSystem {
    private final UUID id;
    private final List<Subject> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private AccessControlSystemStatus status;
    private long version;

    AccessControlSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = AccessControlSystemStatus.POLICY_DRAFT;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    AccessControlSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void assignRole(AssignRoleCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run assignRole when aggregate is terminal");
    this.status = AccessControlSystemStatus.POLICY_ACTIVE;
    this.version++;
    this.domainEvents.add(new AccessControlSystemAssignRoleEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void definePolicy(DefinePolicyCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run definePolicy when aggregate is terminal");
    this.status = AccessControlSystemStatus.AUTHORIZED;
    this.version++;
    this.domainEvents.add(new AccessControlSystemDefinePolicyEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void authorize(AuthorizeCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run authorize when aggregate is terminal");
    this.status = AccessControlSystemStatus.DENIED;
    this.version++;
    this.domainEvents.add(new AccessControlSystemAuthorizeEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void recordAudit(RecordAuditCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run recordAudit when aggregate is terminal");
    this.status = AccessControlSystemStatus.REVOKED;
    this.version++;
    this.domainEvents.add(new AccessControlSystemRecordAuditEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == AccessControlSystemStatus.REVOKED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class AccessControlSystemService {
    private final AccessControlSystemRepository repository;
    private final AccessControlSystemPolicy policy;
    private final Outbox outbox;

    AccessControlSystemService(AccessControlSystemRepository repository, AccessControlSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(AccessControlSystemCommand command) {
        AccessControlSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("AccessControlSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof AssignRoleCommand c) aggregate.assignRole(c);
        if (command instanceof DefinePolicyCommand c) aggregate.definePolicy(c);
        if (command instanceof AuthorizeCommand c) aggregate.authorize(c);
        if (command instanceof RecordAuditCommand c) aggregate.recordAudit(c);
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

- Persist `AccessControlSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `AccessControlSystem` invariants and each command method.
- State-machine test all valid and invalid `AccessControlSystemStatus` transitions.
- Contract test every `AccessControlSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `AccessControlSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `AccessControlSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
