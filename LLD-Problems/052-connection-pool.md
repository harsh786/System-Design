# 052. Design Connection Pool

Source problem: `Design connection pool.`  
Category: `Resource management`  
Primary focus: `health checks, leasing, timeout, leak detection`  
Archetype: `platform-library`

## 1. Interview Framing

Design `connection pool` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `connection pool` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `IDLE, LEASED, VALIDATING, EVICTING, CLOSED`.
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

- `Client`
- `ConnectionFactory`
- `HealthChecker`

Primary use cases:

- `borrow` command on `ConnectionPool`
- `returnConnection` command on `ConnectionPool`
- `validateConnection` command on `ConnectionPool`
- `evictIdle` command on `ConnectionPool`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `ConnectionPool` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Connection, Lease, PoolConfig, HealthProbe` | Have identity and change over time under the aggregate. |
| Value objects | `ConnectionId, Timeout, Capacity, Endpoint` | Immutable concepts compared by value. |
| Policies | `ConnectionPoolPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `ConnectionPoolRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
IDLE, LEASED, VALIDATING, EVICTING, CLOSED
```

Invariants:

- `ConnectionPool` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `ConnectionPoolService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `ConnectionPool` | Composes | Connection, Lease, PoolConfig | Owns invariants and lifecycle transitions. |
| `ConnectionPoolRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `ConnectionPoolPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Lock/atomic primitive | Protects | Shared mutable state | Documents thread-safety and prevents race conditions. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class ConnectionPool {
  +UUID id
  +ConnectionPoolStatus status
  +long version
  +validateInvariants()
}
class ConnectionPoolService {
  +handle(command)
}
class ConnectionPoolRepository {
  <<interface>>
  +findById(UUID id) ConnectionPool
  +save(ConnectionPool aggregate, long expectedVersion)
}
class ConnectionPoolPolicy {
  <<interface>>
  +evaluate(context) Decision
}
ConnectionPoolService --> ConnectionPoolRepository
ConnectionPoolService --> ConnectionPoolPolicy
ConnectionPoolService --> ConnectionPool
class Connection {
  +UUID id
  +validate()
}
ConnectionPool "1" o-- "many" Connection
class Lease {
  +UUID id
  +validate()
}
ConnectionPool "1" o-- "many" Lease
class PoolConfig {
  +UUID id
  +validate()
}
ConnectionPool "1" o-- "many" PoolConfig
class HealthProbe {
  +UUID id
  +validate()
}
ConnectionPool "1" o-- "many" HealthProbe
class ConnectionId {
  <<value object>>
}
ConnectionPool ..> ConnectionId
class Timeout {
  <<value object>>
}
ConnectionPool ..> Timeout
class Capacity {
  <<value object>>
}
ConnectionPool ..> Capacity
ConnectionPoolPolicy <|.. DefaultConnectionPoolPolicy
ConnectionPoolService ..> MetricsRecorder
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as ConnectionPoolService
participant Repo as ConnectionPoolRepository
participant Policy as ConnectionPoolPolicy
participant Agg as ConnectionPool
participant Outbox
Client->>Service: borrow(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: borrow(command)
Agg-->>Service: ConnectionPoolBorrowEvent
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
package lld.connectionpool;

import java.time.Duration;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

enum ConnectionPoolState {
    IDLE,
    LEASED,
    VALIDATING,
    EVICTING,
    CLOSED
}

interface ConnectionPoolOperation<R> {
    R run() throws Exception;
}

interface ConnectionPoolPolicy {
    boolean allowAttempt(int attempt, Throwable lastFailure);
    Duration delayBeforeNextAttempt(int attempt);
}

interface MetricsRecorder {
    void increment(String metricName);
    void timing(String metricName, Duration duration);
}

final class ConnectionPool {
    private final AtomicReference<ConnectionPoolState> state = new AtomicReference<>(ConnectionPoolState.IDLE);
    private final ScheduledExecutorService scheduler;
    private final ConnectionPoolPolicy policy;
    private final MetricsRecorder metrics;

    ConnectionPool(ScheduledExecutorService scheduler, ConnectionPoolPolicy policy, MetricsRecorder metrics) {
        this.scheduler = Objects.requireNonNull(scheduler);
        this.policy = Objects.requireNonNull(policy);
        this.metrics = Objects.requireNonNull(metrics);
    }

    public <R> CompletableFuture<R> execute(ConnectionPoolOperation<R> operation) {
        if (isClosed()) return CompletableFuture.failedFuture(new IllegalStateException("ConnectionPool is closed"));
        CompletableFuture<R> result = new CompletableFuture<>();
        executeAttempt(operation, result, 1, null);
        return result;
    }

    private <R> void executeAttempt(ConnectionPoolOperation<R> operation, CompletableFuture<R> result, int attempt, Throwable lastFailure) {
        scheduler.execute(() -> {
            try {
                state.set(ConnectionPoolState.LEASED);
                R value = operation.run();
                metrics.increment("connection-pool.success");
                result.complete(value);
            } catch (Throwable failure) {
                metrics.increment("connection-pool.failure");
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
        state.set(ConnectionPoolState.CLOSED);
        scheduler.shutdown();
    }

    private boolean isClosed() {
        return state.get() == ConnectionPoolState.CLOSED;
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

- Unit test `ConnectionPool` invariants and each command method.
- State-machine test all valid and invalid `ConnectionPoolStatus` transitions.
- Contract test every `ConnectionPoolRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `ConnectionPool` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `ConnectionPoolService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
