# Top 100 System Design Problem Bank For Architect Interviews

This is the expanded HLD practice bank for architect-role interviews. It builds on `02-system-design-hld.md`, which already contains the answer template and a top-50 list.

Goal:

> Practice enough problem shapes that any new system design interview can be reduced to known patterns: reads, writes, storage, fanout, realtime, scheduling, search, media, payments, consistency, observability, security, scale, and cost.

## How To Use This Bank

For every problem, produce:

1. Requirements and non-goals.
2. Scale estimates: DAU, QPS, peak QPS, storage, bandwidth, fanout, retention.
3. APIs and async event contracts.
4. Data model and access patterns.
5. High-level architecture.
6. Bottleneck deep dives.
7. Failure modes and recovery.
8. Security, abuse prevention, privacy, and compliance.
9. Observability: SLIs, SLOs, dashboards, alerts, traces, logs.
10. Cost and trade-offs.

Architect rule:

> Do not memorize one architecture per problem. Learn the core pattern each problem trains, then adapt it to the requirements.

---

# Pattern Coverage Map

| Pattern | Problems That Train It |
|---|---|
| key generation and redirects | URL shortener, Pastebin, object storage |
| cache hierarchy and invalidation | CDN, distributed cache, API gateway, feed, search |
| fanout and ranking | Twitter, news feed, Instagram, TikTok, LinkedIn |
| realtime delivery | WhatsApp, Slack, Discord, presence, collaborative editing |
| media pipelines | YouTube, Netflix, Twitch, Spotify, Zoom |
| distributed storage | S3, Dropbox, Google Drive, GFS, backup platform |
| search/indexing | search engine, autocomplete, log search, product search |
| geo/spatial systems | Uber, maps, nearby places, food delivery |
| booking and concurrency | hotel, airline, movie tickets, calendar, inventory |
| ledgers and money movement | payments, wallet, banking ledger, trading, fraud |
| batch and scheduling | cron, workflow engine, ETL, report generation, Kubernetes scheduler |
| stream processing | Kafka, analytics dashboard, fraud detection, IoT ingestion |
| multi-tenancy | Slack, SaaS platform, config service, identity, billing |
| observability | metrics, logs, tracing, alerting, incident platform |
| platform control planes | API gateway, feature flags, CI/CD, config, service discovery |

---

# Top 100 Problems By Interview Category

## 1. Core Web, Edge, And Platform Primitives

| # | Problem Statement | Category | Deep-Dive Focus |
|---|---|---|---|
| 1 | Design TinyURL / Bitly URL shortener. | Core web scale | key generation, redirects, TTL, abuse prevention, analytics |
| 2 | Design Pastebin / GitHub Gist. | Core web scale | paste storage, expiration, privacy, syntax rendering, spam control |
| 3 | Design a rate limiter for APIs. | Edge/platform | token bucket, sliding window, distributed counters, fairness |
| 4 | Design an API gateway. | Platform | routing, auth, quotas, throttling, canary, observability |
| 5 | Design a load balancer. | Infrastructure | L4/L7 routing, health checks, consistent hashing, draining |
| 6 | Design a CDN and static asset platform. | Edge | edge cache, origin shield, invalidation, signed URLs, geo routing |
| 7 | Design a distributed cache like Redis/Memcached. | Storage/platform | sharding, replication, eviction, hot keys, cache stampede |
| 8 | Design a distributed queue. | Messaging | visibility timeout, retries, DLQ, priority, ordering |
| 9 | Design a Kafka-like event log. | Streaming | partitions, replication, offsets, retention, consumer groups |
| 10 | Design a unique ID generator like Snowflake. | Platform | clock drift, sequence, region/worker IDs, monotonicity |

## 2. Realtime Messaging, Collaboration, And Communication

