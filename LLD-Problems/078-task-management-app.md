# 078. Design Task Management App

Source problem: `Design task management app.`  
Category: `Productivity`  
Primary focus: `projects, tasks, assignment, state transitions`  
Archetype: `state-workflow`

## 1. Interview Framing

Design `task management app` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `task management app` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `BACKLOG, TODO, IN_PROGRESS, BLOCKED, DONE`.
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

- `User`
- `Assignee`
- `ProjectAdmin`

Primary use cases:

- `createTask` command on `TaskManagementApp`
- `assignTask` command on `TaskManagementApp`
- `transitionTask` command on `TaskManagementApp`
- `addComment` command on `TaskManagementApp`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `TaskManagementApp` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Project, Task, Checklist, Comment, Assignment` | Have identity and change over time under the aggregate. |
| Value objects | `TaskId, DueDate, Priority, UserId` | Immutable concepts compared by value. |
| Policies | `TaskManagementAppPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `TaskManagementAppRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
BACKLOG, TODO, IN_PROGRESS, BLOCKED, DONE, ARCHIVED
```

Invariants:

- `TaskManagementApp` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `TaskManagementAppService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `TaskManagementApp` | Composes | Project, Task, Checklist | Owns invariants and lifecycle transitions. |
| `TaskManagementAppRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `TaskManagementAppPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class TaskManagementApp {
  +UUID id
  +TaskManagementAppStatus status
  +long version
  +validateInvariants()
}
class TaskManagementAppService {
  +handle(command)
}
class TaskManagementAppRepository {
  <<interface>>
  +findById(UUID id) TaskManagementApp
  +save(TaskManagementApp aggregate, long expectedVersion)
}
class TaskManagementAppPolicy {
  <<interface>>
  +evaluate(context) Decision
}
TaskManagementAppService --> TaskManagementAppRepository
TaskManagementAppService --> TaskManagementAppPolicy
TaskManagementAppService --> TaskManagementApp
class Project {
  +UUID id
  +validate()
}
TaskManagementApp "1" o-- "many" Project
class Task {
  +UUID id
  +validate()
}
TaskManagementApp "1" o-- "many" Task
class Checklist {
  +UUID id
  +validate()
}
TaskManagementApp "1" o-- "many" Checklist
class Comment {
  +UUID id
  +validate()
}
TaskManagementApp "1" o-- "many" Comment
class TaskId {
  <<value object>>
}
TaskManagementApp ..> TaskId
class DueDate {
  <<value object>>
}
TaskManagementApp ..> DueDate
class Priority {
  <<value object>>
}
TaskManagementApp ..> Priority
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as TaskManagementAppService
participant Repo as TaskManagementAppRepository
participant Policy as TaskManagementAppPolicy
participant Agg as TaskManagementApp
participant Outbox
Client->>Service: createTask(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: createTask(command)
Agg-->>Service: TaskManagementAppCreateTaskEvent
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
package lld.taskmanagementapp;

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

enum TaskManagementAppStatus {
    BACKLOG,
    TODO,
    IN_PROGRESS,
    BLOCKED,
    DONE,
    ARCHIVED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record TaskManagementAppCreateTaskEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record TaskManagementAppAssignTaskEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record TaskManagementAppTransitionTaskEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record TaskManagementAppAddCommentEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface TaskManagementAppCommand permits CreateTaskCommand, AssignTaskCommand, TransitionTaskCommand, AddCommentCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record CreateTaskCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements TaskManagementAppCommand {}
record AssignTaskCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements TaskManagementAppCommand {}
record TransitionTaskCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements TaskManagementAppCommand {}
record AddCommentCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements TaskManagementAppCommand {}

interface TaskManagementAppRepository {
    Optional<TaskManagementApp> findById(UUID id);
    void save(TaskManagementApp aggregate, long expectedVersion);
}

interface TaskManagementAppPolicy {
    Decision evaluate(TaskManagementApp aggregate, TaskManagementAppCommand command);
}

final class Project {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class TaskManagementApp {
    private final UUID id;
    private final List<Project> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private TaskManagementAppStatus status;
    private long version;

    TaskManagementApp(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = TaskManagementAppStatus.BACKLOG;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    TaskManagementAppStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void createTask(CreateTaskCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run createTask when aggregate is terminal");
    this.status = TaskManagementAppStatus.TODO;
    this.version++;
    this.domainEvents.add(new TaskManagementAppCreateTaskEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void assignTask(AssignTaskCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run assignTask when aggregate is terminal");
    this.status = TaskManagementAppStatus.IN_PROGRESS;
    this.version++;
    this.domainEvents.add(new TaskManagementAppAssignTaskEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void transitionTask(TransitionTaskCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run transitionTask when aggregate is terminal");
    this.status = TaskManagementAppStatus.BLOCKED;
    this.version++;
    this.domainEvents.add(new TaskManagementAppTransitionTaskEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void addComment(AddCommentCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run addComment when aggregate is terminal");
    this.status = TaskManagementAppStatus.DONE;
    this.version++;
    this.domainEvents.add(new TaskManagementAppAddCommentEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == TaskManagementAppStatus.ARCHIVED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class TaskManagementAppService {
    private final TaskManagementAppRepository repository;
    private final TaskManagementAppPolicy policy;
    private final Outbox outbox;

    TaskManagementAppService(TaskManagementAppRepository repository, TaskManagementAppPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(TaskManagementAppCommand command) {
        TaskManagementApp aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("TaskManagementApp not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof CreateTaskCommand c) aggregate.createTask(c);
        if (command instanceof AssignTaskCommand c) aggregate.assignTask(c);
        if (command instanceof TransitionTaskCommand c) aggregate.transitionTask(c);
        if (command instanceof AddCommentCommand c) aggregate.addComment(c);
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

- Persist `TaskManagementApp` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `TaskManagementApp` invariants and each command method.
- State-machine test all valid and invalid `TaskManagementAppStatus` transitions.
- Contract test every `TaskManagementAppRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `TaskManagementApp` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `TaskManagementAppService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
