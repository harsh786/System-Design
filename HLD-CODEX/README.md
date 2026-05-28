# HLD-CODEX Complete System Design Solutions

This directory contains 116 complete system-design solutions in a Claude-style, interview-ready format. Claude-generated solution bodies are reused where available; the remaining problems are transformed from the existing deep-dive source material into the same solution-oriented structure.

Each solution is structured around requirements, capacity, data modeling, HLD, LLD, component deep dives, optimization, observability, trade-offs, and interview talking points.

## Category Map

| Folder | Count | Focus |
|---|---:|---|
| [Core Platform And Infrastructure](01-core-platform-infra/README.md) | 10 | Foundational distributed systems: URL shorteners, ID generation, caches, queues, logs, rate limiting, API gateway, DNS, and notification systems. |
| [Realtime Collaboration And Communication](02-realtime-collaboration/README.md) | 10 | Messaging, video calls, collaborative editing, presence, WebSocket fanout, ordering, and conflict resolution. |
| [Social Feeds And Graph Platforms](03-social-feeds-graphs/README.md) | 10 | Feeds, timelines, recommendations, social graphs, fanout, ranking, creator platforms, and high-scale engagement systems. |
| [Media, Content And Trust Systems](04-media-content-trust/README.md) | 10 | Media upload, processing, streaming, reviews, news feeds, copyright, abuse detection, and content moderation. |
| [Search, Geo And ML Platforms](05-search-geo-ml/README.md) | 10 | Search engines, geospatial indexing, autocomplete, personalization, recommendations, maps, crawlers, and ML feature systems. |
| [Storage And File Systems](06-storage-file-systems/README.md) | 10 | Object storage, distributed file systems, backup, metadata, sync, deduplication, replication, and durability tradeoffs. |
| [Commerce, Marketplace And Booking](07-commerce-marketplace-booking/README.md) | 13 | Catalogs, inventory, ordering, restaurants, travel, ticketing, auctions, promotions, and marketplace matching. |
| [Fintech, Payments And Ledgers](08-fintech-payments-ledgers/README.md) | 16 | Payments, wallets, banking, trading, brokerage, UPI, SIPs, holdings, ledgers, fraud, reconciliation, and compliance. |
| [Data, Workflow And Analytics](09-data-workflow-analytics/README.md) | 10 | ETL, stream processing, analytics stores, schedulers, orchestrators, feature stores, A/B testing, and experimentation. |
| [Infrastructure, Security And Observability](10-infra-security-observability/README.md) | 10 | Cloud infrastructure, container schedulers, CI/CD, monitoring, logging, secrets, auth, policy, and resilience platforms. |
| [Productivity, Ads And AI Platforms](11-productivity-messaging-ads-ai/README.md) | 7 | Calendar, email, ads, online judge, gaming leaderboard, webhook delivery, and LLM assistant backends. |

## Category Index

### Core Platform And Infrastructure

Foundational distributed systems: URL shorteners, ID generation, caches, queues, logs, rate limiting, API gateway, DNS, and notification systems.

- [001. TinyURL / Bitly URL shortener](01-core-platform-infra/001-tinyurl-bitly-url-shortener.md) - key generation, redirects, TTL, abuse prevention, analytics
- [002. Pastebin / GitHub Gist](01-core-platform-infra/002-pastebin-github-gist.md) - paste storage, expiration, privacy, syntax rendering, spam control
- [003. A rate limiter for APIs](01-core-platform-infra/003-rate-limiter-for-apis.md) - token bucket, sliding window, distributed counters, fairness
- [004. An API gateway](01-core-platform-infra/004-api-gateway.md) - routing, auth, quotas, throttling, canary, observability
- [005. A load balancer](01-core-platform-infra/005-load-balancer.md) - L4/L7 routing, health checks, consistent hashing, draining
- [006. A CDN and static asset platform](01-core-platform-infra/006-cdn-and-static-asset-platform.md) - edge cache, origin shield, invalidation, signed URLs, geo routing
- [007. A distributed cache like Redis/Memcached](01-core-platform-infra/007-distributed-cache-like-redis-memcached.md) - sharding, replication, eviction, hot keys, cache stampede
- [008. A distributed queue](01-core-platform-infra/008-distributed-queue.md) - visibility timeout, retries, DLQ, priority, ordering
- [009. A Kafka-like event log](01-core-platform-infra/009-kafka-like-event-log.md) - partitions, replication, offsets, retention, consumer groups
- [010. A unique ID generator like Snowflake](01-core-platform-infra/010-unique-id-generator-like-snowflake.md) - clock drift, sequence, region/worker IDs, monotonicity

