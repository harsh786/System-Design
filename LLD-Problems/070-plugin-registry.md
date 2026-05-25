# 070. Design Plugin Registry

Source problem: `Design plugin registry.`  
Category: `Extensibility`  
Primary focus: `discovery, lifecycle, versioning, isolation`  
Archetype: `state-workflow`

## 1. Interview Framing

Design `plugin registry` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `plugin registry` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `DISCOVERED, LOADED, STARTED, STOPPED, FAILED`.
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

- `Application`
- `PluginAuthor`
- `Operator`

Primary use cases:

- `discover` command on `PluginRegistry`
- `loadPlugin` command on `PluginRegistry`
- `startPlugin` command on `PluginRegistry`
- `unloadPlugin` command on `PluginRegistry`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `PluginRegistry` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Plugin, PluginDescriptor, PluginInstance, ExtensionPoint, LifecycleManager` | Have identity and change over time under the aggregate. |
| Value objects | `PluginId, Version, Capability, Dependency` | Immutable concepts compared by value. |
| Policies | `PluginRegistryPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `PluginRegistryRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
DISCOVERED, LOADED, STARTED, STOPPED, FAILED, UNLOADED
```

Invariants:

- `PluginRegistry` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `PluginRegistryService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `PluginRegistry` | Composes | Plugin, PluginDescriptor, PluginInstance | Owns invariants and lifecycle transitions. |
| `PluginRegistryRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `PluginRegistryPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class PluginRegistry {
  +UUID id
  +PluginRegistryStatus status
  +long version
  +validateInvariants()
}
class PluginRegistryService {
  +handle(command)
}
class PluginRegistryRepository {
  <<interface>>
  +findById(UUID id) PluginRegistry
  +save(PluginRegistry aggregate, long expectedVersion)
}
class PluginRegistryPolicy {
  <<interface>>
  +evaluate(context) Decision
}
PluginRegistryService --> PluginRegistryRepository
PluginRegistryService --> PluginRegistryPolicy
PluginRegistryService --> PluginRegistry
class Plugin {
  +UUID id
  +validate()
}
PluginRegistry "1" o-- "many" Plugin
class PluginDescriptor {
  +UUID id
  +validate()
}
PluginRegistry "1" o-- "many" PluginDescriptor
class PluginInstance {
  +UUID id
  +validate()
}
PluginRegistry "1" o-- "many" PluginInstance
class ExtensionPoint {
  +UUID id
  +validate()
}
PluginRegistry "1" o-- "many" ExtensionPoint
class PluginId {
  <<value object>>
}
PluginRegistry ..> PluginId
class Version {
  <<value object>>
}
PluginRegistry ..> Version
class Capability {
  <<value object>>
}
PluginRegistry ..> Capability
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as PluginRegistryService
participant Repo as PluginRegistryRepository
participant Policy as PluginRegistryPolicy
participant Agg as PluginRegistry
participant Outbox
Client->>Service: discover(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: discover(command)
Agg-->>Service: PluginRegistryDiscoverEvent
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
package lld.pluginregistry;

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

enum PluginRegistryStatus {
    DISCOVERED,
    LOADED,
    STARTED,
    STOPPED,
    FAILED,
    UNLOADED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record PluginRegistryDiscoverEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record PluginRegistryLoadPluginEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record PluginRegistryStartPluginEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record PluginRegistryUnloadPluginEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface PluginRegistryCommand permits DiscoverCommand, LoadPluginCommand, StartPluginCommand, UnloadPluginCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record DiscoverCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements PluginRegistryCommand {}
record LoadPluginCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements PluginRegistryCommand {}
record StartPluginCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements PluginRegistryCommand {}
record UnloadPluginCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements PluginRegistryCommand {}

interface PluginRegistryRepository {
    Optional<PluginRegistry> findById(UUID id);
    void save(PluginRegistry aggregate, long expectedVersion);
}

interface PluginRegistryPolicy {
    Decision evaluate(PluginRegistry aggregate, PluginRegistryCommand command);
}

final class Plugin {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class PluginRegistry {
    private final UUID id;
    private final List<Plugin> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private PluginRegistryStatus status;
    private long version;

    PluginRegistry(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = PluginRegistryStatus.DISCOVERED;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    PluginRegistryStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void discover(DiscoverCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run discover when aggregate is terminal");
    this.status = PluginRegistryStatus.LOADED;
    this.version++;
    this.domainEvents.add(new PluginRegistryDiscoverEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void loadPlugin(LoadPluginCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run loadPlugin when aggregate is terminal");
    this.status = PluginRegistryStatus.STARTED;
    this.version++;
    this.domainEvents.add(new PluginRegistryLoadPluginEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void startPlugin(StartPluginCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run startPlugin when aggregate is terminal");
    this.status = PluginRegistryStatus.STOPPED;
    this.version++;
    this.domainEvents.add(new PluginRegistryStartPluginEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void unloadPlugin(UnloadPluginCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run unloadPlugin when aggregate is terminal");
    this.status = PluginRegistryStatus.FAILED;
    this.version++;
    this.domainEvents.add(new PluginRegistryUnloadPluginEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == PluginRegistryStatus.UNLOADED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class PluginRegistryService {
    private final PluginRegistryRepository repository;
    private final PluginRegistryPolicy policy;
    private final Outbox outbox;

    PluginRegistryService(PluginRegistryRepository repository, PluginRegistryPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(PluginRegistryCommand command) {
        PluginRegistry aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("PluginRegistry not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof DiscoverCommand c) aggregate.discover(c);
        if (command instanceof LoadPluginCommand c) aggregate.loadPlugin(c);
        if (command instanceof StartPluginCommand c) aggregate.startPlugin(c);
        if (command instanceof UnloadPluginCommand c) aggregate.unloadPlugin(c);
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

- Persist `PluginRegistry` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `PluginRegistry` invariants and each command method.
- State-machine test all valid and invalid `PluginRegistryStatus` transitions.
- Contract test every `PluginRegistryRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `PluginRegistry` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `PluginRegistryService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
