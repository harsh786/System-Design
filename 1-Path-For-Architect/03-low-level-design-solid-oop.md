# Low-Level Design, SOLID, OOP, and Patterns

_Split from `../world_class_pro_architect_master_roadmap.md`. The original source file is intentionally untouched._

---

## Architect-Level LLD Mastery Addendum

Use this section as the interview operating model for all LLD/OOD questions.

### LLD Answer Flow

```text
Clarify requirements -> Identify actors -> Define use cases -> Extract domain entities -> Define invariants -> Choose relationships -> Define interfaces -> Model state transitions -> Handle concurrency -> Handle persistence -> Handle errors -> Add extensibility points -> Define tests
```

A strong answer does not start with classes. It starts with behavior, invariants, and change points.

### SOLID in Interview Language

| Principle | What It Means | Interview Proof | Common Failure |
| --- | --- | --- | --- |
| SRP | One reason to change per class/module. | Separate pricing, payment, inventory, and notification policies. | A `Manager` class coordinating everything. |
| OCP | Add behavior through extension, not risky modification. | Strategy, policy interfaces, plugins, feature rules. | Adding `if/else` for every new type. |
| LSP | Subtypes must preserve base contracts. | A replacement implementation works without caller changes. | Subclass throws unsupported operations or weakens invariants. |
| ISP | Clients depend only on operations they need. | Split read/write/admin interfaces. | One fat interface with unused methods. |
| DIP | High-level policy depends on abstractions, not concrete infrastructure. | Domain service depends on `PaymentProvider`, not `StripeClient`. | Business logic imports database, HTTP, or vendor SDK directly. |

### OOP Relationship Rules

| Relationship | Meaning | Use When | Interview Warning |
| --- | --- | --- | --- |
| Association | One object knows another. | Collaboration without ownership. | Avoid turning every relation into bidirectional navigation. |
| Aggregation | Whole references parts, but parts can live independently. | Team and employees, playlist and songs. | Often overused; explain lifecycle clearly. |
| Composition | Whole owns lifecycle of parts. | Order and order lines, board and cells. | Deleting the whole deletes the part. |
| Inheritance | Subtype is substitutable for base type. | Stable taxonomy with shared contract. | Prefer composition for behavior variation. |
| Dependency | Temporary use of another object/service. | Method parameter, factory call, policy call. | Keep dependencies explicit and injectable. |

### Core Design Surfaces

- Domain model: entities, value objects, aggregates, services, repositories, factories.
- Contracts: interfaces, DTOs, commands, events, errors, validation rules.
- Invariants: what must always be true, where it is enforced, and how it is tested.
- State machines: states, allowed transitions, guards, idempotency, retries, compensation.
- Concurrency: locks, optimistic concurrency, atomic operations, queues, immutability, thread safety.
- Persistence: transaction boundaries, repository APIs, schema shape, indexes, consistency guarantees.
- Extensibility: policy interfaces, strategy selection, plugin registry, configuration, versioning.
- Observability: structured logs, metrics, trace IDs, audit events for important state transitions.

### Pattern Selection Matrix

| Problem | Prefer | Why |
| --- | --- | --- |
| Multiple interchangeable algorithms | Strategy | Keeps algorithm choice explicit and testable. |
| Object construction has many optional fields | Builder | Protects invariants and avoids long constructors. |
| External system must look like local abstraction | Adapter | Isolates vendor/client differences. |
| Add behavior without changing object contract | Decorator | Useful for logging, caching, auth, retries. |
| Complex subsystem needs simple entry point | Facade | Hides orchestration detail from callers. |
| Behavior depends on lifecycle state | State | Removes scattered conditional transitions. |
| Request should be queued, retried, undone, or audited | Command | Captures intent as an object. |
| Many subscribers react to a change | Observer/Event | Decouples producer and consumers. |
| Business rules are combinable predicates | Specification | Makes rules reusable and testable. |
| Cross-service data change must emit event | Outbox | Preserves atomic write plus reliable publish. |

### Concurrency Checklist

- Identify shared mutable state.
- Prefer immutability or ownership transfer.
- Define lock ordering if multiple locks exist.
- Use optimistic concurrency for user-facing aggregate updates when conflicts are rare.
- Use idempotency keys for commands that may retry.
- Use bounded queues and back-pressure instead of unbounded memory growth.
- Document thread-safety for each public class.
- Test with concurrent execution, forced retries, and race-prone timing.

