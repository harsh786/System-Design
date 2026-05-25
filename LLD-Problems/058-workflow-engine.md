# 058. Design Workflow Engine

Source problem: `Design workflow engine.`  
Category: `Orchestration`  
Primary focus: `DAG/state machine, retries, compensation, persistence`  
Archetype: `platform-library`

## 1. Interview Framing

Design `workflow engine` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `workflow engine` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `CREATED, RUNNING, WAITING, COMPENSATING, COMPLETED`.
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

- `WorkflowClient`
- `Worker`
- `PersistenceStore`

Primary use cases:

- `startWorkflow` command on `WorkflowEngine`
- `completeStep` command on `WorkflowEngine`
- `retryStep` command on `WorkflowEngine`
- `compensate` command on `WorkflowEngine`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `WorkflowEngine` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `WorkflowDefinition, WorkflowInstance, Step, Transition, Compensation` | Have identity and change over time under the aggregate. |
| Value objects | `WorkflowId, StepId, RetryPolicy, Version` | Immutable concepts compared by value. |
| Policies | `WorkflowEnginePolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `WorkflowEngineRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
CREATED, RUNNING, WAITING, COMPENSATING, COMPLETED, FAILED
```

Invariants:

- `WorkflowEngine` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `WorkflowEngineService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `WorkflowEngine` | Composes | WorkflowDefinition, WorkflowInstance, Step | Owns invariants and lifecycle transitions. |
| `WorkflowEngineRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `WorkflowEnginePolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Lock/atomic primitive | Protects | Shared mutable state | Documents thread-safety and prevents race conditions. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class WorkflowEngine {
  +UUID id
  +WorkflowEngineStatus status
  +long version
  +validateInvariants()
}
class WorkflowEngineService {
  +handle(command)
}
class WorkflowEngineRepository {
  <<interface>>
  +findById(UUID id) WorkflowEngine
  +save(WorkflowEngine aggregate, long expectedVersion)
}
class WorkflowEnginePolicy {
  <<interface>>
  +evaluate(context) Decision
}
WorkflowEngineService --> WorkflowEngineRepository
WorkflowEngineService --> WorkflowEnginePolicy
WorkflowEngineService --> WorkflowEngine
class WorkflowDefinition {
  +UUID id
  +validate()
}
WorkflowEngine "1" o-- "many" WorkflowDefinition
class WorkflowInstance {
  +UUID id
  +validate()
}
WorkflowEngine "1" o-- "many" WorkflowInstance
class Step {
  +UUID id
  +validate()
}
WorkflowEngine "1" o-- "many" Step
class Transition {
  +UUID id
  +validate()
}
WorkflowEngine "1" o-- "many" Transition
class WorkflowId {
  <<value object>>
}
WorkflowEngine ..> WorkflowId
class StepId {
  <<value object>>
}
WorkflowEngine ..> StepId
class RetryPolicy {
  <<value object>>
}
WorkflowEngine ..> RetryPolicy
WorkflowEnginePolicy <|.. DefaultWorkflowEnginePolicy
WorkflowEngineService ..> MetricsRecorder
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as WorkflowEngineService
participant Repo as WorkflowEngineRepository
participant Policy as WorkflowEnginePolicy
participant Agg as WorkflowEngine
participant Outbox
Client->>Service: startWorkflow(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: startWorkflow(command)
Agg-->>Service: WorkflowEngineStartWorkflowEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |
| Adapter | Hide vendor or infrastructure differences behind stable ports. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |
| Saga / Process Manager | Coordinate multi-step workflows and compensation across payment, inventory, delivery, or approvals. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.workflowengine;

import java.time.Duration;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

enum WorkflowEngineState {
    CREATED,
    RUNNING,
    WAITING,
    COMPENSATING,
    COMPLETED,
    FAILED
}

interface WorkflowEngineOperation<R> {
    R run() throws Exception;
}

interface WorkflowEnginePolicy {
    boolean allowAttempt(int attempt, Throwable lastFailure);
    Duration delayBeforeNextAttempt(int attempt);
}

interface MetricsRecorder {
    void increment(String metricName);
    void timing(String metricName, Duration duration);
}

final class WorkflowEngine {
    private final AtomicReference<WorkflowEngineState> state = new AtomicReference<>(WorkflowEngineState.CREATED);
    private final ScheduledExecutorService scheduler;
    private final WorkflowEnginePolicy policy;
    private final MetricsRecorder metrics;

    WorkflowEngine(ScheduledExecutorService scheduler, WorkflowEnginePolicy policy, MetricsRecorder metrics) {
        this.scheduler = Objects.requireNonNull(scheduler);
        this.policy = Objects.requireNonNull(policy);
        this.metrics = Objects.requireNonNull(metrics);
    }

    public <R> CompletableFuture<R> execute(WorkflowEngineOperation<R> operation) {
        if (isClosed()) return CompletableFuture.failedFuture(new IllegalStateException("WorkflowEngine is closed"));
        CompletableFuture<R> result = new CompletableFuture<>();
        executeAttempt(operation, result, 1, null);
        return result;
    }

    private <R> void executeAttempt(WorkflowEngineOperation<R> operation, CompletableFuture<R> result, int attempt, Throwable lastFailure) {
        scheduler.execute(() -> {
            try {
                state.set(WorkflowEngineState.RUNNING);
                R value = operation.run();
                metrics.increment("workflow-engine.success");
                result.complete(value);
            } catch (Throwable failure) {
                metrics.increment("workflow-engine.failure");
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
        state.set(WorkflowEngineState.FAILED);
        scheduler.shutdown();
    }

    private boolean isClosed() {
        return state.get() == WorkflowEngineState.FAILED;
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
| Hide vendor or infrastructure differences behind stable ports. | `Adapter` |
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| Coordinate multi-step workflows and compensation across payment, inventory, delivery, or approvals. | `Saga / Process Manager` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `WorkflowEngine` invariants and each command method.
- State-machine test all valid and invalid `WorkflowEngineStatus` transitions.
- Contract test every `WorkflowEngineRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `WorkflowEngine` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `WorkflowEngineService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