### Realtime Collaboration And Communication

Messaging, video calls, collaborative editing, presence, WebSocket fanout, ordering, and conflict resolution.

- [011. WhatsApp / Signal messenger](02-realtime-collaboration/011-whatsapp-signal-messenger.md) - E2E encryption, device sync, offline delivery, media, receipts
- [012. Slack](02-realtime-collaboration/012-slack.md) - workspaces, channels, search, notifications, tenant isolation
- [013. Discord](02-realtime-collaboration/013-discord.md) - servers, channels, voice, presence, sharding, moderation
- [014. Facebook Messenger](02-realtime-collaboration/014-facebook-messenger.md) - group chat, online status, media sharing, delivery guarantees
- [015. WebSocket presence service](02-realtime-collaboration/015-websocket-presence-service.md) - heartbeats, connection registry, fanout, stale connection cleanup
- [016. A notification system](02-realtime-collaboration/016-notification-system.md) - email/SMS/push, preferences, templates, retries, priority
- [017. Zoom / video conferencing](02-realtime-collaboration/017-zoom-video-conferencing.md) - SFU vs MCU, WebRTC, screen share, recording, bandwidth adaptation
- [018. Google Docs collaborative editing](02-realtime-collaboration/018-google-docs-collaborative-editing.md) - CRDT/OT, cursor presence, conflict resolution, snapshots
- [019. A live comments system for a viral event](02-realtime-collaboration/019-live-comments-system-for-a-viral-event.md) - ordering, moderation, backpressure, websocket fanout
- [020. A customer-support chat platform](02-realtime-collaboration/020-customer-support-chat-platform.md) - routing agents, queues, transcripts, SLAs, escalation

### Social Feeds And Graph Platforms

Feeds, timelines, recommendations, social graphs, fanout, ranking, creator platforms, and high-scale engagement systems.

- [021. Twitter/X timeline](03-social-feeds-graphs/021-twitter-x-timeline.md) - followers graph, fanout, celebrity problem, ranking
- [022. Facebook News Feed](03-social-feeds-graphs/022-facebook-news-feed.md) - edge ranking, push vs pull, ML ranking, feed cache
- [023. Instagram](03-social-feeds-graphs/023-instagram.md) - photo upload, feed, stories, CDN, moderation
- [024. TikTok](03-social-feeds-graphs/024-tiktok.md) - video feed, recommendation, watch events, creator scale
- [025. Reddit](03-social-feeds-graphs/025-reddit.md) - subreddits, voting, hot/top/new ranking, moderation
- [026. LinkedIn](03-social-feeds-graphs/026-linkedin.md) - connection degrees, jobs feed, search, privacy
- [027. Pinterest](03-social-feeds-graphs/027-pinterest.md) - image boards, visual search, crawling, recommendations
- [028. Quora / Stack Overflow Q&A feed](03-social-feeds-graphs/028-quora-stack-overflow-q-and-a-feed.md) - topics, dedupe, voting, reputation, expert routing
- [029. A comments and reactions platform](03-social-feeds-graphs/029-comments-and-reactions-platform.md) - nested comments, counters, moderation, hot objects
- [030. A follow graph service](03-social-feeds-graphs/030-follow-graph-service.md) - adjacency storage, privacy, fanout, graph queries

