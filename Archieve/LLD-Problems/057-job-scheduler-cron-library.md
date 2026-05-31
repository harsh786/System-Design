# 057. Design Job Scheduler / Cron Library

Source problem: `Design job scheduler / cron library.`  
Category: `Scheduling`  
Primary focus: `recurring jobs, misfires, locks, persistence`  
Archetype: `platform-library`

## 1. Interview Framing

Design `job scheduler cron library` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `job scheduler cron library` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `SCHEDULED, DUE, RUNNING, SUCCEEDED, FAILED`.
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

- `SchedulerClient`
- `Worker`
- `Clock`

Primary use cases:

- `schedule` command on `JobSchedulerCronLibrary`
- `triggerDueJobs` command on `JobSchedulerCronLibrary`
- `recordExecution` command on `JobSchedulerCronLibrary`
- `handleMisfire` command on `JobSchedulerCronLibrary`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `JobSchedulerCronLibrary` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `CronJob, Trigger, Execution, LockRecord` | Have identity and change over time under the aggregate. |
| Value objects | `CronExpression, RunAt, JobId, MisfirePolicy` | Immutable concepts compared by value. |
| Policies | `JobSchedulerCronLibraryPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `JobSchedulerCronLibraryRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
SCHEDULED, DUE, RUNNING, SUCCEEDED, FAILED, MISFIRED
```

Invariants:

- `JobSchedulerCronLibrary` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `JobSchedulerCronLibraryService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `JobSchedulerCronLibrary` | Composes | CronJob, Trigger, Execution | Owns invariants and lifecycle transitions. |
| `JobSchedulerCronLibraryRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `JobSchedulerCronLibraryPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Lock/atomic primitive | Protects | Shared mutable state | Documents thread-safety and prevents race conditions. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class JobSchedulerCronLibrary {
  +UUID id
  +JobSchedulerCronLibraryStatus status
  +long version
  +validateInvariants()
}
class JobSchedulerCronLibraryService {
  +handle(command)
}
class JobSchedulerCronLibraryRepository {
  <<interface>>
  +findById(UUID id) JobSchedulerCronLibrary
  +save(JobSchedulerCronLibrary aggregate, long expectedVersion)
}
class JobSchedulerCronLibraryPolicy {
  <<interface>>
  +evaluate(context) Decision
}
JobSchedulerCronLibraryService --> JobSchedulerCronLibraryRepository
JobSchedulerCronLibraryService --> JobSchedulerCronLibraryPolicy
JobSchedulerCronLibraryService --> JobSchedulerCronLibrary
class CronJob {
  +UUID id
  +validate()
}
JobSchedulerCronLibrary "1" o-- "many" CronJob
class Trigger {
  +UUID id
  +validate()
}
JobSchedulerCronLibrary "1" o-- "many" Trigger
class Execution {
  +UUID id
  +validate()
}
JobSchedulerCronLibrary "1" o-- "many" Execution
class LockRecord {
  +UUID id
  +validate()
}
JobSchedulerCronLibrary "1" o-- "many" LockRecord
class CronExpression {
  <<value object>>
}
JobSchedulerCronLibrary ..> CronExpression
class RunAt {
  <<value object>>
}
JobSchedulerCronLibrary ..> RunAt
class JobId {
  <<value object>>
}
JobSchedulerCronLibrary ..> JobId
JobSchedulerCronLibraryPolicy <|.. DefaultJobSchedulerCronLibraryPolicy
JobSchedulerCronLibraryService ..> MetricsRecorder
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as JobSchedulerCronLibraryService
participant Repo as JobSchedulerCronLibraryRepository
participant Policy as JobSchedulerCronLibraryPolicy
participant Agg as JobSchedulerCronLibrary
participant Outbox
Client->>Service: schedule(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: schedule(command)
Agg-->>Service: JobSchedulerCronLibraryScheduleEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| Command | Represent user or system intent as retryable, auditable, and optionally undoable objects. |
| Adapter | Hide vendor or infrastructure differences behind stable ports. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.jobschedulercronlibrary;

import java.time.Duration;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

enum JobSchedulerCronLibraryState {
    SCHEDULED,
    DUE,
    RUNNING,
    SUCCEEDED,
    FAILED,
    MISFIRED
}

interface JobSchedulerCronLibraryOperation<R> {
    R run() throws Exception;
}

interface JobSchedulerCronLibraryPolicy {
    boolean allowAttempt(int attempt, Throwable lastFailure);
    Duration delayBeforeNextAttempt(int attempt);
}

interface MetricsRecorder {
    void increment(String metricName);
    void timing(String metricName, Duration duration);
}

final class JobSchedulerCronLibrary {
    private final AtomicReference<JobSchedulerCronLibraryState> state = new AtomicReference<>(JobSchedulerCronLibraryState.SCHEDULED);
    private final ScheduledExecutorService scheduler;
    private final JobSchedulerCronLibraryPolicy policy;
    private final MetricsRecorder metrics;

    JobSchedulerCronLibrary(ScheduledExecutorService scheduler, JobSchedulerCronLibraryPolicy policy, MetricsRecorder metrics) {
        this.scheduler = Objects.requireNonNull(scheduler);
        this.policy = Objects.requireNonNull(policy);
        this.metrics = Objects.requireNonNull(metrics);
    }

    public <R> CompletableFuture<R> execute(JobSchedulerCronLibraryOperation<R> operation) {
        if (isClosed()) return CompletableFuture.failedFuture(new IllegalStateException("JobSchedulerCronLibrary is closed"));
        CompletableFuture<R> result = new CompletableFuture<>();
        executeAttempt(operation, result, 1, null);
        return result;
    }

    private <R> void executeAttempt(JobSchedulerCronLibraryOperation<R> operation, CompletableFuture<R> result, int attempt, Throwable lastFailure) {
        scheduler.execute(() -> {
            try {
                state.set(JobSchedulerCronLibraryState.DUE);
                R value = operation.run();
                metrics.increment("job-scheduler-cron-library.success");
                result.complete(value);
            } catch (Throwable failure) {
                metrics.increment("job-scheduler-cron-library.failure");
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
        state.set(JobSchedulerCronLibraryState.MISFIRED);
        scheduler.shutdown();
    }

    private boolean isClosed() {
        return state.get() == JobSchedulerCronLibraryState.MISFIRED;
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
| Represent user or system intent as retryable, auditable, and optionally undoable objects. | `Command` |
| Hide vendor or infrastructure differences behind stable ports. | `Adapter` |
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `JobSchedulerCronLibrary` invariants and each command method.
- State-machine test all valid and invalid `JobSchedulerCronLibraryStatus` transitions.
- Contract test every `JobSchedulerCronLibraryRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `JobSchedulerCronLibrary` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `JobSchedulerCronLibraryService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
