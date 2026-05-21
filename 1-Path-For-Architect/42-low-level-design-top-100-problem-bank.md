# Top 100 Low-Level Design Problem Bank For Architect Interviews

This is the expanded LLD/OOD practice bank for architect-role interviews. It complements `03-low-level-design-solid-oop.md`, which contains the answer flow, SOLID guidance, pattern catalog, and the original top-50 list.

Goal:

> Practice enough LLD problem shapes that any interview can be reduced to known object-modeling, state-machine, concurrency, extensibility, persistence, and testing patterns.

## How To Use This Bank

For every problem, produce:

1. Requirements and non-goals.
2. Actors and use cases.
3. Core entities, value objects, aggregates, and services.
4. Class responsibilities and relationships.
5. Interfaces, policies, repositories, factories, and adapters.
6. State transitions and invariants.
7. Concurrency and thread-safety strategy.
8. Persistence and transaction boundaries.
9. Error handling and idempotency.
10. Extensibility points and design patterns.
11. Test plan: unit, contract, state-machine, concurrency, and property-based tests.

Architect rule:

> Do not start with class names. Start with behavior, invariants, state transitions, and change points; then choose classes and patterns that protect them.

---

# Pattern Coverage Map

| Pattern / Skill | Problems That Train It |
|---|---|
| composition vs inheritance | parking lot, vehicle rental, card games, file system |
| state pattern | vending machine, ATM, order workflow, elevator, traffic signal |
| strategy pattern | pricing, payment, discount, ride matching, tax calculation |
| factory/builder | order creation, game setup, payment provider creation, UI forms |
| command pattern | task scheduler, undo/redo, workflow engine, job queue |
| observer/pub-sub | event bus, notification service, chat, stock ticker |
| decorator/proxy | cache, logger, rate limiter, retry, auth filter |
| repository/unit of work | booking, payments, inventory, library, hospital |
| saga/process manager | order management, food delivery, payment/refund workflow |
| concurrency and locks | cache, thread pool, seat booking, inventory, connection pool |
| idempotency | payment processing, retries, order placement, job execution |
| domain invariants | ledger, wallet, booking, auction, splitwise |
| extensible policies | parking pricing, coupons, access control, feature flags |
| data structures | hash map, LRU/LFU, trie, spreadsheet, file system |
| plugin/adapter design | payment gateway, notification provider, storage provider |

---

# Top 100 LLD Problems By Category

## 1. Classic OOD And Domain Modeling

| # | Problem Statement | Category | Primary Patterns / Focus |
|---|---|---|---|
| 1 | Design a parking lot. | Classic OOD | composition, allocation strategy, pricing policy, ticket lifecycle |
| 2 | Design an elevator system. | State machine | scheduler, direction state, request queues, concurrency |
| 3 | Design a vending machine. | State machine | State, inventory, payment, refunds, error states |
| 4 | Design an ATM. | Banking OOD | state transitions, transaction boundaries, cash dispenser |
| 5 | Design a traffic signal controller. | Control system | State, timing policy, pedestrian events, emergency override |
| 6 | Design a library management system. | Domain modeling | catalog, loans, reservations, fines, policies |
| 7 | Design a hotel booking system. | Booking OOD | availability, reservation state, pricing, cancellation |
| 8 | Design an airline reservation system. | Booking OOD | seat inventory, fare classes, holds, payment timeout |
| 9 | Design a movie ticket booking system. | Booking OOD | seat locking, concurrency, payment expiry, fairness |
| 10 | Design a car rental system. | Rental OOD | vehicle fleet, pricing, availability, pickup/return workflow |

## 2. Games, Rules Engines, And Board Models

| # | Problem Statement | Category | Primary Patterns / Focus |
|---|---|---|---|
| 11 | Design chess. | Game | board, pieces, move validation, check/checkmate, strategy |
| 12 | Design tic-tac-toe. | Game | board state, win detection, simple AI, extensible board size |
| 13 | Design snake and ladders. | Game | board generation, dice, turns, movement rules |
| 14 | Design minesweeper. | Game | grid, reveal BFS/DFS, mine placement, state transitions |
| 15 | Design tetris. | Game | piece rotation, collision, board updates, scoring |
| 16 | Design battleship. | Game | ship placement, hits/misses, turn state, validation |
| 17 | Design blackjack. | Card game | deck, hand evaluation, dealer rules, betting states |
| 18 | Design poker hand evaluator. | Card game | hand ranking, rules strategy, tie-breaking |
| 19 | Design a deck of cards library. | Reusable library | value objects, shuffle strategy, dealing, immutability |
| 20 | Design a sudoku solver. | Algorithmic LLD | backtracking, constraints, board abstraction, testability |