### Media, Content And Trust Systems

Media upload, processing, streaming, reviews, news feeds, copyright, abuse detection, and content moderation.

- [031. YouTube](04-media-content-trust/031-youtube.md) - upload, transcoding, CDN, metadata, recommendations
- [032. Netflix / OTT streaming](04-media-content-trust/032-netflix-ott-streaming.md) - catalog, playback, DRM, regional CDN, resilience
- [033. Twitch live streaming](04-media-content-trust/033-twitch-live-streaming.md) - RTMP ingest, HLS/DASH, low latency, chat scale
- [034. Spotify](04-media-content-trust/034-spotify.md) - audio streaming, playlists, offline mode, recommendations
- [035. A podcast platform](04-media-content-trust/035-podcast-platform.md) - hosting, RSS, subscriptions, CDN, analytics
- [036. Google Photos](04-media-content-trust/036-google-photos.md) - dedupe, thumbnails, metadata search, albums, sharing
- [037. Instagram Stories / ephemeral media](04-media-content-trust/037-instagram-stories-ephemeral-media.md) - TTL, media processing, viewer receipts, ranking
- [038. A video transcoding platform](04-media-content-trust/038-video-transcoding-platform.md) - job queue, workers, retries, priority, cost control
- [039. A digital asset management platform](04-media-content-trust/039-digital-asset-management-platform.md) - metadata, access control, versioning, previews, search
- [040. A content moderation pipeline](04-media-content-trust/040-content-moderation-pipeline.md) - ML review, human review, queues, appeals, audit

### Search, Geo And ML Platforms

Search engines, geospatial indexing, autocomplete, personalization, recommendations, maps, crawlers, and ML feature systems.

- [041. Google Search at a high level](05-search-geo-ml/041-google-search-at-a-high-level.md) - crawling, indexing, ranking, freshness, serving
- [042. Autocomplete / typeahead](05-search-geo-ml/042-autocomplete-typeahead.md) - prefix index, trie, ranking, personalization, latency
- [043. A web crawler](05-search-geo-ml/043-web-crawler.md) - frontier, politeness, dedupe, scheduling, retries
- [044. Product search for Amazon](05-search-geo-ml/044-product-search-for-amazon.md) - inverted index, facets, ranking, availability, personalization
- [045. Yelp / nearby places](05-search-geo-ml/045-yelp-nearby-places.md) - geohash, quadtree, filtering, ranking, reviews
- [046. Google Maps](05-search-geo-ml/046-google-maps.md) - tiles, routing, traffic, ETA, offline maps
- [047. Ride ETA and route computation](05-search-geo-ml/047-ride-eta-and-route-computation.md) - graph routing, traffic updates, caching, freshness
- [048. A recommendation system](05-search-geo-ml/048-recommendation-system.md) - candidate generation, ranking, features, feedback loops
- [049. Image search](05-search-geo-ml/049-image-search.md) - embeddings, metadata, crawling, ranking, safety
- [050. Log search like Splunk/ELK](05-search-geo-ml/050-log-search-like-splunk-elk.md) - ingestion, indexing, retention, query latency

### Storage And File Systems

Object storage, distributed file systems, backup, metadata, sync, deduplication, replication, and durability tradeoffs.

