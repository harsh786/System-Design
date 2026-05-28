# LLD Interview Preparation - Complete Guide (Java)

> 104 Low-Level Design problems with SOLID principles, Design Patterns, UML diagrams, and complete Java implementations.

## How to Use This Repository

1. **Start with** `104-design-an-object-oriented-design-interview-approach.md` - Learn the interview framework
2. **Study** `101-design-patterns-reference.md` - Quick reference for all 23 GoF patterns
3. **Study** `102-solid-principles-reference.md` - SOLID principles with examples
4. **Use** `103-design-patterns-in-lld-mapping.md` - Know which pattern for which problem
5. **Practice** problems in priority order below

---

## Priority 1: MUST PREPARE (Asked in 80%+ interviews)

| # | Problem | Key Pattern | Difficulty |
|---|---------|-------------|------------|
| 001 | [Parking Lot](001-parking-lot.md) | Strategy, State, Factory, Observer | Medium |
| 002 | [LRU Cache](002-lru-cache.md) | Strategy (Eviction) | Medium |
| 003 | [Elevator System](003-elevator-system.md) | State, Strategy, Observer, Command | Hard |
| 004 | [Vending Machine](004-vending-machine.md) | **State Pattern** (primary) | Medium |
| 005 | [Tic-Tac-Toe](005-tic-tac-toe.md) | Strategy, Observer | Easy |
| 006 | [Chess](006-chess.md) | Strategy, Factory, Command | Hard |
| 007 | [Snake & Ladders](007-snake-and-ladders.md) | Strategy, Builder | Easy |
| 008 | [Splitwise](008-splitwise.md) | Strategy, Observer | Medium |
| 009 | [Movie Ticket Booking](009-movie-ticket-booking.md) | Strategy, Observer, Singleton | Medium |
| 010 | [Online Shopping Cart](010-online-shopping-cart.md) | Strategy, Observer, Decorator | Medium |

---

## Priority 2: HIGHLY RECOMMENDED (Asked in 50%+ interviews)

| # | Problem | Key Pattern | Difficulty |
|---|---------|-------------|------------|
| 011 | [Hotel Booking](011-hotel-booking-system.md) | Strategy, State, Builder | Medium |
| 012 | [Library Management](012-library-management-system.md) | Strategy, Observer | Medium |
| 013 | [ATM](013-atm.md) | **State + Chain of Responsibility** | Medium |
| 014 | [Rate Limiter](014-rate-limiter.md) | Strategy | Medium |
| 015 | [Pub/Sub Event Bus](015-pub-sub-event-bus.md) | **Observer** (primary) | Medium |
| 016 | [Thread Pool](016-thread-pool.md) | Producer-Consumer, Strategy | Hard |
| 017 | [Connection Pool](017-connection-pool.md) | **Object Pool**, Factory | Medium |
| 018 | [URL Shortener](018-url-shortener.md) | Strategy, Factory | Easy |
| 019 | [Payment Processing](019-payment-processing.md) | Strategy, State, Chain | Hard |
| 020 | [Food Ordering](020-food-ordering-system.md) | State, Strategy, Observer | Medium |

---

## Priority 3: GOOD TO KNOW (Asked in 30%+ interviews)

| # | Problem | Key Pattern | Difficulty |
|---|---------|-------------|------------|
| 021 | [Traffic Signal](021-traffic-signal-controller.md) | State | Easy |
| 022 | [Airline Reservation](022-airline-reservation.md) | Strategy, State | Medium |
| 023 | [Car Rental](023-car-rental-system.md) | State, Strategy, Decorator | Medium |
| 024 | [Deck of Cards](024-deck-of-cards.md) | Factory, Template Method | Easy |
| 025 | [Ride Sharing (Uber)](025-ride-sharing.md) | State, Strategy, Observer | Hard |
| 026 | [Meeting Room Booking](026-meeting-room-booking.md) | Strategy, Observer | Medium |
| 027 | [Digital Wallet](027-digital-wallet.md) | Strategy, State, Command | Medium |
| 028 | [Logging Framework](028-logging-framework.md) | **Chain of Resp**, Strategy, Singleton | Medium |
| 029 | [Circuit Breaker](029-circuit-breaker.md) | **State Pattern** | Medium |
| 030 | [Chat Application](030-chat-application.md) | Mediator, Observer | Medium |