## 3. Commerce, Booking, And Workflow Domains

| # | Problem Statement | Category | Primary Patterns / Focus |
|---|---|---|---|
| 21 | Design an online shopping cart. | Commerce | cart aggregate, pricing, coupon strategy, inventory checks |
| 22 | Design checkout flow. | Commerce workflow | facade, saga, payment, inventory, order state machine |
| 23 | Design order management system. | Commerce workflow | state machine, command, outbox, idempotency |
| 24 | Design inventory management system. | Commerce | stock, reservations, replenishment, concurrency |
| 25 | Design coupon and discount engine. | Rules/pricing | Strategy, Specification, policy composition, priority |
| 26 | Design product catalog. | Commerce | entities, variants, attributes, search DTOs, versioning |
| 27 | Design auction system. | Marketplace | bidding rules, sniping protection, clock, winner selection |
| 28 | Design food ordering system. | Marketplace | restaurant menu, order lifecycle, delivery assignment |
| 29 | Design ride-sharing trip lifecycle. | Marketplace | matching policy, trip states, pricing, cancellation |
| 30 | Design meeting room booking. | Scheduling | recurring bookings, conflict detection, holds, calendars |

## 4. Payments, Wallets, Ledger, And Finance

| # | Problem Statement | Category | Primary Patterns / Focus |
|---|---|---|---|
| 31 | Design payment processing system. | Fintech | idempotency, provider adapter, retries, reconciliation |
| 32 | Design digital wallet. | Fintech | ledger, balance invariants, holds, limits |
| 33 | Design banking ledger. | Fintech | double-entry accounting, immutable entries, audit |
| 34 | Design refund workflow. | Fintech workflow | process manager, state machine, compensation |
| 35 | Design splitwise expense sharing. | Fintech/social | debt graph, simplification, settlements, invariants |
| 36 | Design invoice and billing system. | SaaS billing | invoice state, proration, retries, dunning policy |
| 37 | Design subscription management. | SaaS billing | plan changes, trial, renewal, cancellation, entitlements |
| 38 | Design tax calculation service. | Finance rules | jurisdiction strategy, rule versioning, rounding |
| 39 | Design expense approval system. | Enterprise finance | policy engine, workflow, delegation, audit |
| 40 | Design fraud rule engine. | Risk | Specification, rule composition, explainability, versioning |

## 5. Data Structures And In-Memory Components

| # | Problem Statement | Category | Primary Patterns / Focus |
|---|---|---|---|
| 41 | Design LRU cache. | Data structure | hashmap + doubly linked list, eviction, thread safety |
| 42 | Design LFU cache. | Data structure | frequency buckets, tie-breaking, O(1) operations |
| 43 | Design TTL cache. | Data structure | expiration, lazy/eager cleanup, time source abstraction |
| 44 | Design concurrent hash map. | Data structure | sharding locks, resizing, thread safety |
| 45 | Design hash map. | Data structure | hashing, collisions, resizing, load factor |
| 46 | Design trie/autocomplete library. | Data structure | prefix search, ranking, memory trade-offs |
| 47 | Design rate limiter library. | Data structure/platform | token bucket, sliding window, distributed extension |
| 48 | Design priority queue scheduler. | Data structure | heap, delayed jobs, recurring jobs, cancellation |
| 49 | Design bloom filter service. | Data structure | false positives, hash functions, sizing |
| 50 | Design in-memory database. | Data structure/database | indexing, transactions, TTL, snapshots |

## 6. Infrastructure Libraries And Platform Components

