# 079. Design Document Sharing Permissions

Source problem: `Design document sharing permissions.`  
Category: `Collaboration`  
Primary focus: `ACLs, inherited permissions, link sharing, audit`  
Archetype: `domain`

## 1. Interview Framing

Design `document sharing permissions` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `document sharing permissions` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `PRIVATE, SHARED, LINK_ENABLED, REVOKED, INHERITED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `Owner`
- `Collaborator`
- `PermissionService`

Primary use cases:

- `grantAccess` command on `DocumentSharingPermissions`
- `revokeAccess` command on `DocumentSharingPermissions`
- `enableLink` command on `DocumentSharingPermissions`
- `authorizeAccess` command on `DocumentSharingPermissions`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `DocumentSharingPermissions` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Document, Principal, AccessGrant, ShareLink, AuditRecord` | Have identity and change over time under the aggregate. |
| Value objects | `Permission, PrincipalId, ResourceId, LinkToken` | Immutable concepts compared by value. |
| Policies | `DocumentSharingPermissionsPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `DocumentSharingPermissionsRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
PRIVATE, SHARED, LINK_ENABLED, REVOKED, INHERITED
```

Invariants:

- `DocumentSharingPermissions` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `DocumentSharingPermissionsService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `DocumentSharingPermissions` | Composes | Document, Principal, AccessGrant | Owns invariants and lifecycle transitions. |
| `DocumentSharingPermissionsRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `DocumentSharingPermissionsPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class DocumentSharingPermissions {
  +UUID id
  +DocumentSharingPermissionsStatus status
  +long version
  +validateInvariants()
}
class DocumentSharingPermissionsService {
  +handle(command)
}
class DocumentSharingPermissionsRepository {
  <<interface>>
  +findById(UUID id) DocumentSharingPermissions
  +save(DocumentSharingPermissions aggregate, long expectedVersion)
}
class DocumentSharingPermissionsPolicy {
  <<interface>>
  +evaluate(context) Decision
}
DocumentSharingPermissionsService --> DocumentSharingPermissionsRepository
DocumentSharingPermissionsService --> DocumentSharingPermissionsPolicy
DocumentSharingPermissionsService --> DocumentSharingPermissions
class Document {
  +UUID id
  +validate()
}
DocumentSharingPermissions "1" o-- "many" Document
class Principal {
  +UUID id
  +validate()
}
DocumentSharingPermissions "1" o-- "many" Principal
class AccessGrant {
  +UUID id
  +validate()
}
DocumentSharingPermissions "1" o-- "many" AccessGrant
class ShareLink {
  +UUID id
  +validate()
}
DocumentSharingPermissions "1" o-- "many" ShareLink
class Permission {
  <<value object>>
}
DocumentSharingPermissions ..> Permission
class PrincipalId {
  <<value object>>
}
DocumentSharingPermissions ..> PrincipalId
class ResourceId {
  <<value object>>
}
DocumentSharingPermissions ..> ResourceId
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as DocumentSharingPermissionsService
participant Repo as DocumentSharingPermissionsRepository
participant Policy as DocumentSharingPermissionsPolicy
participant Agg as DocumentSharingPermissions
participant Outbox
Client->>Service: grantAccess(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: grantAccess(command)
Agg-->>Service: DocumentSharingPermissionsGrantAccessEvent
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
package lld.documentsharingpermissions;

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

enum DocumentSharingPermissionsStatus {
    PRIVATE,
    SHARED,
    LINK_ENABLED,
    REVOKED,
    INHERITED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record DocumentSharingPermissionsGrantAccessEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record DocumentSharingPermissionsRevokeAccessEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record DocumentSharingPermissionsEnableLinkEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record DocumentSharingPermissionsAuthorizeAccessEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface DocumentSharingPermissionsCommand permits GrantAccessCommand, RevokeAccessCommand, EnableLinkCommand, AuthorizeAccessCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record GrantAccessCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements DocumentSharingPermissionsCommand {}
record RevokeAccessCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements DocumentSharingPermissionsCommand {}
record EnableLinkCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements DocumentSharingPermissionsCommand {}
record AuthorizeAccessCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements DocumentSharingPermissionsCommand {}

interface DocumentSharingPermissionsRepository {
    Optional<DocumentSharingPermissions> findById(UUID id);
    void save(DocumentSharingPermissions aggregate, long expectedVersion);
}

interface DocumentSharingPermissionsPolicy {
    Decision evaluate(DocumentSharingPermissions aggregate, DocumentSharingPermissionsCommand command);
}

final class Document {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class DocumentSharingPermissions {
    private final UUID id;
    private final List<Document> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private DocumentSharingPermissionsStatus status;
    private long version;

    DocumentSharingPermissions(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = DocumentSharingPermissionsStatus.PRIVATE;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    DocumentSharingPermissionsStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void grantAccess(GrantAccessCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run grantAccess when aggregate is terminal");
    this.status = DocumentSharingPermissionsStatus.SHARED;
    this.version++;
    this.domainEvents.add(new DocumentSharingPermissionsGrantAccessEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void revokeAccess(RevokeAccessCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run revokeAccess when aggregate is terminal");
    this.status = DocumentSharingPermissionsStatus.LINK_ENABLED;
    this.version++;
    this.domainEvents.add(new DocumentSharingPermissionsRevokeAccessEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void enableLink(EnableLinkCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run enableLink when aggregate is terminal");
    this.status = DocumentSharingPermissionsStatus.REVOKED;
    this.version++;
    this.domainEvents.add(new DocumentSharingPermissionsEnableLinkEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void authorizeAccess(AuthorizeAccessCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run authorizeAccess when aggregate is terminal");
    this.status = DocumentSharingPermissionsStatus.INHERITED;
    this.version++;
    this.domainEvents.add(new DocumentSharingPermissionsAuthorizeAccessEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == DocumentSharingPermissionsStatus.INHERITED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class DocumentSharingPermissionsService {
    private final DocumentSharingPermissionsRepository repository;
    private final DocumentSharingPermissionsPolicy policy;
    private final Outbox outbox;

    DocumentSharingPermissionsService(DocumentSharingPermissionsRepository repository, DocumentSharingPermissionsPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(DocumentSharingPermissionsCommand command) {
        DocumentSharingPermissions aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("DocumentSharingPermissions not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof GrantAccessCommand c) aggregate.grantAccess(c);
        if (command instanceof RevokeAccessCommand c) aggregate.revokeAccess(c);
        if (command instanceof EnableLinkCommand c) aggregate.enableLink(c);
        if (command instanceof AuthorizeAccessCommand c) aggregate.authorizeAccess(c);
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

- Persist `DocumentSharingPermissions` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `DocumentSharingPermissions` invariants and each command method.
- State-machine test all valid and invalid `DocumentSharingPermissionsStatus` transitions.
- Contract test every `DocumentSharingPermissionsRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `DocumentSharingPermissions` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `DocumentSharingPermissionsService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