### LLD Test Plan

- Unit tests for value objects, policies, validators, and state transitions.
- Contract tests for interfaces and adapters.
- Integration tests for repositories and transaction boundaries.
- Concurrency tests for shared state, idempotency, and retry safety.
- Property-based tests for pricing, scheduling, allocation, matching, and state-machine invariants.
- Mutation tests or negative tests for critical rules.

### What Separates Architect-Level LLD

- You state invariants before implementation.
- You know where each business rule lives.
- You make extensibility explicit without abstracting everything.
- You discuss concurrency and failure behavior.
- You show how the design is tested.
- You can evolve the design for new requirements without rewriting the core.

---

## Core Principles

- SOLID.
- DRY.
- KISS.
- YAGNI.
- Composition over inheritance.
- Encapsulation.
- Polymorphism.
- Immutability where useful.
- Dependency inversion.
- Separation of concerns.
- High cohesion, low coupling.

## Design Patterns

### Creational

- Factory Method.
- Abstract Factory.
- Builder.
- Prototype.
- Singleton with caution.

### Structural

- Adapter.
- Facade.
- Decorator.
- Proxy.
- Composite.
- Bridge.

### Behavioral

- Strategy.
- Observer.
- Command.
- State.
- Chain of Responsibility.
- Template Method.
- Mediator.
- Visitor.

### Enterprise Patterns

- Repository.
- Unit of Work.
- Service Layer.
- Specification.
- Data Mapper.
- Domain Model.
- Transaction Script.
- CQRS.
- Outbox.
- Saga.

## LLD Answer Template

```text
1. Clarify requirements
2. Identify actors and use cases
3. Identify core entities
4. Define class responsibilities
5. Define interfaces
6. Define relationships
7. Model state transitions
8. Handle concurrency
9. Define persistence model
10. Define error handling
11. Discuss extensibility
12. Discuss tests
```

## Practice Problems

- Parking lot.
- Elevator.
- Library management.
- Food delivery.
- Hotel booking.
- Movie ticket booking.
- Chess.
- Snake and ladder.
- Splitwise.
- ATM.
- Vending machine.
- File system.
- Logging framework.
- Rate limiter.
- Cache library.
- Notification service.
- Payment gateway.
- Wallet.
- Rule engine.
- Workflow engine.
- Feature flag SDK.
- Job scheduler.
- API gateway filters.
- Distributed lock client.
- Circuit breaker library.

---


## 20.2 LLD Principles and Object Relationships

### SOLID in Interview Language

- Single Responsibility Principle: one reason to change; separate orchestration, domain rules, persistence, and transport.
- Open/Closed Principle: extend behavior through interfaces, strategy, plugin points, and configuration.
- Liskov Substitution Principle: subclasses must preserve parent contracts and invariants.
- Interface Segregation Principle: clients should not depend on methods they do not use.
- Dependency Inversion Principle: domain depends on abstractions, not framework or database details.

### OOD Relationship Types

- Inheritance: "is-a"; use only when subtype behavior truly preserves the base contract.
- Composition: strong "has-a"; child lifecycle is owned by parent; preferred for behavior reuse.
- Aggregation: weak "has-a"; referenced object can outlive the owner.
- Association: one object uses or knows another without ownership.
- Dependency: temporary use through method parameters or local variables.
- Polymorphism: call through a common interface while concrete behavior varies.
- Encapsulation: hide state and expose operations that preserve invariants.
- Abstraction: expose the essential contract, hide implementation details.

### Architect-Level LLD Checklist

1. Identify actors, use cases, and invariants.
2. Separate domain objects, services, repositories, factories, policies, and adapters.
3. Define state transitions explicitly.
4. Choose composition before inheritance unless polymorphic hierarchy is justified.
5. Make concurrency and idempotency part of the design, not an afterthought.
6. Describe persistence boundaries and transaction boundaries.
7. Add extension points only where change is realistic.
8. Prove testability with unit, integration, contract, concurrency, and property-style tests.


## Top 50 LLD/OOD Interview Problems