| # | Problem Statement | Category | Primary Patterns / Focus |
|---|---|---|---|
| 51 | Design thread pool. | Concurrency | worker lifecycle, bounded queue, shutdown, rejection policy |
| 52 | Design connection pool. | Resource management | health checks, leasing, timeout, leak detection |
| 53 | Design object pool. | Resource management | pooling lifecycle, validation, max size, cleanup |
| 54 | Design retry library. | Resilience | backoff, jitter, retryable errors, idempotency |
| 55 | Design circuit breaker library. | Resilience | closed/open/half-open states, metrics, fallback |
| 56 | Design distributed lock client. | Coordination | leases, fencing tokens, renewal, failure handling |
| 57 | Design job scheduler / cron library. | Scheduling | recurring jobs, misfires, locks, persistence |
| 58 | Design workflow engine. | Orchestration | DAG/state machine, retries, compensation, persistence |
| 59 | Design event bus / pub-sub library. | Messaging | observer, filtering, async handlers, delivery guarantees |
| 60 | Design message queue client. | Messaging | ack/nack, visibility timeout, retry, DLQ |

## 7. APIs, Gateways, Configuration, And Developer Tools

| # | Problem Statement | Category | Primary Patterns / Focus |
|---|---|---|---|
| 61 | Design URL shortener LLD. | API/product | key generation, repository, redirect stats, expiration |
| 62 | Design API gateway filter chain. | API/platform | chain of responsibility, auth, rate limit, routing |
| 63 | Design middleware pipeline. | API/platform | filters, interceptors, ordering, error handling |
| 64 | Design feature flag SDK. | Platform SDK | local cache, targeting rules, rollout, fallback |
| 65 | Design configuration service client. | Platform SDK | snapshots, watchers, versioning, refresh policy |
| 66 | Design logging framework. | Developer tool | appenders, formatters, levels, async buffering |
| 67 | Design metrics library. | Observability SDK | counters, gauges, histograms, tags, exporters |
| 68 | Design tracing SDK. | Observability SDK | spans, context propagation, sampling, exporters |
| 69 | Design dependency injection container. | Framework | providers, scopes, lifecycle, circular dependencies |
| 70 | Design plugin registry. | Extensibility | discovery, lifecycle, versioning, isolation |

## 8. File Systems, Editors, Documents, And Productivity

| # | Problem Statement | Category | Primary Patterns / Focus |
|---|---|---|---|
| 71 | Design file system. | Storage OOD | directories, files, permissions, path resolution |
| 72 | Design text editor. | Editor | buffer, cursor, undo/redo, command pattern |
| 73 | Design spreadsheet. | Productivity | formula graph, dependency evaluation, cycle detection |
| 74 | Design calendar application. | Productivity | events, recurrence, conflict detection, time zones |
| 75 | Design meeting scheduler. | Productivity | availability, ranking slots, constraints, invites |
| 76 | Design notification service LLD. | Productivity/platform | channels, templates, preferences, batching |
| 77 | Design email client model. | Productivity | folders, labels, threads, search, sync state |
| 78 | Design task management app. | Productivity | projects, tasks, assignment, state transitions |
| 79 | Design document sharing permissions. | Collaboration | ACLs, inherited permissions, link sharing, audit |
| 80 | Design collaborative whiteboard model. | Collaboration | shapes, layers, events, conflict handling |

## 9. Social, Chat, Media, And User-Facing Apps

| # | Problem Statement | Category | Primary Patterns / Focus |
|---|---|---|---|
| 81 | Design chat application LLD. | Communication | conversations, messages, receipts, typing indicators |
| 82 | Design group chat permissions. | Communication | roles, membership, moderation, state transitions |
| 83 | Design social network LLD. | Social | profiles, friendships, posts, comments, privacy |
| 84 | Design news feed domain model. | Social/feed | post aggregate, ranking policy, visibility rules |
| 85 | Design Instagram-like media post model. | Social/media | media, captions, likes, comments, moderation |
| 86 | Design music player. | Media | playlists, playback queue, repeat/shuffle strategy |
| 87 | Design video player state machine. | Media | buffering, play/pause, seek, quality changes |
| 88 | Design content moderation workflow. | Trust/safety | review states, policies, escalation, appeals |
| 89 | Design review/rating system. | Social/commerce | ratings, aggregates, moderation, fraud checks |
| 90 | Design recommendation rule configuration. | Product/ML | policy objects, feature flags, experiment variants |

## 10. Enterprise, Healthcare, Operations, And Security

