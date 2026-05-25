# 069. Design Dependency Injection Container

Source problem: `Design dependency injection container.`  
Category: `Framework`  
Primary focus: `providers, scopes, lifecycle, circular dependencies`  
Archetype: `platform-library`

## 1. Interview Framing

Design `dependency injection container` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `dependency injection container` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `BUILDING, READY, RESOLVING, FAILED, CLOSED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.
- Offer a small public API with bounded resources, back-pressure, and safe shutdown.
- Expose metrics hooks without coupling the core library to a specific observability vendor.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `Application`
- `ModuleAuthor`
- `Provider`

Primary use cases:

- `bind` command on `DependencyInjectionContainer`
- `resolve` command on `DependencyInjectionContainer`
- `createScope` command on `DependencyInjectionContainer`
- `detectCycle` command on `DependencyInjectionContainer`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `DependencyInjectionContainer` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Container, Binding, Provider, Scope, ObjectGraph` | Have identity and change over time under the aggregate. |
| Value objects | `TypeKey, ScopeName, Qualifier, Lifecycle` | Immutable concepts compared by value. |
| Policies | `DependencyInjectionContainerPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `DependencyInjectionContainerRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
BUILDING, READY, RESOLVING, FAILED, CLOSED
```

Invariants:

- `DependencyInjectionContainer` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `DependencyInjectionContainerService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `DependencyInjectionContainer` | Composes | Container, Binding, Provider | Owns invariants and lifecycle transitions. |
| `DependencyInjectionContainerRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `DependencyInjectionContainerPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Lock/atomic primitive | Protects | Shared mutable state | Documents thread-safety and prevents race conditions. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class DependencyInjectionContainer {
  +UUID id
  +DependencyInjectionContainerStatus status
  +long version
  +validateInvariants()
}
class DependencyInjectionContainerService {
  +handle(command)
}
class DependencyInjectionContainerRepository {
  <<interface>>
  +findById(UUID id) DependencyInjectionContainer
  +save(DependencyInjectionContainer aggregate, long expectedVersion)
}
class DependencyInjectionContainerPolicy {
  <<interface>>
  +evaluate(context) Decision
}
DependencyInjectionContainerService --> DependencyInjectionContainerRepository
DependencyInjectionContainerService --> DependencyInjectionContainerPolicy
DependencyInjectionContainerService --> DependencyInjectionContainer
class Container {
  +UUID id
  +validate()
}
DependencyInjectionContainer "1" o-- "many" Container
class Binding {
  +UUID id
  +validate()
}
DependencyInjectionContainer "1" o-- "many" Binding
class Provider {
  +UUID id
  +validate()
}
DependencyInjectionContainer "1" o-- "many" Provider
class Scope {
  +UUID id
  +validate()
}
DependencyInjectionContainer "1" o-- "many" Scope
class TypeKey {
  <<value object>>
}
DependencyInjectionContainer ..> TypeKey
class ScopeName {
  <<value object>>
}
DependencyInjectionContainer ..> ScopeName
class Qualifier {
  <<value object>>
}
DependencyInjectionContainer ..> Qualifier
DependencyInjectionContainerPolicy <|.. DefaultDependencyInjectionContainerPolicy
DependencyInjectionContainerService ..> MetricsRecorder
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as DependencyInjectionContainerService
participant Repo as DependencyInjectionContainerRepository
participant Policy as DependencyInjectionContainerPolicy
participant Agg as DependencyInjectionContainer
participant Outbox
Client->>Service: bind(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: bind(command)
Agg-->>Service: DependencyInjectionContainerBindEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |
| Factory / Builder | Create valid aggregates and command objects while keeping constructors small and invariant-safe. |
| Adapter | Hide vendor or infrastructure differences behind stable ports. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.dependencyinjectioncontainer;

import java.time.Duration;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

enum DependencyInjectionContainerState {
    BUILDING,
    READY,
    RESOLVING,
    FAILED,
    CLOSED
}

interface DependencyInjectionContainerOperation<R> {
    R run() throws Exception;
}

interface DependencyInjectionContainerPolicy {
    boolean allowAttempt(int attempt, Throwable lastFailure);
    Duration delayBeforeNextAttempt(int attempt);
}

interface MetricsRecorder {
    void increment(String metricName);
    void timing(String metricName, Duration duration);
}

final class DependencyInjectionContainer {
    private final AtomicReference<DependencyInjectionContainerState> state = new AtomicReference<>(DependencyInjectionContainerState.BUILDING);
    private final ScheduledExecutorService scheduler;
    private final DependencyInjectionContainerPolicy policy;
    private final MetricsRecorder metrics;

    DependencyInjectionContainer(ScheduledExecutorService scheduler, DependencyInjectionContainerPolicy policy, MetricsRecorder metrics) {
        this.scheduler = Objects.requireNonNull(scheduler);
        this.policy = Objects.requireNonNull(policy);
        this.metrics = Objects.requireNonNull(metrics);
    }

    public <R> CompletableFuture<R> execute(DependencyInjectionContainerOperation<R> operation) {
        if (isClosed()) return CompletableFuture.failedFuture(new IllegalStateException("DependencyInjectionContainer is closed"));
        CompletableFuture<R> result = new CompletableFuture<>();
        executeAttempt(operation, result, 1, null);
        return result;
    }

    private <R> void executeAttempt(DependencyInjectionContainerOperation<R> operation, CompletableFuture<R> result, int attempt, Throwable lastFailure) {
        scheduler.execute(() -> {
            try {
                state.set(DependencyInjectionContainerState.READY);
                R value = operation.run();
                metrics.increment("dependency-injection-container.success");
                result.complete(value);
            } catch (Throwable failure) {
                metrics.increment("dependency-injection-container.failure");
                if (!policy.allowAttempt(attempt, failure)) {
                    result.completeExceptionally(failure);
                    return;
                }
                Duration delay = policy.delayBeforeNextAttempt(attempt);
                scheduler.schedule(
                        () -> executeAttempt(operation, result, attempt + 1, failure),
                        delay.toMillis(),
                        TimeUnit.MILLISECONDS
                );
            }
        });
    }

    public void close() {
        state.set(DependencyInjectionContainerState.CLOSED);
        scheduler.shutdown();
    }

    private boolean isClosed() {
        return state.get() == DependencyInjectionContainerState.CLOSED;
    }
}
```

## 11. Concurrency And Thread Safety

- Bound queues, pools, buffers, and retry attempts to avoid unbounded memory growth.
- Use explicit lifecycle states for start, drain, shutdown, and closed operations.
- Protect shared mutable state with locks/atomics and document which APIs are thread-safe.
- Prefer listener/event callbacks for asynchronous completion instead of blocking client threads.

## 12. Persistence And Transactions

- Keep runtime state in memory by default; persist only jobs, leases, offsets, or workflow state that must survive restart.
- Store idempotency keys, delivery receipts, or execution records where retries cross process boundaries.
- Use repository interfaces so embedded, SQL, Redis, or remote stores can be swapped.

## 13. Error Handling And Idempotency

- Return typed domain errors: `NotFound`, `InvalidState`, `PolicyRejected`, `Conflict`, and `DuplicateCommand`.
- Never partially mutate aggregate state before all guards pass.
- Log rejection reasons with correlation id; avoid logging secrets, tokens, or sensitive payloads.
- Use idempotency records for externally retried commands and provider callbacks.
- Expose caller-visible failure modes such as timeout, rejected execution, open circuit, or closed client.

## 14. Extensibility Hooks

| Change point | Extension mechanism |
|---|---|
| Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. | `State` |
| Create valid aggregates and command objects while keeping constructors small and invariant-safe. | `Factory / Builder` |
| Hide vendor or infrastructure differences behind stable ports. | `Adapter` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `DependencyInjectionContainer` invariants and each command method.
- State-machine test all valid and invalid `DependencyInjectionContainerStatus` transitions.
- Contract test every `DependencyInjectionContainerRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `DependencyInjectionContainer` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `DependencyInjectionContainerService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
