# 027. Design Auction System

Source problem: `Design auction system.`  
Category: `Marketplace`  
Primary focus: `bidding rules, sniping protection, clock, winner selection`  
Archetype: `rules`

## 1. Interview Framing

Design `auction system` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `auction system` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `SCHEDULED, OPEN, EXTENDED, CLOSED, SETTLED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `Bidder`
- `Seller`
- `Clock`

Primary use cases:

- `openAuction` command on `AuctionSystem`
- `placeBid` command on `AuctionSystem`
- `extendAuction` command on `AuctionSystem`
- `settleWinner` command on `AuctionSystem`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `AuctionSystem` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Auction, Bid, BidderProfile, ReservePrice, WinningResult` | Have identity and change over time under the aggregate. |
| Value objects | `Money, TimeRange, BidId, Version` | Immutable concepts compared by value. |
| Policies | `AuctionSystemPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `AuctionSystemRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
SCHEDULED, OPEN, EXTENDED, CLOSED, SETTLED, CANCELLED
```

Invariants:

- `AuctionSystem` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `AuctionSystemService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `AuctionSystem` | Composes | Auction, Bid, BidderProfile | Owns invariants and lifecycle transitions. |
| `AuctionSystemRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `AuctionSystemPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class AuctionSystem {
  +UUID id
  +AuctionSystemStatus status
  +long version
  +validateInvariants()
}
class AuctionSystemService {
  +handle(command)
}
class AuctionSystemRepository {
  <<interface>>
  +findById(UUID id) AuctionSystem
  +save(AuctionSystem aggregate, long expectedVersion)
}
class AuctionSystemPolicy {
  <<interface>>
  +evaluate(context) Decision
}
AuctionSystemService --> AuctionSystemRepository
AuctionSystemService --> AuctionSystemPolicy
AuctionSystemService --> AuctionSystem
class Auction {
  +UUID id
  +validate()
}
AuctionSystem "1" o-- "many" Auction
class Bid {
  +UUID id
  +validate()
}
AuctionSystem "1" o-- "many" Bid
class BidderProfile {
  +UUID id
  +validate()
}
AuctionSystem "1" o-- "many" BidderProfile
class ReservePrice {
  +UUID id
  +validate()
}
AuctionSystem "1" o-- "many" ReservePrice
class Money {
  <<value object>>
}
AuctionSystem ..> Money
class TimeRange {
  <<value object>>
}
AuctionSystem ..> TimeRange
class BidId {
  <<value object>>
}
AuctionSystem ..> BidId
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as AuctionSystemService
participant Repo as AuctionSystemRepository
participant Policy as AuctionSystemPolicy
participant Agg as AuctionSystem
participant Outbox
Client->>Service: openAuction(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: openAuction(command)
Agg-->>Service: AuctionSystemOpenAuctionEvent
Service->>Repo: save(aggregate, expectedVersion)
Service->>Outbox: append(domainEvents)
Service-->>Client: result DTO
```

## 9. Applied Design Patterns

| Pattern | Where it fits |
|---|---|
| Specification | Compose business predicates and keep rule evaluation explainable. |

## 10. Java Reference Design

This is intentionally framework-free Java. In an interview, write the aggregate, repository, policy, and service first; add adapters later.

```java
package lld.auctionsystem;

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

enum AuctionSystemStatus {
    SCHEDULED,
    OPEN,
    EXTENDED,
    CLOSED,
    SETTLED,
    CANCELLED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record AuctionSystemOpenAuctionEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record AuctionSystemPlaceBidEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record AuctionSystemExtendAuctionEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record AuctionSystemSettleWinnerEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface AuctionSystemCommand permits OpenAuctionCommand, PlaceBidCommand, ExtendAuctionCommand, SettleWinnerCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record OpenAuctionCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements AuctionSystemCommand {}
record PlaceBidCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements AuctionSystemCommand {}
record ExtendAuctionCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements AuctionSystemCommand {}
record SettleWinnerCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements AuctionSystemCommand {}

interface AuctionSystemRepository {
    Optional<AuctionSystem> findById(UUID id);
    void save(AuctionSystem aggregate, long expectedVersion);
}

interface AuctionSystemPolicy {
    Decision evaluate(AuctionSystem aggregate, AuctionSystemCommand command);
}

final class Auction {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class AuctionSystem {
    private final UUID id;
    private final List<Auction> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private AuctionSystemStatus status;
    private long version;

    AuctionSystem(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = AuctionSystemStatus.SCHEDULED;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    AuctionSystemStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void openAuction(OpenAuctionCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run openAuction when aggregate is terminal");
    this.status = AuctionSystemStatus.OPEN;
    this.version++;
    this.domainEvents.add(new AuctionSystemOpenAuctionEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void placeBid(PlaceBidCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run placeBid when aggregate is terminal");
    this.status = AuctionSystemStatus.EXTENDED;
    this.version++;
    this.domainEvents.add(new AuctionSystemPlaceBidEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void extendAuction(ExtendAuctionCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run extendAuction when aggregate is terminal");
    this.status = AuctionSystemStatus.CLOSED;
    this.version++;
    this.domainEvents.add(new AuctionSystemExtendAuctionEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void settleWinner(SettleWinnerCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run settleWinner when aggregate is terminal");
    this.status = AuctionSystemStatus.SETTLED;
    this.version++;
    this.domainEvents.add(new AuctionSystemSettleWinnerEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == AuctionSystemStatus.CANCELLED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class AuctionSystemService {
    private final AuctionSystemRepository repository;
    private final AuctionSystemPolicy policy;
    private final Outbox outbox;

    AuctionSystemService(AuctionSystemRepository repository, AuctionSystemPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(AuctionSystemCommand command) {
        AuctionSystem aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("AuctionSystem not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof OpenAuctionCommand c) aggregate.openAuction(c);
        if (command instanceof PlaceBidCommand c) aggregate.placeBid(c);
        if (command instanceof ExtendAuctionCommand c) aggregate.extendAuction(c);
        if (command instanceof SettleWinnerCommand c) aggregate.settleWinner(c);
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

- Persist `AuctionSystem` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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
| Compose business predicates and keep rule evaluation explainable. | `Specification` |
| New persistence backend | Implement repository/adapter interfaces. |
| New read model or notification | Subscribe to domain events from the outbox. |
| New validation or business rule | Add policy/specification implementation and register it. |

## 15. Test Plan

- Unit test `AuctionSystem` invariants and each command method.
- State-machine test all valid and invalid `AuctionSystemStatus` transitions.
- Contract test every `AuctionSystemRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `AuctionSystem` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `AuctionSystemService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
