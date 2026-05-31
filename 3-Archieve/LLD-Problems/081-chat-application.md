# 081. Design Chat Application LLD

Source problem: `Design chat application LLD.`  
Category: `Communication`  
Primary focus: `conversations, messages, receipts, typing indicators`  
Archetype: `domain`

## 1. Interview Framing

Design `chat application LLD` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `chat application LLD` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `DRAFT, SENT, DELIVERED, READ, DELETED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `Sender`
- `Recipient`
- `NotificationService`

Primary use cases:

- `sendMessage` command on `ChatApplication`
- `markDelivered` command on `ChatApplication`
- `markRead` command on `ChatApplication`
- `showTyping` command on `ChatApplication`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `ChatApplication` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Conversation, Message, Participant, Receipt, TypingIndicator` | Have identity and change over time under the aggregate. |
| Value objects | `MessageId, UserId, Timestamp, DeliveryState` | Immutable concepts compared by value. |
| Policies | `ChatApplicationPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `ChatApplicationRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
DRAFT, SENT, DELIVERED, READ, DELETED, FAILED
```

Invariants:

- `ChatApplication` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `ChatApplicationService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `ChatApplication` | Composes | Conversation, Message, Participant | Owns invariants and lifecycle transitions. |
| `ChatApplicationRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `ChatApplicationPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class ChatApplication {
  +UUID id
  +ChatApplicationStatus status
  +long version
  +validateInvariants()
}
class ChatApplicationService {
  +handle(command)
}
class ChatApplicationRepository {
  <<interface>>
  +findById(UUID id) ChatApplication
  +save(ChatApplication aggregate, long expectedVersion)
}
class ChatApplicationPolicy {
  <<interface>>
  +evaluate(context) Decision
}
ChatApplicationService --> ChatApplicationRepository
ChatApplicationService --> ChatApplicationPolicy
ChatApplicationService --> ChatApplication
class Conversation {
  +UUID id
  +validate()
}
ChatApplication "1" o-- "many" Conversation
class Message {
  +UUID id
  +validate()
}
ChatApplication "1" o-- "many" Message
class Participant {
  +UUID id
  +validate()
}
ChatApplication "1" o-- "many" Participant
class Receipt {
  +UUID id
  +validate()
}
ChatApplication "1" o-- "many" Receipt
class MessageId {
  <<value object>>
}
ChatApplication ..> MessageId
class UserId {
  <<value object>>
}
ChatApplication ..> UserId
class Timestamp {
  <<value object>>
}
ChatApplication ..> Timestamp
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as ChatApplicationService
participant Repo as ChatApplicationRepository
participant Policy as ChatApplicationPolicy
participant Agg as ChatApplication
participant Outbox
Client->>Service: sendMessage(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: sendMessage(command)
Agg-->>Service: ChatApplicationSendMessageEvent
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
package lld.chatapplication;

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

enum ChatApplicationStatus {
    DRAFT,
    SENT,
    DELIVERED,
    READ,
    DELETED,
    FAILED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record ChatApplicationSendMessageEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ChatApplicationMarkDeliveredEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ChatApplicationMarkReadEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ChatApplicationShowTypingEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface ChatApplicationCommand permits SendMessageCommand, MarkDeliveredCommand, MarkReadCommand, ShowTypingCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record SendMessageCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ChatApplicationCommand {}
record MarkDeliveredCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ChatApplicationCommand {}
record MarkReadCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ChatApplicationCommand {}
record ShowTypingCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ChatApplicationCommand {}

interface ChatApplicationRepository {
    Optional<ChatApplication> findById(UUID id);
    void save(ChatApplication aggregate, long expectedVersion);
}

interface ChatApplicationPolicy {
    Decision evaluate(ChatApplication aggregate, ChatApplicationCommand command);
}

final class Conversation {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class ChatApplication {
    private final UUID id;
    private final List<Conversation> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private ChatApplicationStatus status;
    private long version;

    ChatApplication(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = ChatApplicationStatus.DRAFT;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    ChatApplicationStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void sendMessage(SendMessageCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run sendMessage when aggregate is terminal");
    this.status = ChatApplicationStatus.SENT;
    this.version++;
    this.domainEvents.add(new ChatApplicationSendMessageEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void markDelivered(MarkDeliveredCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run markDelivered when aggregate is terminal");
    this.status = ChatApplicationStatus.DELIVERED;
    this.version++;
    this.domainEvents.add(new ChatApplicationMarkDeliveredEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void markRead(MarkReadCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run markRead when aggregate is terminal");
    this.status = ChatApplicationStatus.READ;
    this.version++;
    this.domainEvents.add(new ChatApplicationMarkReadEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void showTyping(ShowTypingCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run showTyping when aggregate is terminal");
    this.status = ChatApplicationStatus.DELETED;
    this.version++;
    this.domainEvents.add(new ChatApplicationShowTypingEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == ChatApplicationStatus.FAILED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class ChatApplicationService {
    private final ChatApplicationRepository repository;
    private final ChatApplicationPolicy policy;
    private final Outbox outbox;

    ChatApplicationService(ChatApplicationRepository repository, ChatApplicationPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(ChatApplicationCommand command) {
        ChatApplication aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("ChatApplication not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof SendMessageCommand c) aggregate.sendMessage(c);
        if (command instanceof MarkDeliveredCommand c) aggregate.markDelivered(c);
        if (command instanceof MarkReadCommand c) aggregate.markRead(c);
        if (command instanceof ShowTypingCommand c) aggregate.showTyping(c);
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

- Persist `ChatApplication` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `ChatApplication` invariants and each command method.
- State-machine test all valid and invalid `ChatApplicationStatus` transitions.
- Contract test every `ChatApplicationRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `ChatApplication` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `ChatApplicationService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