| # | Problem Statement | Category | Deep-Dive Focus |
|---|---|---|---|
| 11 | Design WhatsApp / Signal messenger. | Realtime/security | E2E encryption, device sync, offline delivery, media, receipts |
| 12 | Design Slack. | Collaboration/SaaS | workspaces, channels, search, notifications, tenant isolation |
| 13 | Design Discord. | Realtime/community | servers, channels, voice, presence, sharding, moderation |
| 14 | Design Facebook Messenger. | Realtime/social | group chat, online status, media sharing, delivery guarantees |
| 15 | Design WebSocket presence service. | Realtime infra | heartbeats, connection registry, fanout, stale connection cleanup |
| 16 | Design a notification system. | Product infra | email/SMS/push, preferences, templates, retries, priority |
| 17 | Design Zoom / video conferencing. | Realtime media | SFU vs MCU, WebRTC, screen share, recording, bandwidth adaptation |
| 18 | Design Google Docs collaborative editing. | Collaboration | CRDT/OT, cursor presence, conflict resolution, snapshots |
| 19 | Design a live comments system for a viral event. | Realtime/social | ordering, moderation, backpressure, websocket fanout |
| 20 | Design a customer-support chat platform. | SaaS/realtime | routing agents, queues, transcripts, SLAs, escalation |

## 3. Social Media, Feeds, And Consumer Networks

| # | Problem Statement | Category | Deep-Dive Focus |
|---|---|---|---|
| 21 | Design Twitter/X timeline. | Social/feed | followers graph, fanout, celebrity problem, ranking |
| 22 | Design Facebook News Feed. | Social/feed | edge ranking, push vs pull, ML ranking, feed cache |
| 23 | Design Instagram. | Social/media | photo upload, feed, stories, CDN, moderation |
| 24 | Design TikTok. | Social/video | video feed, recommendation, watch events, creator scale |
| 25 | Design Reddit. | Community/social | subreddits, voting, hot/top/new ranking, moderation |
| 26 | Design LinkedIn. | Professional graph | connection degrees, jobs feed, search, privacy |
| 27 | Design Pinterest. | Discovery/media | image boards, visual search, crawling, recommendations |
| 28 | Design Quora / Stack Overflow Q&A feed. | Knowledge/social | topics, dedupe, voting, reputation, expert routing |
| 29 | Design a comments and reactions platform. | Social infra | nested comments, counters, moderation, hot objects |
| 30 | Design a follow graph service. | Social graph | adjacency storage, privacy, fanout, graph queries |

## 4. Media Streaming, Content Delivery, And Creator Platforms

| # | Problem Statement | Category | Deep-Dive Focus |
|---|---|---|---|
| 31 | Design YouTube. | Media/video | upload, transcoding, CDN, metadata, recommendations |
| 32 | Design Netflix / OTT streaming. | Media/video | catalog, playback, DRM, regional CDN, resilience |
| 33 | Design Twitch live streaming. | Live media | RTMP ingest, HLS/DASH, low latency, chat scale |
| 34 | Design Spotify. | Media/audio | audio streaming, playlists, offline mode, recommendations |
| 35 | Design a podcast platform. | Media/audio | hosting, RSS, subscriptions, CDN, analytics |
| 36 | Design Google Photos. | Media/ML | dedupe, thumbnails, metadata search, albums, sharing |
| 37 | Design Instagram Stories / ephemeral media. | Social/media | TTL, media processing, viewer receipts, ranking |
| 38 | Design a video transcoding platform. | Batch/media | job queue, workers, retries, priority, cost control |
| 39 | Design a digital asset management platform. | Enterprise media | metadata, access control, versioning, previews, search |
| 40 | Design a content moderation pipeline. | Trust/safety | ML review, human review, queues, appeals, audit |

## 5. Search, Discovery, Geo, And Navigation

| # | Problem Statement | Category | Deep-Dive Focus |
|---|---|---|---|
| 41 | Design Google Search at a high level. | Search | crawling, indexing, ranking, freshness, serving |
| 42 | Design autocomplete / typeahead. | Search | prefix index, trie, ranking, personalization, latency |
| 43 | Design a web crawler. | Search/data | frontier, politeness, dedupe, scheduling, retries |
| 44 | Design product search for Amazon. | Search/commerce | inverted index, facets, ranking, availability, personalization |
| 45 | Design Yelp / nearby places. | Geo/search | geohash, quadtree, filtering, ranking, reviews |
| 46 | Design Google Maps. | Geo/navigation | tiles, routing, traffic, ETA, offline maps |
| 47 | Design ride ETA and route computation. | Geo/realtime | graph routing, traffic updates, caching, freshness |
| 48 | Design a recommendation system. | ML/data | candidate generation, ranking, features, feedback loops |
| 49 | Design image search. | Search/media | embeddings, metadata, crawling, ranking, safety |
| 50 | Design log search like Splunk/ELK. | Search/observability | ingestion, indexing, retention, query latency |

## 6. Storage, File Sync, Object Storage, And Backup

