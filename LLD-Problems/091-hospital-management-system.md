# 091. Design Hospital Management System

Source problem: `Design hospital management system.`  
Category: `Healthcare`  
Primary focus: `patients, doctors, appointments, billing, privacy`  
Archetype: `domain`

## 1. Interview Framing

Design `hospital management system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `hospital management system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `REGISTERED, SCHEDULED, IN_TREATMENT, DISCHARGED, BILLED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `Patient`
- `Doctor`
- `Receptionist`
- `BillingService`

Primary use cases:

- `registerPatient` command on `HospitalManagementSystem`
- `scheduleAppointment` command on `HospitalManagementSystem`
- `recordTreatment` command on `HospitalManagementSystem`
- `generateBill` command on `HospitalManagementSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `HospitalManagementSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `PatientRecord, Doctor, Appointment, Treatment, Bill` | Have identity and change over time under the aggregate. |
| Value objects | `PatientId, DoctorId, DateRange, Money` | Immutable concepts compared by value. |
| Policies | `HospitalManagementSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `HospitalManagementSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
REGISTERED, SCHEDULED, IN_TREATMENT, DISCHARGED, BILLED, ARCHIVED
```

Invariants:

- `HospitalManagementSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `HospitalManagementSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `HospitalManagementSystem` | Composes | PatientRecord, Doctor, Appointment | Owns invariants and lifecycle transitions. |
| `HospitalManagementSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `HospitalManagementSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class HospitalManagementSystem {
  +UUID id
  +HospitalManagementSystemStatus status
  +long version
  +validateInvariants()
}
class HospitalManagementSystemService {
  +handle(command)
}
class HospitalManagementSystemRepository {
  <<interface>>
  +findById(UUID id) HospitalManagementSystem
  +save(HospitalManagementSystem aggregate, long expectedVersion)
}
class HospitalManagementSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
HospitalManagementSystemService --> HospitalManagementSystemRepository
HospitalManagementSystemService --> HospitalManagementSystemPolicy
HospitalManagementSystemService --> HospitalManagementSystem
class PatientRecord {
  +UUID id
  +validate()
}
HospitalManagementSystem "1" o-- "many" PatientRecord
class Doctor {
  +UUID id
  +validate()
}
HospitalManagementSystem "1" o-- "many" Doctor
class Appointment {
  +UUID id
  +validate()
}
HospitalManagementSystem "1" o-- "many" Appointment
class Treatment {
  +UUID id
  +validate()
}
HospitalManagementSystem "1" o-- "many" Treatment
class PatientId {
  <<value object>>
}
HospitalManagementSystem ..> PatientId
class DoctorId {
  <<value object>>
}
HospitalManagementSystem ..> DoctorId
class DateRange {
  <<value object>>
}
HospitalManagementSystem ..> DateRange
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as HospitalManagementSystemService
participant Repo as HospitalManagementSystemRepository
participant Policy as HospitalManagementSystemPolicy
participant Agg as HospitalManagementSystem
participant Outbox
Client->>Service: registerPatient(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: registerPatient(command)
Agg-->>Service: HospitalManagementSystemRegisterPatientEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.hospitalmanagementsystem;

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

enum HospitalManagementSystemStatus {
    REGISTERED,
    SCHEDULED,
    IN_TREATMENT,
    DISCHARGED,
    BILLED,
    ARCHIVED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record HospitalManagementSystemRegisterPatientEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record HospitalManagementSystemScheduleAppointmentEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record HospitalManagementSystemRecordTreatmentEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record HospitalManagementSystemGenerateBillEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface HospitalManagementSystemCommand permits RegisterPatientCommand, ScheduleAppointmentCommand, RecordTreatmentCommand, GenerateBillCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record RegisterPatientCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements HospitalManagementSystemCommand {}
record ScheduleAppointmentCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements HospitalManagementSystemCommand {}
record RecordTreatmentCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements HospitalManagementSystemCommand {}
record GenerateBillCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements HospitalManagementSystemCommand {}

interface HospitalManagementSystemRepository {
    Optional<HospitalManagementSystem> findById(UUID id);
    void save(HospitalManagementSystem aggregate, long expectedVersion);
}

interface HospitalManagementSystemPolicy {
    Decision evaluate(HospitalManagementSystem aggregate, HospitalManagementSystemCommand command);
}

final class PatientRecord {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class HospitalManagementSystem {
    private final UUID id;
    private final List<PatientRecord> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private HospitalManagementSystemStatus status;
    private long version;

    HospitalManagementSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = HospitalManagementSystemStatus.REGISTERED;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    HospitalManagementSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void registerPatient(RegisterPatientCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run registerPatient when aggregate is terminal");
    this.status = HospitalManagementSystemStatus.SCHEDULED;
    this.version++;
    this.domainEvents.add(new HospitalManagementSystemRegisterPatientEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void scheduleAppointment(ScheduleAppointmentCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run scheduleAppointment when aggregate is terminal");
    this.status = HospitalManagementSystemStatus.IN_TREATMENT;
    this.version++;
    this.domainEvents.add(new HospitalManagementSystemScheduleAppointmentEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void recordTreatment(RecordTreatmentCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run recordTreatment when aggregate is terminal");
    this.status = HospitalManagementSystemStatus.DISCHARGED;
    this.version++;
    this.domainEvents.add(new HospitalManagementSystemRecordTreatmentEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void generateBill(GenerateBillCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run generateBill when aggregate is terminal");
    this.status = HospitalManagementSystemStatus.BILLED;
    this.version++;
    this.domainEvents.add(new HospitalManagementSystemGenerateBillEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == HospitalManagementSystemStatus.ARCHIVED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class HospitalManagementSystemService {
    private final HospitalManagementSystemRepository repository;
    private final HospitalManagementSystemPolicy policy;
    private final Outbox outbox;

    HospitalManagementSystemService(HospitalManagementSystemRepository repository, HospitalManagementSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(HospitalManagementSystemCommand command) {
        HospitalManagementSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("HospitalManagementSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof RegisterPatientCommand c) aggregate.registerPatient(c);
        if (command instanceof ScheduleAppointmentCommand c) aggregate.scheduleAppointment(c);
        if (command instanceof RecordTreatmentCommand c) aggregate.recordTreatment(c);
        if (command instanceof GenerateBillCommand c) aggregate.generateBill(c);
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

- Persist `HospitalManagementSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `HospitalManagementSystem` invariants and each command method.
- State-machine test all valid and invalid `HospitalManagementSystemStatus` transitions.
- Contract test every `HospitalManagementSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `HospitalManagementSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `HospitalManagementSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