---

## Priority 4: DATA STRUCTURES & INFRASTRUCTURE

| # | Problem | Key Pattern | Difficulty |
|---|---------|-------------|------------|
| 031 | [Social Network](031-social-network.md) | Observer, Strategy, Iterator | Medium |
| 032 | [HashMap](032-hashmap.md) | Strategy | Hard |
| 033 | [Notification Service](033-notification-service.md) | Strategy, Observer, Factory | Medium |
| 034 | [Job Scheduler](034-job-scheduler.md) | Command, Strategy, Observer | Hard |
| 035 | [Inventory Management](035-inventory-management.md) | Observer, Strategy, State | Medium |
| 036 | [Auction System](036-auction-system.md) | Strategy, State, Observer | Medium |
| 037 | [File System](037-file-system.md) | **Composite**, Iterator | Medium |
| 038 | [Text Editor](038-text-editor.md) | **Command + Memento** | Medium |
| 039 | [Spreadsheet](039-spreadsheet.md) | Observer, Strategy, Command | Hard |
| 040 | [Trie/Autocomplete](040-trie-autocomplete.md) | Composite, Strategy | Medium |

---

## Priority 5: ADVANCED & SPECIALIZED

| # | Problem | Key Pattern | Difficulty |
|---|---------|-------------|------------|
| 041 | [LFU Cache](041-lfu-cache.md) | Strategy | Hard |
| 042 | [Object Pool](042-object-pool.md) | Object Pool, Factory | Medium |
| 043 | [DI Container](043-dependency-injection-container.md) | Factory, Singleton, Registry | Hard |
| 044 | [Workflow Engine](044-workflow-engine.md) | State, Strategy, Chain | Hard |
| 045 | [Feature Flag SDK](045-feature-flag-sdk.md) | Strategy, Observer, Proxy | Medium |
| 046 | [API Gateway](046-api-gateway.md) | **Chain of Responsibility** | Medium |
| 047 | [Subscription Management](047-subscription-management.md) | State, Strategy | Medium |
| 048 | [Coupon/Discount Engine](048-coupon-discount-engine.md) | Strategy, Chain, Composite | Medium |
| 049 | [Minesweeper](049-minesweeper.md) | Observer, Strategy | Easy |
| 050 | [Tetris](050-tetris.md) | State, Factory | Medium |

---

## Priority 6: GAMES & ENTERTAINMENT

| # | Problem | Key Pattern | Difficulty |
|---|---------|-------------|------------|
| 051 | [Blackjack](051-blackjack.md) | State, Strategy, Template | Medium |
| 052 | [Order Management](052-order-management.md) | State, Observer, Builder | Medium |
| 053 | [Distributed Lock](053-distributed-lock.md) | Strategy, Proxy | Hard |
| 054 | [Retry Library](054-retry-library.md) | Strategy, Builder, Decorator | Medium |
| 055 | [Bloom Filter](055-bloom-filter.md) | Strategy | Medium |
| 056 | [In-Memory Database](056-in-memory-database.md) | Command, Strategy, Factory | Hard |
| 057 | [Priority Queue Scheduler](057-priority-queue-scheduler.md) | Strategy, Command | Medium |
| 058 | [Message Queue](058-message-queue.md) | Observer, Strategy, Factory | Hard |
| 059 | [Calendar Application](059-calendar-application.md) | Observer, Strategy, Builder | Medium |
| 060 | [Task Management (Jira)](060-task-management.md) | State, Observer, Strategy | Medium |

---

## Priority 7: DOMAIN-SPECIFIC