- [051. Object storage like S3](06-storage-file-systems/051-object-storage-like-s3.md) - buckets, object metadata, durability, erasure coding, multipart upload
- [052. Dropbox](06-storage-file-systems/052-dropbox.md) - block sync, dedupe, conflict resolution, offline clients
- [053. Google Drive](06-storage-file-systems/053-google-drive.md) - permissions, sharing, versioning, sync, search
- [054. A distributed file system like GFS/HDFS](06-storage-file-systems/054-distributed-file-system-like-gfs-hdfs.md) - master metadata, chunk servers, replication, consistency
- [055. Backup and restore platform](06-storage-file-systems/055-backup-and-restore-platform.md) - snapshots, retention, restore tests, encryption, ransomware recovery
- [056. A photo/file metadata service](06-storage-file-systems/056-photo-file-metadata-service.md) - metadata indexing, ACLs, search, versioning
- [057. A file upload service for large files](06-storage-file-systems/057-file-upload-service-for-large-files.md) - multipart upload, resumability, checksums, malware scanning
- [058. A document versioning system](06-storage-file-systems/058-document-versioning-system.md) - immutable versions, diffs, conflict resolution, retention
- [059. A distributed key-value store](06-storage-file-systems/059-distributed-key-value-store.md) - consistent hashing, replication, quorum, vector clocks
- [060. A blob storage lifecycle manager](06-storage-file-systems/060-blob-storage-lifecycle-manager.md) - tiering, TTL, archival, deletion, compliance holds

### Commerce, Marketplace And Booking

Catalogs, inventory, ordering, restaurants, travel, ticketing, auctions, promotions, and marketplace matching.

- [061. Amazon e-commerce marketplace](07-commerce-marketplace-booking/061-amazon-e-commerce-marketplace.md) - catalog, cart, inventory, orders, payments, search
- [062. Shopping cart](07-commerce-marketplace-booking/062-shopping-cart.md) - session state, price changes, inventory holds, checkout
- [063. Order management system](07-commerce-marketplace-booking/063-order-management-system.md) - state machine, saga, idempotency, fulfillment
- [064. Inventory reservation system](07-commerce-marketplace-booking/064-inventory-reservation-system.md) - oversell prevention, locks, consistency, reconciliation
- [065. Uber / Lyft Ride-Hailing Platform](07-commerce-marketplace-booking/065-uber-lyft.md) - driver location ingestion, matching, surge pricing, trip state, payment, safety
- [066. DoorDash / Food Delivery Platform](07-commerce-marketplace-booking/066-doordash-food-delivery.md) - restaurant integration, menu freshness, order lifecycle, courier dispatch, ETA, refunds
- [067. Airbnb Home Rental Marketplace](07-commerce-marketplace-booking/067-airbnb.md) - listing search, calendar availability, pricing, booking, payouts, reviews, trust
- [068. Hotel Booking Platform](07-commerce-marketplace-booking/068-hotel-booking.md) - room inventory, rate plans, holds, PMS/channel sync, cancellation, overbooking
- [069. Movie Ticket Booking Like BookMyShow](07-commerce-marketplace-booking/069-movie-ticket-booking-like-bookmyshow.md) - seat discovery, locking, fairness, ticket issuance
- [070. Airline Reservation System](07-commerce-marketplace-booking/070-airline-reservation.md) - fare classes, PNR, ticketing, GDS, schedule changes
- [101. Zomato Food Delivery Platform](07-commerce-marketplace-booking/101-zomato-food-delivery-platform.md) - restaurant discovery, menu availability, order lifecycle, payment, delivery partner dispatch, ETA, real-time tracking, refunds, fraud
- [111. Parking Lot / Smart Parking Marketplace](07-commerce-marketplace-booking/111-parking-lot-smart-parking-marketplace.md) - spot discovery, reservations, sensors, gates, settlement
- [114. Auction / Bidding Platform](07-commerce-marketplace-booking/114-auction-bidding-platform.md) - bid validation, proxy bids, anti-sniping, payment, payout

### Fintech, Payments And Ledgers

Payments, wallets, banking, trading, brokerage, UPI, SIPs, holdings, ledgers, fraud, reconciliation, and compliance.

