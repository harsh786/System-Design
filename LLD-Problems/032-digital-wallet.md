# 032. Design Digital Wallet

Source problem: `Design digital wallet.`  
Category: `Fintech`  
Primary focus: `ledger, balance invariants, holds, limits`  
Archetype: `finance`

## 1. Interview Framing

Design `digital wallet` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `digital wallet` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `ACTIVE, HELD, DEBITED, CREDITED, SUSPENDED`.
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

- `WalletOwner`
- `Merchant`
- `ComplianceService`

Primary use cases:

- `credit` command on `DigitalWallet`
- `debit` command on `DigitalWallet`
- `placeHold` command on `DigitalWallet`
- `transfer` command on `DigitalWallet`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `DigitalWallet` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Wallet, Account, LedgerEntry, Hold, Transfer` | Have identity and change over time under the aggregate. |
| Value objects | `Money, AccountId, TransactionId, Limit` | Immutable concepts compared by value. |
| Policies | `DigitalWalletPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `DigitalWalletRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
ACTIVE, HELD, DEBITED, CREDITED, SUSPENDED, CLOSED
```

Invariants:

- `DigitalWallet` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.
- Money and capacity changes are atomic within the transaction boundary.
- A repeated idempotency key returns the original result and never double-applies side effects.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `DigitalWalletService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `DigitalWallet` | Composes | Wallet, Account, LedgerEntry | Owns invariants and lifecycle transitions. |
| `DigitalWalletRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `DigitalWalletPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |
| Idempotency store | Guards | Command handling | Makes retries safe for payment, booking, and workflow commands. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class DigitalWallet {
  +UUID id
  +DigitalWalletStatus status
  +long version
  +validateInvariants()
}
class DigitalWalletService {
  +handle(command)
}
class DigitalWalletRepository {
  <<interface>>
  +findById(UUID id) DigitalWallet
  +save(DigitalWallet aggregate, long expectedVersion)
}
class DigitalWalletPolicy {
  <<interface>>
  +evaluate(context) Decision
}
DigitalWalletService --> DigitalWalletRepository
DigitalWalletService --> DigitalWalletPolicy
DigitalWalletService --> DigitalWallet
class Wallet {
  +UUID id
  +validate()
}
DigitalWallet "1" o-- "many" Wallet
class Account {
  +UUID id
  +validate()
}
DigitalWallet "1" o-- "many" Account
class LedgerEntry {
  +UUID id
  +validate()
}
DigitalWallet "1" o-- "many" LedgerEntry
class Hold {
  +UUID id
  +validate()
}
DigitalWallet "1" o-- "many" Hold
class Money {
  <<value object>>
}
DigitalWallet ..> Money
class AccountId {
  <<value object>>
}
DigitalWallet ..> AccountId
class TransactionId {
  <<value object>>
}
DigitalWallet ..> TransactionId
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as DigitalWalletService
participant Repo as DigitalWalletRepository
participant Policy as DigitalWalletPolicy
participant Agg as DigitalWallet
participant Outbox
Client->>Service: credit(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: credit(command)
Agg-->>Service: DigitalWalletCreditEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| State | Model valid lifecycle transitions and reject illegal moves at the aggregate boundary. |
| Repository | Keep persistence and optimistic version checks outside the domain model. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.digitalwallet;

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

enum DigitalWalletStatus {
    ACTIVE,
    HELD,
    DEBITED,
    CREDITED,
    SUSPENDED,
    CLOSED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record DigitalWalletCreditEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record DigitalWalletDebitEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record DigitalWalletPlaceHoldEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record DigitalWalletTransferEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface DigitalWalletCommand permits CreditCommand, DebitCommand, PlaceHoldCommand, TransferCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record CreditCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements DigitalWalletCommand {}
record DebitCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements DigitalWalletCommand {}
record PlaceHoldCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements DigitalWalletCommand {}
record TransferCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements DigitalWalletCommand {}

interface DigitalWalletRepository {
    Optional<DigitalWallet> findById(UUID id);
    void save(DigitalWallet aggregate, long expectedVersion);
}

interface DigitalWalletPolicy {
    Decision evaluate(DigitalWallet aggregate, DigitalWalletCommand command);
}

final class Wallet {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class DigitalWallet {
    private final UUID id;
    private final List<Wallet> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private DigitalWalletStatus status;
    private long version;

    DigitalWallet(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = DigitalWalletStatus.ACTIVE;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    DigitalWalletStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void credit(CreditCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run credit when aggregate is terminal");
    this.status = DigitalWalletStatus.HELD;
    this.version++;
    this.domainEvents.add(new DigitalWalletCreditEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void debit(DebitCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run debit when aggregate is terminal");
    this.status = DigitalWalletStatus.DEBITED;
    this.version++;
    this.domainEvents.add(new DigitalWalletDebitEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void placeHold(PlaceHoldCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run placeHold when aggregate is terminal");
    this.status = DigitalWalletStatus.CREDITED;
    this.version++;
    this.domainEvents.add(new DigitalWalletPlaceHoldEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void transfer(TransferCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run transfer when aggregate is terminal");
    this.status = DigitalWalletStatus.SUSPENDED;
    this.version++;
    this.domainEvents.add(new DigitalWalletTransferEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == DigitalWalletStatus.CLOSED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class DigitalWalletService {
    private final DigitalWalletRepository repository;
    private final DigitalWalletPolicy policy;
    private final Outbox outbox;

    DigitalWalletService(DigitalWalletRepository repository, DigitalWalletPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(DigitalWalletCommand command) {
        DigitalWallet aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("DigitalWallet not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof CreditCommand c) aggregate.credit(c);
        if (command instanceof DebitCommand c) aggregate.debit(c);
        if (command instanceof PlaceHoldCommand c) aggregate.placeHold(c);
        if (command instanceof TransferCommand c) aggregate.transfer(c);
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

- Persist `DigitalWallet` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Keep persistence and optimistic version checks outside the domain model. | `Repository` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `DigitalWallet` invariants and each command method.
- State-machine test all valid and invalid `DigitalWalletStatus` transitions.
- Contract test every `DigitalWalletRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `DigitalWallet` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `DigitalWalletService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
