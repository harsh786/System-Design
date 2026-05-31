# 068. Design Tracing SDK

Source problem: `Design tracing SDK.`  
Category: `Observability SDK`  
Primary focus: `spans, context propagation, sampling, exporters`  
Archetype: `platform-library`

## 1. Interview Framing

Design `tracing SDK` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `tracing SDK` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `SPAN_STARTED, SPAN_ENDED, SAMPLED, EXPORTED, DROPPED`.
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
- `TraceExporter`
- `Sampler`

Primary use cases:

- `startSpan` command on `TracingSDK`
- `propagateContext` command on `TracingSDK`
- `endSpan` command on `TracingSDK`
- `exportSpan` command on `TracingSDK`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `TracingSDK` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Tracer, Span, SpanContext, Sampler, Exporter` | Have identity and change over time under the aggregate. |
| Value objects | `TraceId, SpanId, Tag, Duration` | Immutable concepts compared by value. |
| Policies | `TracingSDKPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `TracingSDKRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
SPAN_STARTED, SPAN_ENDED, SAMPLED, EXPORTED, DROPPED
```

Invariants:

- `TracingSDK` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `TracingSDKService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `TracingSDK` | Composes | Tracer, Span, SpanContext | Owns invariants and lifecycle transitions. |
| `TracingSDKRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `TracingSDKPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Lock/atomic primitive | Protects | Shared mutable state | Documents thread-safety and prevents race conditions. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class TracingSDK {
  +UUID id
  +TracingSDKStatus status
  +long version
  +validateInvariants()
}
class TracingSDKService {
  +handle(command)
}
class TracingSDKRepository {
  <<interface>>
  +findById(UUID id) TracingSDK
  +save(TracingSDK aggregate, long expectedVersion)
}
class TracingSDKPolicy {
  <<interface>>
  +evaluate(context) Decision
}
TracingSDKService --> TracingSDKRepository
TracingSDKService --> TracingSDKPolicy
TracingSDKService --> TracingSDK
class Tracer {
  +UUID id
  +validate()
}
TracingSDK "1" o-- "many" Tracer
class Span {
  +UUID id
  +validate()
}
TracingSDK "1" o-- "many" Span
class SpanContext {
  +UUID id
  +validate()
}
TracingSDK "1" o-- "many" SpanContext
class Sampler {
  +UUID id
  +validate()
}
TracingSDK "1" o-- "many" Sampler
class TraceId {
  <<value object>>
}
TracingSDK ..> TraceId
class SpanId {
  <<value object>>
}
TracingSDK ..> SpanId
class Tag {
  <<value object>>
}
TracingSDK ..> Tag
TracingSDKPolicy <|.. DefaultTracingSDKPolicy
TracingSDKService ..> MetricsRecorder
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as TracingSDKService
participant Repo as TracingSDKRepository
participant Policy as TracingSDKPolicy
participant Agg as TracingSDK
participant Outbox
Client->>Service: startSpan(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: startSpan(command)
Agg-->>Service: TracingSDKStartSpanEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| Adapter | Hide vendor or infrastructure differences behind stable ports. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.tracingsdk;

import java.time.Duration;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

enum TracingSDKState {
    SPAN_STARTED,
    SPAN_ENDED,
    SAMPLED,
    EXPORTED,
    DROPPED
}

interface TracingSDKOperation<R> {
    R run() throws Exception;
}

interface TracingSDKPolicy {
    boolean allowAttempt(int attempt, Throwable lastFailure);
    Duration delayBeforeNextAttempt(int attempt);
}

interface MetricsRecorder {
    void increment(String metricName);
    void timing(String metricName, Duration duration);
}

final class TracingSDK {
    private final AtomicReference<TracingSDKState> state = new AtomicReference<>(TracingSDKState.SPAN_STARTED);
    private final ScheduledExecutorService scheduler;
    private final TracingSDKPolicy policy;
    private final MetricsRecorder metrics;

    TracingSDK(ScheduledExecutorService scheduler, TracingSDKPolicy policy, MetricsRecorder metrics) {
        this.scheduler = Objects.requireNonNull(scheduler);
        this.policy = Objects.requireNonNull(policy);
        this.metrics = Objects.requireNonNull(metrics);
    }

    public <R> CompletableFuture<R> execute(TracingSDKOperation<R> operation) {
        if (isClosed()) return CompletableFuture.failedFuture(new IllegalStateException("TracingSDK is closed"));
        CompletableFuture<R> result = new CompletableFuture<>();
        executeAttempt(operation, result, 1, null);
        return result;
    }

    private <R> void executeAttempt(TracingSDKOperation<R> operation, CompletableFuture<R> result, int attempt, Throwable lastFailure) {
        scheduler.execute(() -> {
            try {
                state.set(TracingSDKState.SPAN_ENDED);
                R value = operation.run();
                metrics.increment("tracing-sdk.success");
                result.complete(value);
            } catch (Throwable failure) {
                metrics.increment("tracing-sdk.failure");
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
        state.set(TracingSDKState.DROPPED);
        scheduler.shutdown();
    }

    private boolean isClosed() {
        return state.get() == TracingSDKState.DROPPED;
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
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `TracingSDK` invariants and each command method.
- State-machine test all valid and invalid `TracingSDKStatus` transitions.
- Contract test every `TracingSDKRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `TracingSDK` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `TracingSDKService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
