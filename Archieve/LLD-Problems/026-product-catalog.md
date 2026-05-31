# 026. Design Product Catalog

Source problem: `Design product catalog.`  
Category: `Commerce`  
Primary focus: `entities, variants, attributes, search DTOs, versioning`  
Archetype: `domain`

## 1. Interview Framing

Design `product catalog` as a domain-centered LLD. Start with behavior, invariants, lifecycle states, and change points before naming classes. Keep the core model independent from UI, database, queues, and vendor SDKs.

## 2. Requirements

- Support the main user journeys for `product catalog` with clear command boundaries.
- Maintain lifecycle state with explicit valid transitions: `DRAFT, ACTIVE, INACTIVE, OUT_OF_STOCK, ARCHIVED`.
- Preserve core invariants inside the aggregate instead of scattering checks across controllers.
- Expose repository and policy interfaces so storage, rules, and integrations can change independently.
- Emit domain events for important state changes to support audit, projections, and notifications.

## 3. Non-Goals

- Full distributed system design, capacity planning, and network protocols.
- UI screens, mobile clients, and authentication flows unless they affect domain invariants.
- Vendor-specific database schemas or framework annotations in the core model.

## 4. Actors And Use Cases

Actors:

- `CatalogAdmin`
- `Customer`
- `SearchIndexer`

Primary use cases:

- `createProduct` command on `ProductCatalog`
- `addVariant` command on `ProductCatalog`
- `updatePrice` command on `ProductCatalog`
- `publishProduct` command on `ProductCatalog`

## 5. Core Domain Model

| Type | Examples | Responsibility |
|---|---|---|
| Aggregate root | `ProductCatalog` | Owns lifecycle, invariants, version, and domain events. |
| Entities | `Product, Variant, Attribute, Category, Price` | Have identity and change over time under the aggregate. |
| Value objects | `SKU, Money, Locale, Version` | Immutable concepts compared by value. |
| Policies | `ProductCatalogPolicy`, validation/ranking/pricing strategies | Encapsulate rules that vary by business or deployment. |
| Repositories | `ProductCatalogRepository` | Load/save aggregate with optimistic concurrency. |
| Events | Domain event records | Capture meaningful state changes after successful commands. |

## 6. State, Invariants, And Relationships

States:

```text
DRAFT, ACTIVE, INACTIVE, OUT_OF_STOCK, ARCHIVED
```

Invariants:

- `ProductCatalog` can only move through declared states; invalid transitions fail fast.
- Every command validates caller intent, current state, and policy decision before mutating state.
- Aggregate version increases exactly once per successful command.
- Domain events are recorded only after the aggregate has accepted the state change.

Relationships:

| Component | Relationship | Collaborators | Why it exists |
|---|---|---|---|
| `ProductCatalogService` | Depends on | Repository, policies, clock/idempotency store | Coordinates one use case and transaction boundary. |
| `ProductCatalog` | Composes | Product, Variant, Attribute | Owns invariants and lifecycle transitions. |
| `ProductCatalogRepository` | Abstracts | Persistence model | Keeps database details out of domain code. |
| `ProductCatalogPolicy` | Strategy/specification | Business rules | Enables new rules without editing core workflow. |
| Domain events | Publish facts | Outbox/subscribers | Decouples side effects such as notifications, indexing, and audit. |

## 7. UML Class Diagram

```mermaid
classDiagram
direction LR
class ProductCatalog {
  +UUID id
  +ProductCatalogStatus status
  +long version
  +validateInvariants()
}
class ProductCatalogService {
  +handle(command)
}
class ProductCatalogRepository {
  <<interface>>
  +findById(UUID id) ProductCatalog
  +save(ProductCatalog aggregate, long expectedVersion)
}
class ProductCatalogPolicy {
  <<interface>>
  +evaluate(context) Decision
}
ProductCatalogService --> ProductCatalogRepository
ProductCatalogService --> ProductCatalogPolicy
ProductCatalogService --> ProductCatalog
class Product {
  +UUID id
  +validate()
}
ProductCatalog "1" o-- "many" Product
class Variant {
  +UUID id
  +validate()
}
ProductCatalog "1" o-- "many" Variant
class Attribute {
  +UUID id
  +validate()
}
ProductCatalog "1" o-- "many" Attribute
class Category {
  +UUID id
  +validate()
}
ProductCatalog "1" o-- "many" Category
class SKU {
  <<value object>>
}
ProductCatalog ..> SKU
class Money {
  <<value object>>
}
ProductCatalog ..> Money
class Locale {
  <<value object>>
}
ProductCatalog ..> Locale
```

## 8. Main Sequence