| # | Problem Statement | Category | Deep-Dive Focus |
|---|---|---|---|
| 51 | Design object storage like S3. | Storage | buckets, object metadata, durability, erasure coding, multipart upload |
| 52 | Design Dropbox. | File sync | block sync, dedupe, conflict resolution, offline clients |
| 53 | Design Google Drive. | File storage | permissions, sharing, versioning, sync, search |
| 54 | Design a distributed file system like GFS/HDFS. | Storage infra | master metadata, chunk servers, replication, consistency |
| 55 | Design backup and restore platform. | Reliability/storage | snapshots, retention, restore tests, encryption, ransomware recovery |
| 56 | Design a photo/file metadata service. | Storage metadata | metadata indexing, ACLs, search, versioning |
| 57 | Design a file upload service for large files. | Web/storage | multipart upload, resumability, checksums, malware scanning |
| 58 | Design a document versioning system. | Collaboration/storage | immutable versions, diffs, conflict resolution, retention |
| 59 | Design a distributed key-value store. | Storage infra | consistent hashing, replication, quorum, vector clocks |
| 60 | Design a blob storage lifecycle manager. | Storage/cost | tiering, TTL, archival, deletion, compliance holds |

## 7. Commerce, Booking, Marketplaces, And Inventory

| # | Problem Statement | Category | Deep-Dive Focus |
|---|---|---|---|
| 61 | Design Amazon e-commerce marketplace. | Commerce | catalog, cart, inventory, orders, payments, search |
| 62 | Design shopping cart. | Commerce | session state, price changes, inventory holds, checkout |
| 63 | Design order management system. | Commerce | state machine, saga, idempotency, fulfillment |
| 64 | Design inventory reservation system. | Commerce | oversell prevention, locks, consistency, reconciliation |
| 65 | Design Uber / Lyft. | Marketplace/geo | driver matching, location updates, surge pricing, dispatch |
| 66 | Design DoorDash / food delivery. | Marketplace/logistics | order lifecycle, restaurant integration, delivery routing, ETA |
| 67 | Design Airbnb. | Booking/marketplace | search, availability calendar, booking, pricing, reviews |
| 68 | Design hotel booking. | Booking | availability, holds, overbooking, pricing, cancellation |
| 69 | Design movie ticket booking like BookMyShow. | Booking | seat locking, payment timeout, fairness, concurrency |
| 70 | Design airline reservation. | Booking | fare classes, seat inventory, global distribution, consistency |

## 8. Payments, Ledger, Fintech, And Risk

| # | Problem Statement | Category | Deep-Dive Focus |
|---|---|---|---|
| 71 | Design payment gateway like Stripe. | Fintech | idempotency, PCI, retries, webhooks, reconciliation |
| 72 | Design digital wallet. | Fintech | ledger, limits, holds, transfers, fraud checks |
| 73 | Design banking ledger. | Fintech | double-entry accounting, audit, immutable entries, correctness |
| 74 | Design trading platform. | Fintech/low latency | order book, matching, market data, risk checks |
| 75 | Design fraud detection platform. | Risk/data | stream scoring, feature store, rules, model feedback |
| 76 | Design billing and subscription platform. | SaaS/fintech | plans, invoices, proration, retries, dunning |
| 77 | Design expense management system. | Enterprise fintech | receipt ingestion, policy checks, approvals, audit |
| 78 | Design payout system for creators/drivers. | Marketplace fintech | balances, KYC, payout rails, reconciliation |
| 79 | Design tax calculation service. | Commerce fintech | jurisdiction rules, versioning, audit, latency |
| 80 | Design financial reporting pipeline. | Finance/data | batch close, ledger snapshots, controls, lineage |

## 9. Data, Batch Jobs, Scheduling, And Analytics

| # | Problem Statement | Category | Deep-Dive Focus |
|---|---|---|---|
| 81 | Design distributed cron / task scheduler. | Scheduling | recurring jobs, distributed locks, leases, retries, misfires |
| 82 | Design batch job processing platform. | Batch infra | job queues, worker pools, priority, retries, cost, isolation |
| 83 | Design workflow engine like Airflow / Step Functions. | Orchestration | DAGs, state, retries, idempotency, backfills |
| 84 | Design Kubernetes-like scheduler. | Infrastructure | bin packing, constraints, priorities, preemption, failures |
| 85 | Design real-time analytics dashboard. | Data/realtime | Kafka, stream processing, OLAP store, freshness |
| 86 | Design data lakehouse platform. | Data platform | S3, Iceberg/Hudi/Delta, Spark/Flink, catalog, governance |
| 87 | Design ETL/ELT pipeline platform. | Data engineering | connectors, transformations, lineage, backfill, data quality |
| 88 | Design metrics aggregation system. | Observability/data | time-series ingestion, rollups, retention, alerts |
| 89 | Design IoT ingestion platform. | IoT/data | device identity, MQTT, backpressure, time-series storage |
| 90 | Design report generation system. | Batch/product | scheduling, templates, long-running jobs, delivery, retries |