| # | Problem | Key Pattern | Difficulty |
|---|---------|-------------|------------|
| 061 | [Music Player](061-music-player.md) | State, Strategy, Iterator | Medium |
| 062 | [Hospital Management](062-hospital-management.md) | Strategy, Observer, State | Medium |
| 063 | [Restaurant Management](063-restaurant-management.md) | State, Strategy, Observer | Medium |
| 064 | [Access Control (RBAC)](064-access-control-rbac.md) | Chain, Composite, Proxy | Hard |
| 065 | [Warehouse Management](065-warehouse-management.md) | Strategy, Observer, State | Medium |
| 066 | [Banking Ledger](066-banking-ledger.md) | Command, Strategy | Hard |
| 067 | [Rule Engine](067-rule-engine.md) | **Specification + Strategy** | Hard |
| 068 | [Concurrent HashMap](068-concurrent-hashmap.md) | Strategy, Proxy | Hard |
| 069 | [TTL Cache](069-ttl-cache.md) | Strategy, Observer, Decorator | Medium |
| 070 | [Plugin Registry](070-plugin-registry.md) | Registry, Factory, Observer | Medium |

---

## Priority 8: MONITORING & SECURITY

| # | Problem | Key Pattern | Difficulty |
|---|---------|-------------|------------|
| 071 | [Metrics Library](071-metrics-library.md) | Strategy, Factory, Singleton | Medium |
| 072 | [Document Sharing](072-document-sharing-permissions.md) | Proxy, Composite, Observer | Medium |
| 073 | [Email Client](073-email-client.md) | Builder, Observer, Strategy | Medium |
| 074 | [News Feed](074-news-feed.md) | Strategy, Observer, Iterator | Medium |
| 075 | [Review & Rating](075-review-rating-system.md) | Strategy, Chain | Medium |
| 076 | [Sudoku Solver](076-sudoku-solver.md) | Strategy, Template Method | Medium |
| 077 | [Battleship](077-battleship.md) | Strategy, State | Easy |
| 078 | [Poker Hand Evaluator](078-poker-hand-evaluator.md) | Chain of Responsibility | Medium |
| 079 | [Checkout Flow](079-checkout-flow.md) | Template Method, Strategy | Medium |
| 080 | [Product Catalog](080-product-catalog.md) | Composite, Strategy, Iterator | Medium |

---

## Priority 9: FINANCE & COMPLIANCE

| # | Problem | Key Pattern | Difficulty |
|---|---------|-------------|------------|
| 081 | [Expense Approval](081-expense-approval-system.md) | **Chain of Responsibility** | Medium |
| 082 | [Fraud Rule Engine](082-fraud-rule-engine.md) | Strategy, Chain, Specification | Hard |
| 083 | [Invoice & Billing](083-invoice-billing-system.md) | Builder, Strategy, State | Medium |
| 084 | [Tax Calculation](084-tax-calculation-service.md) | Strategy, Chain, Composite | Medium |
| 085 | [Refund Workflow](085-refund-workflow.md) | State, Strategy, Chain | Medium |
| 086 | [Secrets Manager](086-secrets-manager.md) | Strategy, Proxy, Observer | Hard |
| 087 | [Audit Log Library](087-audit-log-library.md) | Builder, Strategy, Decorator | Medium |
| 088 | [Approval Workflow](088-approval-workflow.md) | Chain, State, Observer | Medium |
| 089 | [Video Player](089-video-player-state-machine.md) | **State Pattern** | Easy |
| 090 | [Content Moderation](090-content-moderation.md) | Chain, State, Strategy | Medium |

---

## Priority 10: SOCIAL & CONTENT

