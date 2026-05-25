# 074. Design Calendar Application

Source problem: `Design calendar application.`  
Category: `Productivity`  
Primary focus: `events, recurrence, conflict detection, time zones`  
Archetype: `domain`

## 1. Interview Framing

Design `calendar application` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `calendar application` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `DRAFT, SCHEDULED, UPDATED, CANCELLED, REMINDER_SENT`.
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
- `CalendarProvider`
- `Invitee`

Primary use cases:

- `createEvent` command on `CalendarApplication`
- `updateEvent` command on `CalendarApplication`
- `expandRecurrence` command on `CalendarApplication`
- `sendInvite` command on `CalendarApplication`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `CalendarApplication` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Calendar, Event, RecurrenceRule, Invite, Reminder` | Have identity and change over time under the aggregate. |
| Value objects | `DateRange, TimeZone, ParticipantId, Location` | Immutable concepts compared by value. |
| Policies | `CalendarApplicationPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `CalendarApplicationRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
DRAFT, SCHEDULED, UPDATED, CANCELLED, REMINDER_SENT
```

Invariants:

- `CalendarApplication` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `CalendarApplicationService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `CalendarApplication` | Composes | Calendar, Event, RecurrenceRule | Owns invariants and lifecycle transitions. |
| `CalendarApplicationRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `CalendarApplicationPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class CalendarApplication {
  +UUID id
  +CalendarApplicationStatus status
  +long version
  +validateInvariants()
}
class CalendarApplicationService {
  +handle(command)
}
class CalendarApplicationRepository {
  <<interface>>
  +findById(UUID id) CalendarApplication
  +save(CalendarApplication aggregate, long expectedVersion)
}
class CalendarApplicationPolicy {
  <<interface>>
  +evaluate(context) Decision
}
CalendarApplicationService --> CalendarApplicationRepository
CalendarApplicationService --> CalendarApplicationPolicy
CalendarApplicationService --> CalendarApplication
class Calendar {
  +UUID id
  +validate()
}
CalendarApplication "1" o-- "many" Calendar
class Event {
  +UUID id
  +validate()
}
CalendarApplication "1" o-- "many" Event
class RecurrenceRule {
  +UUID id
  +validate()
}
CalendarApplication "1" o-- "many" RecurrenceRule
class Invite {
  +UUID id
  +validate()
}
CalendarApplication "1" o-- "many" Invite
class DateRange {
  <<value object>>
}
CalendarApplication ..> DateRange
class TimeZone {
  <<value object>>
}
CalendarApplication ..> TimeZone
class ParticipantId {
  <<value object>>
}
CalendarApplication ..> ParticipantId
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as CalendarApplicationService
participant Repo as CalendarApplicationRepository
participant Policy as CalendarApplicationPolicy
participant Agg as CalendarApplication
participant Outbox
Client->>Service: createEvent(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: createEvent(command)
Agg-->>Service: CalendarApplicationCreateEventEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| Observer / Domain Events | Emit facts after state changes so subscribers can update read models or send notifications. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.calendarapplication;

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

enum CalendarApplicationStatus {
    DRAFT,
    SCHEDULED,
    UPDATED,
    CANCELLED,
    REMINDER_SENT
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record CalendarApplicationCreateEventEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record CalendarApplicationUpdateEventEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record CalendarApplicationExpandRecurrenceEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record CalendarApplicationSendInviteEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface CalendarApplicationCommand permits CreateEventCommand, UpdateEventCommand, ExpandRecurrenceCommand, SendInviteCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record CreateEventCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CalendarApplicationCommand {}
record UpdateEventCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CalendarApplicationCommand {}
record ExpandRecurrenceCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CalendarApplicationCommand {}
record SendInviteCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements CalendarApplicationCommand {}

interface CalendarApplicationRepository {
    Optional<CalendarApplication> findById(UUID id);
    void save(CalendarApplication aggregate, long expectedVersion);
}

interface CalendarApplicationPolicy {
    Decision evaluate(CalendarApplication aggregate, CalendarApplicationCommand command);
}

final class Calendar {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class CalendarApplication {
    private final UUID id;
    private final List<Calendar> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private CalendarApplicationStatus status;
    private long version;

    CalendarApplication(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = CalendarApplicationStatus.DRAFT;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    CalendarApplicationStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void createEvent(CreateEventCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run createEvent when aggregate is terminal");
    this.status = CalendarApplicationStatus.SCHEDULED;
    this.version++;
    this.domainEvents.add(new CalendarApplicationCreateEventEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void updateEvent(UpdateEventCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run updateEvent when aggregate is terminal");
    this.status = CalendarApplicationStatus.UPDATED;
    this.version++;
    this.domainEvents.add(new CalendarApplicationUpdateEventEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void expandRecurrence(ExpandRecurrenceCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run expandRecurrence when aggregate is terminal");
    this.status = CalendarApplicationStatus.CANCELLED;
    this.version++;
    this.domainEvents.add(new CalendarApplicationExpandRecurrenceEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void sendInvite(SendInviteCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run sendInvite when aggregate is terminal");
    this.status = CalendarApplicationStatus.REMINDER_SENT;
    this.version++;
    this.domainEvents.add(new CalendarApplicationSendInviteEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == CalendarApplicationStatus.REMINDER_SENT;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class CalendarApplicationService {
    private final CalendarApplicationRepository repository;
    private final CalendarApplicationPolicy policy;
    private final Outbox outbox;

    CalendarApplicationService(CalendarApplicationRepository repository, CalendarApplicationPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(CalendarApplicationCommand command) {
        CalendarApplication aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("CalendarApplication not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof CreateEventCommand c) aggregate.createEvent(c);
        if (command instanceof UpdateEventCommand c) aggregate.updateEvent(c);
        if (command instanceof ExpandRecurrenceCommand c) aggregate.expandRecurrence(c);
        if (command instanceof SendInviteCommand c) aggregate.sendInvite(c);
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

- Persist `CalendarApplication` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Emit facts after state changes so subscribers can update read models or send notifications. | `Observer / Domain Events` |
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `CalendarApplication` invariants and each command method.
- State-machine test all valid and invalid `CalendarApplicationStatus` transitions.
- Contract test every `CalendarApplicationRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `CalendarApplication` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `CalendarApplicationService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
