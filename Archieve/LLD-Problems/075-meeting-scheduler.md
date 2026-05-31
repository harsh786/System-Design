# 075. Design Meeting Scheduler

Source problem: `Design meeting scheduler.`  
Category: `Productivity`  
Primary focus: `availability, ranking slots, constraints, invites`  
Archetype: `booking`

## 1. Interview Framing

Design `meeting scheduler` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `meeting scheduler` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `COLLECTING_AVAILABILITY, RANKING, PROPOSED, CONFIRMED, CANCELLED`.
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

- `Organizer`
- `Participant`
- `RoomProvider`

Primary use cases:

- `collectAvailability` command on `MeetingScheduler`
- `rankSlots` command on `MeetingScheduler`
- `proposeSlot` command on `MeetingScheduler`
- `confirmMeeting` command on `MeetingScheduler`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `MeetingScheduler` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `MeetingRequest, AvailabilityWindow, CandidateSlot, Invite, RankingPolicy` | Have identity and change over time under the aggregate. |
| Value objects | `DateRange, TimeZone, ParticipantId, Score` | Immutable concepts compared by value. |
| Policies | `MeetingSchedulerPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `MeetingSchedulerRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
COLLECTING_AVAILABILITY, RANKING, PROPOSED, CONFIRMED, CANCELLED
```

Invariants:

- `MeetingScheduler` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.
- Money and capacity changes are atomic within the transaction boundary.
- A repeated idempotency key returns the original result and never double-applies side effects.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `MeetingSchedulerService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `MeetingScheduler` | Composes | MeetingRequest, AvailabilityWindow, CandidateSlot | Owns invariants and lifecycle transitions. |
| `MeetingSchedulerRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `MeetingSchedulerPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class MeetingScheduler {
  +UUID id
  +MeetingSchedulerStatus status
  +long version
  +validateInvariants()
}
class MeetingSchedulerService {
  +handle(command)
}
class MeetingSchedulerRepository {
  <<interface>>
  +findById(UUID id) MeetingScheduler
  +save(MeetingScheduler aggregate, long expectedVersion)
}
class MeetingSchedulerPolicy {
  <<interface>>
  +evaluate(context) Decision
}
MeetingSchedulerService --> MeetingSchedulerRepository
MeetingSchedulerService --> MeetingSchedulerPolicy
MeetingSchedulerService --> MeetingScheduler
class MeetingRequest {
  +UUID id
  +validate()
}
MeetingScheduler "1" o-- "many" MeetingRequest
class AvailabilityWindow {
  +UUID id
  +validate()
}
MeetingScheduler "1" o-- "many" AvailabilityWindow
class CandidateSlot {
  +UUID id
  +validate()
}
MeetingScheduler "1" o-- "many" CandidateSlot
class Invite {
  +UUID id
  +validate()
}
MeetingScheduler "1" o-- "many" Invite
class DateRange {
  <<value object>>
}
MeetingScheduler ..> DateRange
class TimeZone {
  <<value object>>
}
MeetingScheduler ..> TimeZone
class ParticipantId {
  <<value object>>
}
MeetingScheduler ..> ParticipantId
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as MeetingSchedulerService
participant Repo as MeetingSchedulerRepository
participant Policy as MeetingSchedulerPolicy
participant Agg as MeetingScheduler
participant Outbox
Client->>Service: collectAvailability(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: collectAvailability(command)
Agg-->>Service: MeetingSchedulerCollectAvailabilityEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |
| Strategy | Swap algorithms such as pricing, ranking, scheduling, matching, or retry without changing the aggregate. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.meetingscheduler;

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

enum MeetingSchedulerStatus {
    COLLECTING_AVAILABILITY,
    RANKING,
    PROPOSED,
    CONFIRMED,
    CANCELLED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record MeetingSchedulerCollectAvailabilityEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record MeetingSchedulerRankSlotsEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record MeetingSchedulerProposeSlotEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record MeetingSchedulerConfirmMeetingEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface MeetingSchedulerCommand permits CollectAvailabilityCommand, RankSlotsCommand, ProposeSlotCommand, ConfirmMeetingCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record CollectAvailabilityCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements MeetingSchedulerCommand {}
record RankSlotsCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements MeetingSchedulerCommand {}
record ProposeSlotCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements MeetingSchedulerCommand {}
record ConfirmMeetingCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements MeetingSchedulerCommand {}

interface MeetingSchedulerRepository {
    Optional<MeetingScheduler> findById(UUID id);
    void save(MeetingScheduler aggregate, long expectedVersion);
}

interface MeetingSchedulerPolicy {
    Decision evaluate(MeetingScheduler aggregate, MeetingSchedulerCommand command);
}

final class MeetingRequest {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class MeetingScheduler {
    private final UUID id;
    private final List<MeetingRequest> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private MeetingSchedulerStatus status;
    private long version;

    MeetingScheduler(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = MeetingSchedulerStatus.COLLECTING_AVAILABILITY;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    MeetingSchedulerStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void collectAvailability(CollectAvailabilityCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run collectAvailability when aggregate is terminal");
    this.status = MeetingSchedulerStatus.RANKING;
    this.version++;
    this.domainEvents.add(new MeetingSchedulerCollectAvailabilityEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void rankSlots(RankSlotsCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run rankSlots when aggregate is terminal");
    this.status = MeetingSchedulerStatus.PROPOSED;
    this.version++;
    this.domainEvents.add(new MeetingSchedulerRankSlotsEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void proposeSlot(ProposeSlotCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run proposeSlot when aggregate is terminal");
    this.status = MeetingSchedulerStatus.CONFIRMED;
    this.version++;
    this.domainEvents.add(new MeetingSchedulerProposeSlotEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void confirmMeeting(ConfirmMeetingCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run confirmMeeting when aggregate is terminal");
    this.status = MeetingSchedulerStatus.CANCELLED;
    this.version++;
    this.domainEvents.add(new MeetingSchedulerConfirmMeetingEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == MeetingSchedulerStatus.CANCELLED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class MeetingSchedulerService {
    private final MeetingSchedulerRepository repository;
    private final MeetingSchedulerPolicy policy;
    private final Outbox outbox;

    MeetingSchedulerService(MeetingSchedulerRepository repository, MeetingSchedulerPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(MeetingSchedulerCommand command) {
        MeetingScheduler aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("MeetingScheduler not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof CollectAvailabilityCommand c) aggregate.collectAvailability(c);
        if (command instanceof RankSlotsCommand c) aggregate.rankSlots(c);
        if (command instanceof ProposeSlotCommand c) aggregate.proposeSlot(c);
        if (command instanceof ConfirmMeetingCommand c) aggregate.confirmMeeting(c);
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

- Persist `MeetingScheduler` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Swap algorithms such as pricing, ranking, scheduling, matching, or retry without changing the aggregate. | `Strategy` |
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `MeetingScheduler` invariants and each command method.
- State-machine test all valid and invalid `MeetingSchedulerStatus` transitions.
- Contract test every `MeetingSchedulerRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `MeetingScheduler` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `MeetingSchedulerService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