| # | Problem | Key Pattern | Difficulty |
|---|---------|-------------|------------|
| 091 | [Recommendation System](091-recommendation-system.md) | Strategy, Chain, Observer | Hard |
| 092 | [Collaborative Whiteboard](092-collaborative-whiteboard.md) | Command, Composite, Observer | Hard |
| 093 | [Group Chat Permissions](093-group-chat-permissions.md) | Proxy, Composite, Strategy | Medium |
| 094 | [Instagram Media Post](094-instagram-media-post.md) | Builder, Observer, Iterator | Medium |
| 095 | [Configuration Service](095-configuration-service.md) | Strategy, Observer, Proxy | Medium |
| 096 | [Tracing SDK](096-tracing-sdk.md) | Builder, Strategy, Factory | Hard |
| 097 | [Clinic Appointment](097-clinic-appointment-scheduler.md) | Strategy, Observer, State | Medium |
| 098 | [Form Builder](098-form-builder-validation.md) | Builder, Composite, Strategy, Visitor | Medium |
| 099 | [Kafka Event Log](099-kafka-event-log.md) | Strategy, Iterator, Factory | Hard |
| 100 | [Meeting Scheduler](100-meeting-scheduler.md) | Strategy, Observer | Medium |

---

## Reference Guides

| # | Guide | Purpose |
|---|-------|---------|
| 101 | [Design Patterns Reference](101-design-patterns-reference.md) | All 23 GoF patterns with Java code |
| 102 | [SOLID Principles Reference](102-solid-principles-reference.md) | SOLID + OOP with before/after examples |
| 103 | [Pattern-Problem Mapping](103-design-patterns-in-lld-mapping.md) | Which pattern for which problem |
| 104 | [Interview Approach Guide](104-design-an-object-oriented-design-interview-approach.md) | Step-by-step framework for LLD interviews |

---

## Design Pattern Frequency in LLD

| Pattern | Frequency | Top Use Cases |
|---------|-----------|---------------|
| Strategy | 90+ problems | Algorithms, pricing, sorting, matching |
| Observer | 70+ problems | Notifications, real-time updates |
| State | 40+ problems | Lifecycle management, state machines |
| Factory | 35+ problems | Object creation |
| Builder | 25+ problems | Complex object construction |
| Chain of Responsibility | 20+ problems | Validation pipelines, approval chains |
| Command | 15+ problems | Undo/redo, action encapsulation |
| Composite | 12+ problems | Tree structures (files, categories, forms) |
| Singleton | 10+ problems | Registries, pools, factories |
| Template Method | 8+ problems | Algorithm skeleton with variable steps |

---

## Quick Study Plan

### 1 Week Plan (For urgent interviews)
- Day 1: Problems 001-004 (Parking Lot, LRU Cache, Elevator, Vending Machine)
- Day 2: Problems 005-008 (Tic-Tac-Toe, Chess, Snake & Ladders, Splitwise)
- Day 3: Problems 009-012 (Movie Ticket, Shopping Cart, Hotel, Library)
- Day 4: Problems 013-016 (ATM, Rate Limiter, Pub/Sub, Thread Pool)
- Day 5: Problems 017-020 (Connection Pool, URL Shortener, Payment, Food Ordering)
- Day 6: Reference guides 101-104
- Day 7: Revision of top 10

### 2 Week Plan (Comprehensive)
- Week 1: Priority 1-3 (Problems 001-030)
- Week 2: Priority 4-6 (Problems 031-060) + Reference guides

### 1 Month Plan (Complete mastery)
- Week 1: Priority 1-2 (001-020)
- Week 2: Priority 3-5 (021-050)
- Week 3: Priority 6-8 (051-080)
- Week 4: Priority 9-10 (081-100) + All references + Revision

---

## Each Solution Contains

1. Problem Statement & Requirements
2. UML Class Diagram (Mermaid)
3. Design Patterns Applied (with explanation WHY)
4. SOLID Principles Demonstrated
5. Complete Java 17+ Implementation
6. State/Sequence Diagrams (where applicable)
7. Key Interview Talking Points
8. Common Follow-up Questions
9. Test Scenarios

---

## Tech Stack
- Language: Java 17+
- Features: Records, Sealed Interfaces, Pattern Matching, var
- No frameworks - pure Java for interview clarity
- Thread-safety using java.util.concurrent where needed
