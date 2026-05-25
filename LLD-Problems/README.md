# LLD Problems: Interview Playbook

This directory contains one low-level design document per problem from
`1-Path-For-Architect/42-low-level-design-top-100-problem-bank.md`, plus
additional high-signal LLD drills such as Kafka.

Each document follows the same interview-ready structure:

- requirements and non-goals
- actors and use cases
- entities, value objects, aggregates, services, repositories, policies, and events
- state transitions, invariants, relationships, Mermaid UML, and sequence diagrams
- Java reference design
- concurrency, persistence, error handling, idempotency, extensibility, and tests

## Index

| # | Problem | Category | File |
|---|---|---|---|
| 1 | Design a parking lot. | Classic OOD | [001-parking-lot.md](./001-parking-lot.md) |
| 2 | Design an elevator system. | State machine | [002-elevator-system.md](./002-elevator-system.md) |
| 3 | Design a vending machine. | State machine | [003-vending-machine.md](./003-vending-machine.md) |
| 4 | Design an ATM. | Banking OOD | [004-atm.md](./004-atm.md) |
| 5 | Design a traffic signal controller. | Control system | [005-traffic-signal-controller.md](./005-traffic-signal-controller.md) |
| 6 | Design a library management system. | Domain modeling | [006-library-management-system.md](./006-library-management-system.md) |
| 7 | Design a hotel booking system. | Booking OOD | [007-hotel-booking-system.md](./007-hotel-booking-system.md) |
| 8 | Design an airline reservation system. | Booking OOD | [008-airline-reservation-system.md](./008-airline-reservation-system.md) |
| 9 | Design a movie ticket booking system. | Booking OOD | [009-movie-ticket-booking-system.md](./009-movie-ticket-booking-system.md) |
| 10 | Design a car rental system. | Rental OOD | [010-car-rental-system.md](./010-car-rental-system.md) |
| 11 | Design chess. | Game | [011-chess.md](./011-chess.md) |
| 12 | Design tic-tac-toe. | Game | [012-tic-tac-toe.md](./012-tic-tac-toe.md) |
| 13 | Design snake and ladders. | Game | [013-snake-and-ladders.md](./013-snake-and-ladders.md) |
| 14 | Design minesweeper. | Game | [014-minesweeper.md](./014-minesweeper.md) |
| 15 | Design tetris. | Game | [015-tetris.md](./015-tetris.md) |
| 16 | Design battleship. | Game | [016-battleship.md](./016-battleship.md) |
| 17 | Design blackjack. | Card game | [017-blackjack.md](./017-blackjack.md) |
| 18 | Design poker hand evaluator. | Card game | [018-poker-hand-evaluator.md](./018-poker-hand-evaluator.md) |
| 19 | Design a deck of cards library. | Reusable library | [019-deck-of-cards-library.md](./019-deck-of-cards-library.md) |
| 20 | Design a sudoku solver. | Algorithmic LLD | [020-sudoku-solver.md](./020-sudoku-solver.md) |
| 21 | Design an online shopping cart. | Commerce | [021-online-shopping-cart.md](./021-online-shopping-cart.md) |
| 22 | Design checkout flow. | Commerce workflow | [022-checkout-flow.md](./022-checkout-flow.md) |
| 23 | Design order management system. | Commerce workflow | [023-order-management-system.md](./023-order-management-system.md) |
| 24 | Design inventory management system. | Commerce | [024-inventory-management-system.md](./024-inventory-management-system.md) |
| 25 | Design coupon and discount engine. | Rules/pricing | [025-coupon-and-discount-engine.md](./025-coupon-and-discount-engine.md) |
| 26 | Design product catalog. | Commerce | [026-product-catalog.md](./026-product-catalog.md) |
| 27 | Design auction system. | Marketplace | [027-auction-system.md](./027-auction-system.md) |
| 28 | Design food ordering system. | Marketplace | [028-food-ordering-system.md](./028-food-ordering-system.md) |
| 29 | Design ride-sharing trip lifecycle. | Marketplace | [029-ride-sharing-trip-lifecycle.md](./029-ride-sharing-trip-lifecycle.md) |
| 30 | Design meeting room booking. | Scheduling | [030-meeting-room-booking.md](./030-meeting-room-booking.md) |
| 31 | Design payment processing system. | Fintech | [031-payment-processing-system.md](./031-payment-processing-system.md) |
| 32 | Design digital wallet. | Fintech | [032-digital-wallet.md](./032-digital-wallet.md) |
| 33 | Design banking ledger. | Fintech | [033-banking-ledger.md](./033-banking-ledger.md) |
| 34 | Design refund workflow. | Fintech workflow | [034-refund-workflow.md](./034-refund-workflow.md) |
| 35 | Design splitwise expense sharing. | Fintech/social | [035-splitwise-expense-sharing.md](./035-splitwise-expense-sharing.md) |
| 36 | Design invoice and billing system. | SaaS billing | [036-invoice-and-billing-system.md](./036-invoice-and-billing-system.md) |
| 37 | Design subscription management. | SaaS billing | [037-subscription-management.md](./037-subscription-management.md) |
| 38 | Design tax calculation service. | Finance rules | [038-tax-calculation-service.md](./038-tax-calculation-service.md) |
| 39 | Design expense approval system. | Enterprise finance | [039-expense-approval-system.md](./039-expense-approval-system.md) |
| 40 | Design fraud rule engine. | Risk | [040-fraud-rule-engine.md](./040-fraud-rule-engine.md) |
| 41 | Design LRU cache. | Data structure | [041-lru-cache.md](./041-lru-cache.md) |
| 42 | Design LFU cache. | Data structure | [042-lfu-cache.md](./042-lfu-cache.md) |
| 43 | Design TTL cache. | Data structure | [043-ttl-cache.md](./043-ttl-cache.md) |
| 44 | Design concurrent hash map. | Data structure | [044-concurrent-hash-map.md](./044-concurrent-hash-map.md) |
| 45 | Design hash map. | Data structure | [045-hash-map.md](./045-hash-map.md) |
| 46 | Design trie/autocomplete library. | Data structure | [046-trie-autocomplete-library.md](./046-trie-autocomplete-library.md) |
| 47 | Design rate limiter library. | Data structure/platform | [047-rate-limiter-library.md](./047-rate-limiter-library.md) |
| 48 | Design priority queue scheduler. | Data structure | [048-priority-queue-scheduler.md](./048-priority-queue-scheduler.md) |
| 49 | Design bloom filter service. | Data structure | [049-bloom-filter-service.md](./049-bloom-filter-service.md) |
| 50 | Design in-memory database. | Data structure/database | [050-in-memory-database.md](./050-in-memory-database.md) |
| 51 | Design thread pool. | Concurrency | [051-thread-pool.md](./051-thread-pool.md) |
| 52 | Design connection pool. | Resource management | [052-connection-pool.md](./052-connection-pool.md) |
| 53 | Design object pool. | Resource management | [053-object-pool.md](./053-object-pool.md) |
| 54 | Design retry library. | Resilience | [054-retry-library.md](./054-retry-library.md) |
| 55 | Design circuit breaker library. | Resilience | [055-circuit-breaker-library.md](./055-circuit-breaker-library.md) |
| 56 | Design distributed lock client. | Coordination | [056-distributed-lock-client.md](./056-distributed-lock-client.md) |
| 57 | Design job scheduler / cron library. | Scheduling | [057-job-scheduler-cron-library.md](./057-job-scheduler-cron-library.md) |
| 58 | Design workflow engine. | Orchestration | [058-workflow-engine.md](./058-workflow-engine.md) |
| 59 | Design event bus / pub-sub library. | Messaging | [059-event-bus-pub-sub-library.md](./059-event-bus-pub-sub-library.md) |
| 60 | Design message queue client. | Messaging | [060-message-queue-client.md](./060-message-queue-client.md) |
| 61 | Design URL shortener LLD. | API/product | [061-url-shortener.md](./061-url-shortener.md) |
| 62 | Design API gateway filter chain. | API/platform | [062-api-gateway-filter-chain.md](./062-api-gateway-filter-chain.md) |
| 63 | Design middleware pipeline. | API/platform | [063-middleware-pipeline.md](./063-middleware-pipeline.md) |
| 64 | Design feature flag SDK. | Platform SDK | [064-feature-flag-sdk.md](./064-feature-flag-sdk.md) |
| 65 | Design configuration service client. | Platform SDK | [065-configuration-service-client.md](./065-configuration-service-client.md) |
| 66 | Design logging framework. | Developer tool | [066-logging-framework.md](./066-logging-framework.md) |
| 67 | Design metrics library. | Observability SDK | [067-metrics-library.md](./067-metrics-library.md) |
| 68 | Design tracing SDK. | Observability SDK | [068-tracing-sdk.md](./068-tracing-sdk.md) |
| 69 | Design dependency injection container. | Framework | [069-dependency-injection-container.md](./069-dependency-injection-container.md) |
| 70 | Design plugin registry. | Extensibility | [070-plugin-registry.md](./070-plugin-registry.md) |
| 71 | Design file system. | Storage OOD | [071-file-system.md](./071-file-system.md) |
| 72 | Design text editor. | Editor | [072-text-editor.md](./072-text-editor.md) |
| 73 | Design spreadsheet. | Productivity | [073-spreadsheet.md](./073-spreadsheet.md) |
| 74 | Design calendar application. | Productivity | [074-calendar-application.md](./074-calendar-application.md) |
| 75 | Design meeting scheduler. | Productivity | [075-meeting-scheduler.md](./075-meeting-scheduler.md) |
| 76 | Design notification service LLD. | Productivity/platform | [076-notification-service.md](./076-notification-service.md) |
| 77 | Design email client model. | Productivity | [077-email-client-model.md](./077-email-client-model.md) |
| 78 | Design task management app. | Productivity | [078-task-management-app.md](./078-task-management-app.md) |
| 79 | Design document sharing permissions. | Collaboration | [079-document-sharing-permissions.md](./079-document-sharing-permissions.md) |
| 80 | Design collaborative whiteboard model. | Collaboration | [080-collaborative-whiteboard-model.md](./080-collaborative-whiteboard-model.md) |
| 81 | Design chat application LLD. | Communication | [081-chat-application.md](./081-chat-application.md) |
| 82 | Design group chat permissions. | Communication | [082-group-chat-permissions.md](./082-group-chat-permissions.md) |
| 83 | Design social network LLD. | Social | [083-social-network.md](./083-social-network.md) |
| 84 | Design news feed domain model. | Social/feed | [084-news-feed-domain-model.md](./084-news-feed-domain-model.md) |
| 85 | Design Instagram-like media post model. | Social/media | [085-instagram-like-media-post-model.md](./085-instagram-like-media-post-model.md) |
| 86 | Design music player. | Media | [086-music-player.md](./086-music-player.md) |
| 87 | Design video player state machine. | Media | [087-video-player-state-machine.md](./087-video-player-state-machine.md) |
| 88 | Design content moderation workflow. | Trust/safety | [088-content-moderation-workflow.md](./088-content-moderation-workflow.md) |
| 89 | Design review/rating system. | Social/commerce | [089-review-rating-system.md](./089-review-rating-system.md) |
| 90 | Design recommendation rule configuration. | Product/ML | [090-recommendation-rule-configuration.md](./090-recommendation-rule-configuration.md) |
| 91 | Design hospital management system. | Healthcare | [091-hospital-management-system.md](./091-hospital-management-system.md) |
| 92 | Design clinic appointment scheduler. | Healthcare | [092-clinic-appointment-scheduler.md](./092-clinic-appointment-scheduler.md) |
| 93 | Design restaurant management system. | Operations | [093-restaurant-management-system.md](./093-restaurant-management-system.md) |
| 94 | Design warehouse management system. | Operations | [094-warehouse-management-system.md](./094-warehouse-management-system.md) |
| 95 | Design access control system. | Security | [095-access-control-system.md](./095-access-control-system.md) |
| 96 | Design secrets manager LLD. | Security | [096-secrets-manager.md](./096-secrets-manager.md) |
| 97 | Design audit log library. | Security/compliance | [097-audit-log-library.md](./097-audit-log-library.md) |
| 98 | Design approval workflow system. | Enterprise workflow | [098-approval-workflow-system.md](./098-approval-workflow-system.md) |
| 99 | Design rule engine. | Enterprise rules | [099-rule-engine.md](./099-rule-engine.md) |
| 100 | Design form builder and validation engine. | Enterprise app | [100-form-builder-and-validation-engine.md](./100-form-builder-and-validation-engine.md) |
| 101 | Design Kafka / distributed event log. | Messaging / Streaming | [101-kafka-event-log.md](./101-kafka-event-log.md) |