- [071. Payment Gateway Like Stripe](08-fintech-payments-ledgers/071-payment-gateway-like-stripe.md) - idempotency, PCI, authorization/capture/refund, webhooks, reconciliation
- [072. Digital Wallet](08-fintech-payments-ledgers/072-digital-wallet.md) - balances, top-up, transfer, withdrawal, KYC, fraud
- [073. Banking Ledger](08-fintech-payments-ledgers/073-banking-ledger.md) - chart of accounts, entries, snapshots, reversals, close, audit
- [074. Trading Platform](08-fintech-payments-ledgers/074-trading-platform.md) - order book, pre-trade risk, matching, market data, clearing
- [075. Fraud Detection Platform](08-fintech-payments-ledgers/075-fraud-detection-platform.md) - real-time scoring, feature freshness, rules, models, feedback
- [076. Billing And Subscription Platform](08-fintech-payments-ledgers/076-billing-and-subscription-platform.md) - plans, entitlements, metering, proration, invoices, dunning
- [077. Expense management system](08-fintech-payments-ledgers/077-expense-management-system.md) - receipt ingestion, policy checks, approvals, audit
- [078. Payout system for creators/drivers](08-fintech-payments-ledgers/078-payout-system-for-creators-drivers.md) - balances, KYC, payout rails, reconciliation
- [079. Tax calculation service](08-fintech-payments-ledgers/079-tax-calculation-service.md) - jurisdiction rules, versioning, audit, latency
- [080. Financial reporting pipeline](08-fintech-payments-ledgers/080-financial-reporting-pipeline.md) - batch close, ledger snapshots, controls, lineage
- [102. Mutual Fund / SIP Investment Platform](08-fintech-payments-ledgers/102-mutual-fund-sip-investment-platform.md) - KYC, SIP mandates, NAV allocation, RTA reconciliation, holdings
- [103. Stock Brokerage Like Zerodha / Robinhood](08-fintech-payments-ledgers/103-stock-brokerage-like-zerodha-robinhood.md) - order routing, risk/margin, executions, positions, settlement
- [104. UPI / Real-Time Bank Transfer System](08-fintech-payments-ledgers/104-upi-real-time-bank-transfer-system.md) - VPA resolution, debit/credit orchestration, callbacks, reversals
- [105. Portfolio Management And Holdings Aggregation](08-fintech-payments-ledgers/105-portfolio-management-and-holdings-aggregation.md) - connectors, holdings normalization, prices, analytics, consent
- [106. Splitwise / Expense Sharing](08-fintech-payments-ledgers/106-splitwise-expense-sharing.md) - expense splits, balance graph, simplification, settlement
- [110. Coupon, Loyalty, And Rewards Platform](08-fintech-payments-ledgers/110-coupon-loyalty-rewards-platform.md) - coupon issuance/redemption, reward ledger, loyalty tiers, abuse

### Data, Workflow And Analytics

ETL, stream processing, analytics stores, schedulers, orchestrators, feature stores, A/B testing, and experimentation.

- [081. Distributed cron / task scheduler](09-data-workflow-analytics/081-distributed-cron-task-scheduler.md) - recurring jobs, distributed locks, leases, retries, misfires
- [082. Batch job processing platform](09-data-workflow-analytics/082-batch-job-processing-platform.md) - job queues, worker pools, priority, retries, cost, isolation
- [083. Workflow engine like Airflow / Step Functions](09-data-workflow-analytics/083-workflow-engine-like-airflow-step-functions.md) - DAGs, state, retries, idempotency, backfills
- [084. Kubernetes-like scheduler](09-data-workflow-analytics/084-kubernetes-like-scheduler.md) - bin packing, constraints, priorities, preemption, failures
- [085. Real-time analytics dashboard](09-data-workflow-analytics/085-real-time-analytics-dashboard.md) - Kafka, stream processing, OLAP store, freshness
- [086. Data lakehouse platform](09-data-workflow-analytics/086-data-lakehouse-platform.md) - S3, Iceberg/Hudi/Delta, Spark/Flink, catalog, governance
- [087. ETL/ELT pipeline platform](09-data-workflow-analytics/087-etl-elt-pipeline-platform.md) - connectors, transformations, lineage, backfill, data quality
- [088. Metrics aggregation system](09-data-workflow-analytics/088-metrics-aggregation-system.md) - time-series ingestion, rollups, retention, alerts
- [089. IoT ingestion platform](09-data-workflow-analytics/089-iot-ingestion-platform.md) - device identity, MQTT, backpressure, time-series storage
- [090. Report generation system](09-data-workflow-analytics/090-report-generation-system.md) - scheduling, templates, long-running jobs, delivery, retries