```mermaid
sequenceDiagram
actor Client
participant Service as ProductCatalogService
participant Repo as ProductCatalogRepository
participant Policy as ProductCatalogPolicy
participant Agg as ProductCatalog
participant Outbox
Client->>Service: createProduct(command, idempotencyKey)
Service->>Repo: findById(command.aggregateId)
Service->>Policy: evaluate(context)
Policy-->>Service: Decision.allowed()
Service->>Agg: createProduct(command)
Agg-->>Service: ProductCatalogCreateProductEvent
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
package lld.productcatalog;

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

enum ProductCatalogStatus {
    DRAFT,
    ACTIVE,
    INACTIVE,
    OUT_OF_STOCK,
    ARCHIVED
}

interface DomainEvent {
    UUID aggregateId();
    Instant occurredAt();
}

record ProductCatalogCreateProductEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ProductCatalogAddVariantEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ProductCatalogUpdatePriceEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}
record ProductCatalogPublishProductEvent(UUID aggregateId, Instant occurredAt, String idempotencyKey) implements DomainEvent {}

sealed interface ProductCatalogCommand permits CreateProductCommand, AddVariantCommand, UpdatePriceCommand, PublishProductCommand {
    UUID aggregateId();
    IdempotencyKey idempotencyKey();
}

record CreateProductCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ProductCatalogCommand {}
record AddVariantCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ProductCatalogCommand {}
record UpdatePriceCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ProductCatalogCommand {}
record PublishProductCommand(UUID aggregateId, IdempotencyKey idempotencyKey, Map<String, String> attributes) implements ProductCatalogCommand {}

interface ProductCatalogRepository {
    Optional<ProductCatalog> findById(UUID id);
    void save(ProductCatalog aggregate, long expectedVersion);
}

interface ProductCatalogPolicy {
    Decision evaluate(ProductCatalog aggregate, ProductCatalogCommand command);
}

final class Product {
    private final UUID id = UUID.randomUUID();
    private final Map<String, String> attributes = new HashMap<>();

    UUID id() { return id; }
    Map<String, String> attributes() { return Collections.unmodifiableMap(attributes); }
}

final class ProductCatalog {
    private final UUID id;
    private final List<Product> children = new ArrayList<>();
    private final List<DomainEvent> domainEvents = new ArrayList<>();
    private final Set<String> processedIdempotencyKeys = new HashSet<>();
    private ProductCatalogStatus status;
    private long version;

    ProductCatalog(UUID id) {
        this.id = Objects.requireNonNull(id);
        this.status = ProductCatalogStatus.DRAFT;
        this.version = 0;
    }

    UUID id() { return id; }
    long version() { return version; }
    ProductCatalogStatus status() { return status; }
    List<DomainEvent> pullDomainEvents() {
        List<DomainEvent> copy = List.copyOf(domainEvents);
        domainEvents.clear();
        return copy;
    }

    public void createProduct(CreateProductCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run createProduct when aggregate is terminal");
    this.status = ProductCatalogStatus.ACTIVE;
    this.version++;
    this.domainEvents.add(new ProductCatalogCreateProductEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void addVariant(AddVariantCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run addVariant when aggregate is terminal");
    this.status = ProductCatalogStatus.INACTIVE;
    this.version++;
    this.domainEvents.add(new ProductCatalogAddVariantEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void updatePrice(UpdatePriceCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run updatePrice when aggregate is terminal");
    this.status = ProductCatalogStatus.OUT_OF_STOCK;
    this.version++;
    this.domainEvents.add(new ProductCatalogUpdatePriceEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    public void publishProduct(PublishProductCommand command) {
    ensureCommandCanRun(command.idempotencyKey());
    ensure(!isTerminal(), "Cannot run publishProduct when aggregate is terminal");
    this.status = ProductCatalogStatus.ARCHIVED;
    this.version++;
    this.domainEvents.add(new ProductCatalogPublishProductEvent(id, Instant.now(), command.idempotencyKey().value()));
}

    private void ensureCommandCanRun(IdempotencyKey key) {
        if (!processedIdempotencyKeys.add(key.value())) {
            throw new DuplicateCommandException("Command already processed: " + key.value());
        }
    }

    private boolean isTerminal() {
        return status == ProductCatalogStatus.ARCHIVED;
    }

    private static void ensure(boolean condition, String message) {
        if (!condition) throw new InvalidStateException(message);
    }
}

final class ProductCatalogService {
    private final ProductCatalogRepository repository;
    private final ProductCatalogPolicy policy;
    private final Outbox outbox;

    ProductCatalogService(ProductCatalogRepository repository, ProductCatalogPolicy policy, Outbox outbox) {
        this.repository = repository;
        this.policy = policy;
        this.outbox = outbox;
    }

    public void handle(ProductCatalogCommand command) {
        ProductCatalog aggregate = repository.findById(command.aggregateId())
                .orElseThrow(() -> new NoSuchElementException("ProductCatalog not found"));
        long expectedVersion = aggregate.version();
        Decision decision = policy.evaluate(aggregate, command);
        if (!decision.allowed()) throw new PolicyRejectedException(decision.reason());

        if (command instanceof CreateProductCommand c) aggregate.createProduct(c);
        if (command instanceof AddVariantCommand c) aggregate.addVariant(c);
        if (command instanceof UpdatePriceCommand c) aggregate.updatePrice(c);
        if (command instanceof PublishProductCommand c) aggregate.publishProduct(c);
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

- Persist `ProductCatalog` as the aggregate table/document with `id`, `status`, `version`, and audit timestamps.
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

- Unit test `ProductCatalog` invariants and each command method.
- State-machine test all valid and invalid `ProductCatalogStatus` transitions.
- Contract test every `ProductCatalogRepository` implementation with optimistic conflict cases.
- Policy tests for allow/deny decisions and explainability.
- Idempotency tests that replay the same command and verify a single mutation/event.

## 16. Interview Tips

1. Start with the invariant: `ProductCatalog` owns state and rejects invalid transitions.
2. Explain the command path: controller -> `ProductCatalogService` -> policy -> aggregate -> repository -> outbox.
3. Call out the primary change points and the pattern that protects each one.
4. Discuss concurrency explicitly: optimistic versioning for aggregates or locks/atomics for in-memory structures.
5. Finish with tests: state transitions, policies, repository contracts, idempotency, and concurrency.