| # | Problem Statement | Category | Primary Patterns / Focus |
|---|---|---|---|
| 91 | Design hospital management system. | Healthcare | patients, doctors, appointments, billing, privacy |
| 92 | Design clinic appointment scheduler. | Healthcare | slots, availability, cancellations, reminders |
| 93 | Design restaurant management system. | Operations | tables, orders, kitchen queue, billing |
| 94 | Design warehouse management system. | Operations | locations, picking, packing, inventory movements |
| 95 | Design access control system. | Security | RBAC/ABAC, policies, resources, audit |
| 96 | Design secrets manager LLD. | Security | encryption, rotation, versioning, access policy |
| 97 | Design audit log library. | Security/compliance | immutable events, redaction, retention, query |
| 98 | Design approval workflow system. | Enterprise workflow | stages, delegates, escalation, audit |
| 99 | Design rule engine. | Enterprise rules | parser/expression model, specification, versioning |
| 100 | Design form builder and validation engine. | Enterprise app | schema, fields, validators, conditional logic |

---

# Category Practice Order

## First 20: Most Common LLD Interview Starters

Practice these until you can draw classes, interfaces, state, and tests quickly:

- Parking lot
- Elevator
- Vending machine
- ATM
- Library management
- Hotel booking
- Movie ticket booking
- Chess
- Online shopping cart
- Payment processing
- Splitwise
- LRU cache
- LFU cache
- Rate limiter
- Thread pool
- Connection pool
- Retry library
- Task scheduler / cron
- File system
- Chat application

## Next 30: Architect-Level LLD Differentiators

These show depth beyond simple OOD:

- Banking ledger
- Refund workflow
- Subscription management
- Fraud rule engine
- Concurrent hash map
- TTL cache
- In-memory database
- Circuit breaker
- Distributed lock client
- Workflow engine
- Event bus
- API gateway filter chain
- Feature flag SDK
- Configuration client
- Logging framework
- Metrics library
- Dependency injection container
- Spreadsheet
- Calendar application
- Document sharing permissions
- Group chat permissions
- Content moderation workflow
- Access control system
- Secrets manager
- Audit log library
- Approval workflow
- Rule engine
- Form builder
- Inventory management
- Order management

---

# How To Generalize Any New LLD Problem

When you see an unfamiliar LLD question, classify it by dominant shape:

| If the problem is about... | Think of... | Main Design Lens |
|---|---|---|
| lifecycle states | vending machine, order, payment, video player | State pattern, guards, transitions |
| allocation | parking, hotel, seat booking, inventory | strategy, locking, constraints |
| money or balance | wallet, ledger, payment, refund | invariants, idempotency, audit |
| users and permissions | document sharing, access control, chat roles | policy, ACL, RBAC/ABAC |
| rules | coupon, tax, fraud, form validation | specification, strategy, versioning |
| reusable library | cache, rate limiter, retry, circuit breaker | interface, concurrency, configuration |
| async work | scheduler, queue client, workflow engine | command, persistence, retry |
| editable document | text editor, spreadsheet, whiteboard | command, memento, dependency graph |
| resource pool | thread pool, connection pool, object pool | lifecycle, bounds, cleanup |
| plugin/provider integration | payment, notification, storage, metrics | adapter, factory, registry |

Architect interview phrase:

> I first identify invariants, state transitions, and expected change points. Then I choose aggregates, interfaces, policies, and patterns that keep those rules testable and extensible without turning the design into abstract noise.

---

# LLD Review Checklist

Use this to score every answer:

- [ ] Requirements and non-goals clarified.
- [ ] Actors and use cases identified.
- [ ] Entities and value objects separated.
- [ ] Invariants stated explicitly.
- [ ] State transitions modeled with valid and invalid transitions.
- [ ] Interfaces and abstractions named by responsibility, not technology.
- [ ] SOLID principles applied pragmatically.
- [ ] Patterns justified by change points.
- [ ] Concurrency and thread safety addressed.
- [ ] Persistence and transaction boundaries defined.
- [ ] Errors, retries, idempotency, and compensation handled where relevant.
- [ ] Extensibility requirements handled without overengineering.
- [ ] Unit, state-machine, contract, and concurrency tests described.
