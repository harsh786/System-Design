# System Design HLD Roadmap

_Split from `../world_class_pro_architect_master_roadmap.md`. The original source file is intentionally untouched._

Use the expanded practice banks here:

- [Top 100 System Design Problem Bank](41-system-design-top-100-problem-bank.md)
- [Top 300 System Design Concepts Interview Question Bank](44-system-design-concepts-top-300-interview-question-bank.md)

---

# 3. System Design Roadmap

## What You Must Master

### Requirements and Scope

- Functional vs non-functional requirements.
- Out-of-scope decisions.
- User personas and workflows.
- API consumers.
- Product constraints.
- Compliance constraints.

### Scale Estimation

- DAU, MAU, QPS, peak QPS.
- Read/write ratio.
- Storage per event/object.
- Bandwidth.
- Cache size.
- Partition count.
- Replication factor.
- Growth projection.

### API Design

- REST resources.
- gRPC services.
- Async event contracts.
- Idempotency keys.
- Pagination.
- Filtering and sorting.
- Versioning.
- Rate-limit headers.
- Error codes.

### Data Design

- Entities and relationships.
- Access patterns.
- Indexes.
- Partition keys.
- Consistency requirements.
- Retention and archival.
- Audit requirements.

### Scaling Patterns

- Horizontal scaling.
- Load balancing.
- Stateless services.
- Read replicas.
- Sharding.
- Caching.
- CDN.
- Queues.
- Stream processing.
- Materialized views.

### Reliability Patterns

- Timeout.
- Retry with jitter.
- Circuit breaker.
- Bulkhead.
- Fallback.
- Load shedding.
- Graceful degradation.
- Failover.
- Disaster recovery.

### Deep Practice Systems

- URL shortener.
- Rate limiter.
- Search autocomplete.
- Distributed cache.
- Notification system.
- Chat system.
- News feed.
- Media platform.
- Video streaming platform.
- File storage and sync.
- Payment system.
- Wallet and ledger.
- Trading system.
- Booking system.
- E-commerce platform.
- API gateway.
- Identity system.
- Feature flag platform.
- Observability platform.
- Real-time analytics platform.

## System Design Template

For the detailed live-interview template, use [`../HLD-Problems/HLD_INTERVIEW_TEMPLATE.md`](../HLD-Problems/HLD_INTERVIEW_TEMPLATE.md).

```text
1. Clarify scope
2. List functional requirements
3. List non-functional requirements
4. Estimate capacity
5. Define APIs
6. Define data model
7. Draw high-level design
8. Deep dive into bottlenecks
9. Handle failures
10. Add security
11. Add observability
12. Add deployment strategy
13. Discuss cost
14. Explain trade-offs
15. Explain migration path
```

---

# 4. Low-Level Design Roadmap


# 21. Top 50 System Design Problems by Category

Use this list for HLD practice. For every problem, produce requirements, scale estimates, APIs, data model, architecture, failure modes, observability, security, deployment, cost, and trade-offs.

For the expanded architect-level practice bank, use `41-system-design-top-100-problem-bank.md`.

| # | Problem | Category | Deep-Dive Focus |
| --- | --- | --- | --- |
| 1 | URL shortener | Core web scale | key generation, redirects, caching, analytics |
| 2 | Rate limiter | Edge/platform | token bucket, sliding window, distributed counters |
| 3 | API gateway | Platform | routing, auth, quotas, observability, canary |
| 4 | Load balancer | Infrastructure | L4/L7 routing, health checks, draining |
| 5 | CDN and static asset platform | Edge | cache invalidation, origin shielding, signed URLs |
| 6 | Distributed cache | Storage/platform | sharding, replication, eviction, hot keys |
| 7 | Distributed queue | Messaging | visibility timeout, retries, DLQ, ordering |
| 8 | Kafka-like event log | Streaming | partitions, replication, offsets, retention |
| 9 | Notification system | Product infra | fanout, preferences, retries, channels |
| 10 | Chat/messaging system | Realtime | WebSocket, ordering, presence, delivery receipts |
| 11 | WhatsApp/Signal-style messenger | Realtime/security | E2E encryption, device sync, media |
| 12 | News feed | Social | fanout-on-write/read, ranking, caching |
| 13 | Twitter/X timeline | Social | followers graph, ranking, celebrity users |
| 14 | Instagram/photo sharing | Social/media | media upload, feed, CDN, moderation |
| 15 | YouTube/video platform | Media | upload, transcoding, CDN, recommendations |
| 16 | Netflix/OTT streaming | Media | catalog, playback, DRM, regional CDN |
| 17 | Dropbox/Google Drive | Storage | chunks, sync, versioning, conflict resolution |
| 18 | Google Photos | Media/ML | dedupe, metadata search, thumbnailing |
| 19 | Search engine | Search | crawling, indexing, ranking, freshness |
| 20 | Autocomplete/typeahead | Search | trie, prefix index, ranking, latency |
| 21 | Web crawler | Search/data | frontier, politeness, dedupe, scheduling |
| 22 | E-commerce marketplace | Commerce | catalog, cart, order, inventory, payment |
| 23 | Shopping cart | Commerce | session state, pricing, inventory holds |
| 24 | Order management system | Commerce | state machine, saga, idempotency |
| 25 | Inventory reservation | Commerce | consistency, oversell prevention, locks |
| 26 | Payment gateway | Fintech | idempotency, PCI, retries, reconciliation |
| 27 | Digital wallet | Fintech | ledger, double-entry accounting, limits |
| 28 | Banking ledger | Fintech | correctness, audit, immutable entries |
| 29 | Fraud detection platform | Data/fintech | stream scoring, features, rules, feedback |
| 30 | Ride-hailing/Uber | Marketplace | matching, geo-indexing, surge, dispatch |
| 31 | Food delivery | Marketplace | order lifecycle, routing, partner integration |
| 32 | Hotel booking | Booking | availability, pricing, holds, overbooking |
| 33 | Movie ticket booking | Booking | seat locking, payment timeout, concurrency |
| 34 | Airline reservation | Booking | inventory classes, global distribution, consistency |
| 35 | Calendar scheduling | Productivity | recurrence, invites, conflict detection |
| 36 | Email service | Productivity | SMTP, inbox indexing, spam, storage |
| 37 | Collaborative document editing | Collaboration | CRDT/OT, presence, snapshots |
| 38 | Feature flag platform | Platform | targeting, consistency, SDK caching |
| 39 | Configuration service | Platform | versioning, rollout, watch, audit |
| 40 | Identity and access management | Security | auth, federation, RBAC, audit |
| 41 | Multi-tenant SaaS platform | SaaS | tenant isolation, quotas, billing, data partitioning |
| 42 | Metrics monitoring system | Observability | ingestion, aggregation, retention, alerting |
| 43 | Log aggregation platform | Observability | ingestion, indexing, storage tiers |
| 44 | Distributed tracing platform | Observability | trace ingestion, sampling, query |
| 45 | CI/CD platform | DevOps | pipeline execution, isolation, artifacts |
| 46 | Kubernetes-like scheduler | Infrastructure | scheduling constraints, bin packing, failures |
| 47 | IoT ingestion platform | IoT | device identity, MQTT, backpressure, time-series |
| 48 | Real-time analytics dashboard | Data | Kafka, Flink, OLAP serving, freshness |
| 49 | Recommendation system | ML/data | candidate generation, ranking, feedback loops |
| 50 | Data lakehouse platform | Data | S3, Iceberg/Hudi, Spark/Flink, governance |

---
