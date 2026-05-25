# 082. Design Group Chat Permissions

Source problem: `Design group chat permissions.`  
Category: `Communication`  
Primary focus: `roles, membership, moderation, state transitions`  
Archetype: `state-workflow`

## 1. Interview Framing

Design `group chat permissions` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `group chat permissions` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `INVITED, ACTIVE, MUTED, BANNED, LEFT`.
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

- `GroupAdmin`
- `Member`
- `Moderator`

Primary use cases:

- `inviteMember` command on `GroupChatPermissions`
- `changeRole` command on `GroupChatPermissions`
- `enforcePermission` command on `GroupChatPermissions`
- `moderateMember` command on `GroupChatPermissions`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `GroupChatPermissions` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Group, Membership, Role, Permission, ModerationAction` | Have identity and change over time under the aggregate. |
| Value objects | `UserId, RoleName, PermissionName, GroupId` | Immutable concepts compared by value. |
| Policies | `GroupChatPermissionsPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `GroupChatPermissionsRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
INVITED, ACTIVE, MUTED, BANNED, LEFT, REMOVED
```

Invariants:

- `GroupChatPermissions` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `GroupChatPermissionsService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `GroupChatPermissions` | Composes | Group, Membership, Role | Owns invariants and lifecycle transitions. |
| `GroupChatPermissionsRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `GroupChatPermissionsPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class GroupChatPermissions {
  +UUID id
  +GroupChatPermissionsStatus status
  +long version
  +validateInvariants()
}
class GroupChatPermissionsService {
  +handle(command)
}
class GroupChatPermissionsRepository {
  <<interface>>
  +findById(UUID id) GroupChatPermissions
  +save(GroupChatPermissions aggregate, long expectedVersion)
}
class GroupChatPermissionsPolicy {
  <<interface>>
  +evaluate(context) Decision
}
GroupChatPermissionsService --> GroupChatPermissionsRepository
GroupChatPermissionsService --> GroupChatPermissionsPolicy
GroupChatPermissionsService --> GroupChatPermissions
class Group {
  +UUID id
  +validate()
}
GroupChatPermissions "1" o-- "many" Group
class Membership {
  +UUID id
  +validate()
}
GroupChatPermissions "1" o-- "many" Membership
class Role {
  +UUID id
  +validate()
}
GroupChatPermissions "1" o-- "many" Role
class Permission {
  +UUID id
  +validate()
}
GroupChatPermissions "1" o-- "many" Permission
class UserId {
  <<value object>>
}
GroupChatPermissions ..> UserId
class RoleName {
  <<value object>>
}
GroupChatPermissions ..> RoleName
class PermissionName {
  <<value object>>
}
GroupChatPermissions ..> PermissionName
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as GroupChatPermissionsService
participant Repo as GroupChatPermissionsRepository
participant Policy as GroupChatPermissionsPolicy
participant Agg as GroupChatPermissions
participant Outbox
Client->>Service: inviteMember(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: inviteMember(command)
Agg-->>Service: GroupChatPermissionsInviteMemberEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.groupchatpermissions;

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

enum GroupChatPermissionsStatus {
    INVITED,
    ACTIVE,
    MUTED,
    BANNED,
    LEFT,
    REMOVED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record GroupChatPermissionsInviteMemberEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record GroupChatPermissionsChangeRoleEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record GroupChatPermissionsEnforcePermissionEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record GroupChatPermissionsModerateMemberEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface GroupChatPermissionsCommand permits InviteMemberCommand, ChangeRoleCommand, EnforcePermissionCommand, ModerateMemberCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record InviteMemberCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements GroupChatPermissionsCommand {}
record ChangeRoleCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements GroupChatPermissionsCommand {}
record EnforcePermissionCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements GroupChatPermissionsCommand {}
record ModerateMemberCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements GroupChatPermissionsCommand {}

interface GroupChatPermissionsRepository {
    Optional<GroupChatPermissions> findById(UUID id);
    void save(GroupChatPermissions aggregate, long expectedVersion);
}

interface GroupChatPermissionsPolicy {
    Decision evaluate(GroupChatPermissions aggregate, GroupChatPermissionsCommand command);
}

final class Group {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class GroupChatPermissions {
    private final UUID id;
    private final List<Group> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private GroupChatPermissionsStatus status;
    private long version;

    GroupChatPermissions(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = GroupChatPermissionsStatus.INVITED;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    GroupChatPermissionsStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void inviteMember(InviteMemberCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run inviteMember when aggregate is terminal");
    this.status = GroupChatPermissionsStatus.ACTIVE;
    this.version++;
    this.domainEvents.add(new GroupChatPermissionsInviteMemberEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void changeRole(ChangeRoleCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run changeRole when aggregate is terminal");
    this.status = GroupChatPermissionsStatus.MUTED;
    this.version++;
    this.domainEvents.add(new GroupChatPermissionsChangeRoleEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void enforcePermission(EnforcePermissionCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run enforcePermission when aggregate is terminal");
    this.status = GroupChatPermissionsStatus.BANNED;
    this.version++;
    this.domainEvents.add(new GroupChatPermissionsEnforcePermissionEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void moderateMember(ModerateMemberCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run moderateMember when aggregate is terminal");
    this.status = GroupChatPermissionsStatus.LEFT;
    this.version++;
    this.domainEvents.add(new GroupChatPermissionsModerateMemberEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == GroupChatPermissionsStatus.REMOVED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class GroupChatPermissionsService {
    private final GroupChatPermissionsRepository repository;
    private final GroupChatPermissionsPolicy policy;
    private final Outbox outbox;

    GroupChatPermissionsService(GroupChatPermissionsRepository repository, GroupChatPermissionsPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(GroupChatPermissionsCommand command) {
        GroupChatPermissions aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("GroupChatPermissions not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof InviteMemberCommand c) aggregate.inviteMember(c);
        if (command instanceof ChangeRoleCommand c) aggregate.changeRole(c);
        if (command instanceof EnforcePermissionCommand c) aggregate.enforcePermission(c);
        if (command instanceof ModerateMemberCommand c) aggregate.moderateMember(c);
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

- Persist `GroupChatPermissions` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `GroupChatPermissions` invariants and each command method.
- State-machine test all valid and invalid `GroupChatPermissionsStatus` transitions.
- Contract test every `GroupChatPermissionsRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `GroupChatPermissions` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `GroupChatPermissionsService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