### Infrastructure, Security And Observability

Cloud infrastructure, container schedulers, CI/CD, monitoring, logging, secrets, auth, policy, and resilience platforms.

- [091. Identity and access management](10-infra-security-observability/091-identity-and-access-management.md) - auth, federation, RBAC/ABAC, sessions, audit
- [092. Multi-tenant SaaS platform](10-infra-security-observability/092-multi-tenant-saas-platform.md) - tenant isolation, quotas, billing, data partitioning
- [093. Feature flag platform](10-infra-security-observability/093-feature-flag-platform.md) - targeting, SDK caching, rollout, consistency, audit
- [094. Configuration service](10-infra-security-observability/094-configuration-service.md) - versioning, watches, rollout, audit, consistency
- [095. CI/CD platform](10-infra-security-observability/095-ci-cd-platform.md) - pipeline execution, isolation, artifacts, secrets, approvals
- [096. Metrics monitoring system like Datadog](10-infra-security-observability/096-metrics-monitoring-system-like-datadog.md) - ingestion, aggregation, storage, dashboards, alerting
- [097. Distributed tracing platform](10-infra-security-observability/097-distributed-tracing-platform.md) - trace ingestion, sampling, correlation, query
- [098. Incident management / on-call platform](10-infra-security-observability/098-incident-management-on-call-platform.md) - alert routing, dedupe, escalation, postmortems
- [099. Distributed lock service like Chubby/ZooKeeper](10-infra-security-observability/099-distributed-lock-service-like-chubby-zookeeper.md) - consensus, leases, fencing tokens, sessions
- [100. Secrets management platform](10-infra-security-observability/100-secrets-management-platform.md) - encryption, rotation, access policy, audit, break-glass

### Productivity, Ads And AI Platforms

Calendar, email, ads, online judge, gaming leaderboard, webhook delivery, and LLM assistant backends.

- [107. Google Calendar / Calendar Scheduling](11-productivity-messaging-ads-ai/107-google-calendar-scheduling.md) - recurrence, attendees, reminders, free/busy, sync tokens
- [108. Gmail / Email System](11-productivity-messaging-ads-ai/108-gmail-email-system.md) - SMTP, spam, mailbox labels, threads, attachments, search
- [109. Ads Serving Platform](11-productivity-messaging-ads-ai/109-ads-serving-platform.md) - candidate selection, targeting, auction, pacing, frequency caps, attribution
- [112. Online Judge Like LeetCode](11-productivity-messaging-ads-ai/112-online-judge-like-leetcode.md) - problem catalog, sandboxing, tests, contests, plagiarism
- [113. Gaming Leaderboard / Tournament Platform](11-productivity-messaging-ads-ai/113-gaming-leaderboard-tournament-platform.md) - scores, ranks, seasons, tournaments, anti-cheat, rewards
- [115. Webhook Delivery Platform](11-productivity-messaging-ads-ai/115-webhook-delivery-platform.md) - endpoint registration, signing, retries, DLQ, ordering, replay
- [116. LLM Inference Platform / ChatGPT-Style Assistant Backend](11-productivity-messaging-ads-ai/116-llm-inference-platform-chatgpt-style-assistant.md) - streaming inference, context, tools, retrieval, safety, quotas, cost