### Games & Entertainment
| # | Problem | Key Focus |
|---|---------|-----------|
| 1 | Design Chess | Board representation, move validation, check/checkmate detection |
| 2 | Design Tic-Tac-Toe | Game state, win detection, AI opponent |
| 3 | Design Snake and Ladders | Board generation, dice, player turns |
| 4 | Design a Deck of Cards | Shuffle algorithm, inheritance, dealing |
| 5 | Design Minesweeper | Grid reveal (BFS/DFS), mine placement, flagging |
| 6 | Design Tetris | Piece rotation, collision detection, line clearing |
| 7 | Design Snakes Game | Deque for body, food generation, collision |
| 8 | Design a Sudoku Solver | Backtracking, constraint validation |
| 9 | Design Battleship | Ship placement, hit/miss tracking, game phases |
| 10 | Design a Card Game (Blackjack/Poker) | Hand evaluation, betting rounds, dealer logic |

### Systems & Infrastructure
| # | Problem | Key Focus |
|---|---------|-----------|
| 11 | Design a Parking Lot | Vehicle types, spot allocation, pricing strategy |
| 12 | Design an Elevator System | Scheduling algorithms (SCAN, LOOK), multi-elevator coordination |
| 13 | Design a Vending Machine | State machine, inventory, payment handling |
| 14 | Design a Traffic Signal System | State transitions, timing, pedestrian crossing |
| 15 | Design an ATM | Transaction types, concurrency, receipt generation |
| 16 | Design a Hotel Booking System | Room types, availability, reservation management |
| 17 | Design an Airline Reservation System | Seat selection, flight search, booking pipeline |
| 18 | Design a Library Management System | Catalog, borrowing, fines, reservations |
| 19 | Design a Movie Ticket Booking System | Show scheduling, seat locking, payment |
| 20 | Design a Car Rental System | Vehicle fleet, pricing, pickup/return |

### Applications & Platforms
| # | Problem | Key Focus |
|---|---------|-----------|
| 21 | Design an Online Shopping Cart | Item management, pricing rules, checkout flow |
| 22 | Design a Food Ordering System | Restaurant menu, order tracking, delivery assignment |
| 23 | Design Stack Overflow | Questions, answers, voting, reputation, tags |
| 24 | Design a Social Network (Facebook) | User profiles, friendships, posts, news feed |
| 25 | Design a File System | Directories, files, permissions, path resolution |
| 26 | Design a Spreadsheet (Excel) | Cell dependencies, formula evaluation, circular detection |
| 27 | Design a Text Editor | Buffer (rope/gap buffer), cursor, undo/redo |
| 28 | Design a Logger/Logging Framework | Log levels, handlers, formatters, rotation |
| 29 | Design a Cache (LRU/LFU) | Eviction policies, HashMap + DLL, thread safety |
| 30 | Design a Pub-Sub System | Topics, subscribers, message delivery, filtering |

### Design Patterns & Utilities
| # | Problem | Key Focus |
|---|---------|-----------|
| 31 | Design a Rate Limiter | Token bucket, sliding window, decorator pattern |
| 32 | Design a Task Scheduler (Cron) | Job scheduling, priority queue, recurring tasks |
| 33 | Design a Connection Pool | Resource management, health checks, timeout |
| 34 | Design an In-Memory Database | Data structures, indexing, transactions |
| 35 | Design a URL Shortener | Encoding, storage, analytics, redirect |
| 36 | Design a Hash Map | Collision handling, resizing, load factor |
| 37 | Design a Thread Pool | Worker threads, task queue, graceful shutdown |
| 38 | Design a Retry Mechanism | Exponential backoff, jitter, circuit breaker |
| 39 | Design an Event Bus | Event routing, handler registration, async dispatch |
| 40 | Design a Notification Service | Channel routing, templates, priority, batching |

### Domain-Specific
| # | Problem | Key Focus |
|---|---------|-----------|
| 41 | Design a Ride-Sharing Service (OOD) | Matching, pricing, trip lifecycle |
| 42 | Design a Hospital Management System | Patients, doctors, appointments, billing |
| 43 | Design a Music Player | Playlist management, playback controls, queue |
| 44 | Design a Calendar Application | Events, recurring events, conflict detection |
| 45 | Design an Inventory Management System | Stock tracking, reorder points, warehouses |
| 46 | Design a Auction System (OOD) | Bidding, time constraints, winner determination |
| 47 | Design a Payment Processing System | Payment methods, refunds, reconciliation |
| 48 | Design a Restaurant Management System | Tables, orders, kitchen queue, billing |
| 49 | Design a Chat Application (OOD) | Messages, conversations, typing indicators |
| 50 | Design a Meeting Scheduler | Availability, room booking, conflict resolution |

---