## 10. Infrastructure, DevOps, Security, And Enterprise Platforms

| # | Problem Statement | Category | Deep-Dive Focus |
|---|---|---|---|
| 91 | Design identity and access management. | Security | auth, federation, RBAC/ABAC, sessions, audit |
| 92 | Design multi-tenant SaaS platform. | SaaS | tenant isolation, quotas, billing, data partitioning |
| 93 | Design feature flag platform. | Platform | targeting, SDK caching, rollout, consistency, audit |
| 94 | Design configuration service. | Platform | versioning, watches, rollout, audit, consistency |
| 95 | Design CI/CD platform. | DevOps | pipeline execution, isolation, artifacts, secrets, approvals |
| 96 | Design metrics monitoring system like Datadog. | Observability | ingestion, aggregation, storage, dashboards, alerting |
| 97 | Design distributed tracing platform. | Observability | trace ingestion, sampling, correlation, query |
| 98 | Design incident management / on-call platform. | SRE | alert routing, dedupe, escalation, postmortems |
| 99 | Design distributed lock service like Chubby/ZooKeeper. | Coordination | consensus, leases, fencing tokens, sessions |
| 100 | Design secrets management platform. | Security/platform | encryption, rotation, access policy, audit, break-glass |

---

# Category Practice Order

## First 20: Most Common Interview Starters

Practice these until you can solve them in 35-45 minutes:

- URL shortener
- Rate limiter
- API gateway
- Distributed cache
- Distributed queue
- Notification system
- Chat system
- WhatsApp
- News feed
- Twitter/X timeline
- Instagram
- YouTube
- Netflix
- Google Drive / Dropbox
- Object storage like S3
- Search engine
- Autocomplete
- E-commerce marketplace
- Payment gateway
- Uber / ride-hailing

## Next 30: Architect-Level Differentiators

These separate senior engineers from architects:

- Slack
- Discord
- Zoom
- Google Docs
- Twitch live streaming
- Content moderation
- Google Maps
- Recommendation system
- Distributed file system
- Backup and restore
- Order management
- Inventory reservation
- Banking ledger
- Fraud detection
- Distributed cron
- Batch job platform
- Workflow engine
- Kubernetes scheduler
- Real-time analytics dashboard
- Data lakehouse
- Identity and access management
- Multi-tenant SaaS
- Feature flags
- Config service
- CI/CD
- Metrics monitoring
- Distributed tracing
- Incident management
- Distributed lock service
- Secrets management
- cricbuzz
- Dream11
- Zomato
- QuickCommerce

---

# How To Generalize Any New Problem

When you see an unfamiliar problem, classify it by dominant pattern:

| If the problem is about... | Think of... |
|---|---|
| short IDs, redirects, metadata | URL shortener, Pastebin, object storage |
| many readers, few writers | CDN, cache, feed cache, search index |
| many writers, ordered events | Kafka, queue, log ingestion, chat |
| real-time user state | chat, presence, collaborative editing |
| huge media objects | YouTube, Netflix, S3, CDN |
| reservation or limited inventory | ticket booking, hotel, airline, inventory holds |
| money movement | payment gateway, wallet, ledger |
| ranking and personalization | feed, search, recommendation |
| geo proximity | Uber, Yelp, Google Maps |
| long-running work | batch jobs, workflow engine, transcoding |
| scheduled work | cron, report generation, Kubernetes scheduler |
| tenant isolation | Slack, SaaS platform, identity, billing |
| platform controls | API gateway, feature flags, config, CI/CD |
| reliability tooling | metrics, logs, tracing, incident platform |

Architect interview phrase:

> I first classify the system by access pattern, state model, consistency requirement, fanout, latency SLO, and failure blast radius. Then I choose storage, caching, queueing, sharding, and deployment strategy around those constraints.
