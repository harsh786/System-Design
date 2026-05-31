# 064. Design Feature Flag SDK

Source problem: `Design feature flag SDK.`  
Category: `Platform SDK`  
Primary focus: `local cache, targeting rules, rollout, fallback`  
Archetype: `platform-library`

## 1. Interview Framing

Design `feature flag SDK` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `feature flag SDK` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `BOOTSTRAPPING, READY, EVALUATING, STALE, OFFLINE`.
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
- `FlagAdmin`
- `ConfigService`

Primary use cases:

- `loadSnapshot` command on `FeatureFlagSDK`
- `evaluateFlag` command on `FeatureFlagSDK`
- `refreshFlags` command on `FeatureFlagSDK`
- `applyFallback` command on `FeatureFlagSDK`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `FeatureFlagSDK` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `FlagDefinition, TargetingRule, EvaluationContext, Rollout, FlagSnapshot` | Have identity and change over time under the aggregate. |
| Value objects | `FlagKey, UserKey, Percentage, Version` | Immutable concepts compared by value. |
| Policies | `FeatureFlagSDKPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `FeatureFlagSDKRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
BOOTSTRAPPING, READY, EVALUATING, STALE, OFFLINE, CLOSED
```

Invariants:

- `FeatureFlagSDK` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `FeatureFlagSDKService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `FeatureFlagSDK` | Composes | FlagDefinition, TargetingRule, EvaluationContext | Owns invariants and lifecycle transitions. |
| `FeatureFlagSDKRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `FeatureFlagSDKPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Lock/atomic primitive | Protects | Shared mutable state | Documents thread-safety and prevents race conditions. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class FeatureFlagSDK {
  +UUID id
  +FeatureFlagSDKStatus status
  +long version
  +validateInvariants()
}
class FeatureFlagSDKService {
  +handle(command)
}
class FeatureFlagSDKRepository {
  <<interface>>
  +findById(UUID id) FeatureFlagSDK
  +save(FeatureFlagSDK aggregate, long expectedVersion)
}
class FeatureFlagSDKPolicy {
  <<interface>>
  +evaluate(context) Decision
}
FeatureFlagSDKService --> FeatureFlagSDKRepository
FeatureFlagSDKService --> FeatureFlagSDKPolicy
FeatureFlagSDKService --> FeatureFlagSDK
class FlagDefinition {
  +UUID id
  +validate()
}
FeatureFlagSDK "1" o-- "many" FlagDefinition
class TargetingRule {
  +UUID id
  +validate()
}
FeatureFlagSDK "1" o-- "many" TargetingRule
class EvaluationContext {
  +UUID id
  +validate()
}
FeatureFlagSDK "1" o-- "many" EvaluationContext
class Rollout {
  +UUID id
  +validate()
}
FeatureFlagSDK "1" o-- "many" Rollout
class FlagKey {
  <<value object>>
}
FeatureFlagSDK ..> FlagKey
class UserKey {
  <<value object>>
}
FeatureFlagSDK ..> UserKey
class Percentage {
  <<value object>>
}
FeatureFlagSDK ..> Percentage
FeatureFlagSDKPolicy <|.. DefaultFeatureFlagSDKPolicy
FeatureFlagSDKService ..> MetricsRecorder
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as FeatureFlagSDKService
participant Repo as FeatureFlagSDKRepository
participant Policy as FeatureFlagSDKPolicy
participant Agg as FeatureFlagSDK
participant Outbox
Client->>Service: loadSnapshot(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: loadSnapshot(command)
Agg-->>Service: FeatureFlagSDKLoadSnapshotEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| Adapter | Hide vendor or infrastructure differences behind stable ports. |
| Specification | Compose business predicates and keep rule evaluation explainable. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.featureflagsdk;

import java.time.Duration;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

enum FeatureFlagSDKState {
    BOOTSTRAPPING,
    READY,
    EVALUATING,
    STALE,
    OFFLINE,
    CLOSED
}

interface FeatureFlagSDKOperation<R> {
    R run() throws Exception;
}

interface FeatureFlagSDKPolicy {
    boolean allowAttempt(int attempt, Throwable lastFailure);
    Duration delayBeforeNextAttempt(int attempt);
}

interface MetricsRecorder {
    void increment(String metricName);
    void timing(String metricName, Duration duration);
}

final class FeatureFlagSDK {
    private final AtomicReference<FeatureFlagSDKState> state = new AtomicReference<>(FeatureFlagSDKState.BOOTSTRAPPING);
    private final ScheduledExecutorService scheduler;
    private final FeatureFlagSDKPolicy policy;
    private final MetricsRecorder metrics;

    FeatureFlagSDK(ScheduledExecutorService scheduler, FeatureFlagSDKPolicy policy, MetricsRecorder metrics) {
        this.scheduler = Objects.requireNonNull(scheduler);
        this.policy = Objects.requireNonNull(policy);
        this.metrics = Objects.requireNonNull(metrics);
    }

    public <R> CompletableFuture<R> execute(FeatureFlagSDKOperation<R> operation) {
        if (isClosed()) return CompletableFuture.failedFuture(new IllegalStateException("FeatureFlagSDK is closed"));
        CompletableFuture<R> result = new CompletableFuture<>();
        executeAttempt(operation, result, 1, null);
        return result;
    }

    private <R> void executeAttempt(FeatureFlagSDKOperation<R> operation, CompletableFuture<R> result, int attempt, Throwable lastFailure) {
        scheduler.execute(() -> {
            try {
                state.set(FeatureFlagSDKState.READY);
                R value = operation.run();
                metrics.increment("feature-flag-sdk.success");
                result.complete(value);
            } catch (Throwable failure) {
                metrics.increment("feature-flag-sdk.failure");
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
        state.set(FeatureFlagSDKState.CLOSED);
        scheduler.shutdown();
    }

    private boolean isClosed() {
        return state.get() == FeatureFlagSDKState.CLOSED;
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
| Hide vendor or infrastructure differences behind stable ports. | `Adapter` |
| Compose business predicates and keep rule evaluation explainable. | `Specification` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `FeatureFlagSDK` invariants and each command method.
- State-machine test all valid and invalid `FeatureFlagSDKStatus` transitions.
- Contract test every `FeatureFlagSDKRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `FeatureFlagSDK` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `FeatureFlagSDKService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
