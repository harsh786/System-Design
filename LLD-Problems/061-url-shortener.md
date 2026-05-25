# 061. Design URL Shortener LLD

Source problem: `Design URL shortener LLD.`  
Category: `API/product`  
Primary focus: `key generation, repository, redirect stats, expiration`  
Archetype: `domain`

## 1. Interview Framing

Design `URL shortener LLD` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `URL shortener LLD` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `ACTIVE, EXPIRED, DISABLED, REDIRECTED, DELETED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `User`
- `RedirectClient`
- `AnalyticsCollector`

Primary use cases:

- `createShortLink` command on `URLShortener`
- `resolveShortCode` command on `URLShortener`
- `recordClick` command on `URLShortener`
- `expireLink` command on `URLShortener`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `URLShortener` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `ShortLink, RedirectRecord, KeyGenerator, ExpirationPolicy` | Have identity and change over time under the aggregate. |
| Value objects | `URL, ShortCode, TTL, ClickId` | Immutable concepts compared by value. |
| Policies | `URLShortenerPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `URLShortenerRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
ACTIVE, EXPIRED, DISABLED, REDIRECTED, DELETED
```

Invariants:

- `URLShortener` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `URLShortenerService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `URLShortener` | Composes | ShortLink, RedirectRecord, KeyGenerator | Owns invariants and lifecycle transitions. |
| `URLShortenerRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `URLShortenerPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class URLShortener {
  +UUID id
  +URLShortenerStatus status
  +long version
  +validateInvariants()
}
class URLShortenerService {
  +handle(command)
}
class URLShortenerRepository {
  <<interface>>
  +findById(UUID id) URLShortener
  +save(URLShortener aggregate, long expectedVersion)
}
class URLShortenerPolicy {
  <<interface>>
  +evaluate(context) Decision
}
URLShortenerService --> URLShortenerRepository
URLShortenerService --> URLShortenerPolicy
URLShortenerService --> URLShortener
class ShortLink {
  +UUID id
  +validate()
}
URLShortener "1" o-- "many" ShortLink
class RedirectRecord {
  +UUID id
  +validate()
}
URLShortener "1" o-- "many" RedirectRecord
class KeyGenerator {
  +UUID id
  +validate()
}
URLShortener "1" o-- "many" KeyGenerator
class ExpirationPolicy {
  +UUID id
  +validate()
}
URLShortener "1" o-- "many" ExpirationPolicy
class URL {
  <<value object>>
}
URLShortener ..> URL
class ShortCode {
  <<value object>>
}
URLShortener ..> ShortCode
class TTL {
  <<value object>>
}
URLShortener ..> TTL
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as URLShortenerService
participant Repo as URLShortenerRepository
participant Policy as URLShortenerPolicy
participant Agg as URLShortener
participant Outbox
Client->>Service: createShortLink(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: createShortLink(command)
Agg-->>Service: URLShortenerCreateShortLinkEvent
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
package lld.urlshortener;

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

enum URLShortenerStatus {
    ACTIVE,
    EXPIRED,
    DISABLED,
    REDIRECTED,
    DELETED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record URLShortenerCreateShortLinkEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record URLShortenerResolveShortCodeEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record URLShortenerRecordClickEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record URLShortenerExpireLinkEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface URLShortenerCommand permits CreateShortLinkCommand, ResolveShortCodeCommand, RecordClickCommand, ExpireLinkCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record CreateShortLinkCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements URLShortenerCommand {}
record ResolveShortCodeCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements URLShortenerCommand {}
record RecordClickCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements URLShortenerCommand {}
record ExpireLinkCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements URLShortenerCommand {}

interface URLShortenerRepository {
    Optional<URLShortener> findById(UUID id);
    void save(URLShortener aggregate, long expectedVersion);
}

interface URLShortenerPolicy {
    Decision evaluate(URLShortener aggregate, URLShortenerCommand command);
}

final class ShortLink {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class URLShortener {
    private final UUID id;
    private final List<ShortLink> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private URLShortenerStatus status;
    private long version;

    URLShortener(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = URLShortenerStatus.ACTIVE;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    URLShortenerStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void createShortLink(CreateShortLinkCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run createShortLink when aggregate is terminal");
    this.status = URLShortenerStatus.EXPIRED;
    this.version++;
    this.domainEvents.add(new URLShortenerCreateShortLinkEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void resolveShortCode(ResolveShortCodeCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run resolveShortCode when aggregate is terminal");
    this.status = URLShortenerStatus.DISABLED;
    this.version++;
    this.domainEvents.add(new URLShortenerResolveShortCodeEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void recordClick(RecordClickCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run recordClick when aggregate is terminal");
    this.status = URLShortenerStatus.REDIRECTED;
    this.version++;
    this.domainEvents.add(new URLShortenerRecordClickEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void expireLink(ExpireLinkCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run expireLink when aggregate is terminal");
    this.status = URLShortenerStatus.DELETED;
    this.version++;
    this.domainEvents.add(new URLShortenerExpireLinkEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == URLShortenerStatus.DELETED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class URLShortenerService {
    private final URLShortenerRepository repository;
    private final URLShortenerPolicy policy;
    private final Outbox outbox;

    URLShortenerService(URLShortenerRepository repository, URLShortenerPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(URLShortenerCommand command) {
        URLShortener aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("URLShortener not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof CreateShortLinkCommand c) aggregate.createShortLink(c);
        if (command instanceof ResolveShortCodeCommand c) aggregate.resolveShortCode(c);
        if (command instanceof RecordClickCommand c) aggregate.recordClick(c);
        if (command instanceof ExpireLinkCommand c) aggregate.expireLink(c);
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

- Persist `URLShortener` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `URLShortener` invariants and each command method.
- State-machine test all valid and invalid `URLShortenerStatus` transitions.
- Contract test every `URLShortenerRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `URLShortener` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `URLShortenerService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
