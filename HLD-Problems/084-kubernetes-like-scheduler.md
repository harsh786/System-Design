# Design Kubernetes-like scheduler - System Design Deep Dive

**Problem #84**  
**Category:** Infrastructure  
**Primary pattern:** commerce booking  
**Deep-dive focus:** bin packing, constraints, priorities, preemption, failures

## 0. Interview Framing

A transactional product and marketplace system where inventory correctness, state machines, idempotency, payment boundaries, and partner integration matter most.

In an interview, start by narrowing the product scope, then anchor the design around the highest-risk path. For this problem, the highest-risk path is usually the path involving **bin packing**. Keep secondary capabilities asynchronous unless they affect correctness, money, privacy, or user-visible availability.

## 1. Requirements

### Functional Requirements

- Browse and search supply.
- Quote price and availability.
- Reserve scarce inventory with timeout.
- Complete payment and fulfillment with idempotent state transitions.
- Expose admin operations for investigation, replay, correction, and policy changes.
- Publish domain events for analytics, search, notifications, and downstream systems.
- Support regional failover and controlled degradation for non-critical features.

### Non-Functional Requirements

- prevent oversell or double-booking for scarce inventory.
- idempotent checkout and payment flows.
- clear state machine with compensating actions.
- search and browse remain available during write pressure.
- auditability for money and inventory decisions.

### Non-Goals

- Do not design every client UI screen; focus on backend, data, and platform contracts.
- Do not optimize rare administrative workflows ahead of the user-visible hot path.
- Do not reserve scarce inventory only in a cache.
- Do not couple payment provider callbacks directly to order state without idempotency.

## 2. Capacity, Traffic, And Size Estimation

Use these as interview-scale assumptions. State that numbers are adjustable and use formulas so the interviewer can change scale.

| Dimension | Baseline Assumption |
|---|---|
| Active users | 20M DAU, 100M MAU |
| Catalog/listings | 10M to 500M items depending on domain |
| Checkout/booking attempts | 5M/day, 20x flash-sale peak |
| Read/write mix | 95:5 browsing to mutation ratio |
| Latency target | p99 < 300 ms browse, p99 < 800 ms checkout orchestration |

### Estimation Formulas

- Average QPS = daily operations / 86,400.
- Peak QPS = average QPS x peak multiplier, usually 3x to 20x depending on virality or business events.
- Storage/day = write_count/day x average_record_size x replication_factor.
- Event log volume/day = events/day x average_event_size x retention_multiplier.
- Cache memory = hot_key_count x average_value_size x replication_factor x overhead_factor.
- Network egress = response_size x read_requests x cache_miss_or_delivery_factor.

### Sizing Notes

- Keep the online source-of-truth data model small; move large payloads, media, traces, and analytics to object storage or specialized stores.
- Partition before you need it. Pick a stable high-cardinality partition key and document how resharding works.
- Track hot partitions separately from total QPS. Most interview failures come from average estimates hiding hot keys, celebrity users, viral objects, or large tenants.

## 3. API Design

Use REST for public/admin APIs and gRPC for internal service-to-service calls. Every mutation accepts an idempotency key. Every list API supports cursor pagination, filtering, and a stable sort.

### Public APIs

```http
POST /v1/orders
Idempotency-Key: <uuid>
Authorization: Bearer <token>
Content-Type: application/json

{
  "client_request_id": "req_123",
  "attributes": {}
}
```

```http
GET /v1/orders/{id}
Authorization: Bearer <token>
```

```http
GET /v1/orders?cursor=<cursor>&limit=50&filter=<filter>&sort=<sort>
Authorization: Bearer <token>
```

```http
PATCH /v1/orders/{id}
Idempotency-Key: <uuid>
Content-Type: application/json

{
  "expected_version": 12,
  "changes": {}
}
```

```http
POST /v1/orders/{id}/actions/{action}
Idempotency-Key: <uuid>
Content-Type: application/json

{
  "reason": "operator_or_user_reason",
  "parameters": {}
}
```

### Domain-Specific API Examples

```http
POST /v1/orders/quotes
Idempotency-Key: <uuid>

{
  "buyer_id": "user_123",
  "items": [{"item_id": "item_123", "quantity": 1}],
  "currency": "USD"
}
```

```http
POST /v1/orders/reservations
Idempotency-Key: <uuid>

{"quote_id": "quote_123", "ttl_seconds": 900}
```

```http
POST /v1/orders/checkout
Idempotency-Key: <uuid>

{"reservation_id": "res_123", "payment_method_token": "tok_123"}
```

### Internal APIs

```protobuf
service OrderOrBookingService {
  rpc CreateOrderOrBooking(CreateOrderOrBookingRequest) returns (OrderOrBooking);
  rpc GetOrderOrBooking(GetOrderOrBookingRequest) returns (OrderOrBooking);
  rpc UpdateOrderOrBooking(UpdateOrderOrBookingRequest) returns (OrderOrBooking);
  rpc EvaluateOrderOrBooking(EvaluateOrderOrBookingRequest) returns (EvaluateOrderOrBookingResponse);
  rpc ListOrderOrBookingEvents(ListOrderOrBookingEventsRequest) returns (stream OrderOrBookingEvent);
}
```

### Error Model

- `400`: invalid request or unsupported transition.
- `401/403`: missing identity or policy denial.
- `404`: resource not found or intentionally hidden by authorization.
- `409`: version conflict, duplicate idempotency key with different payload, or state transition race.
- `429`: tenant/user/key quota exceeded with `Retry-After`.
- `5xx`: dependency or internal failure. Return a request ID for support and tracing.

## 4. Async Event Contracts

Use an outbox table or transactional event publisher so state changes and emitted events cannot diverge.

```json
{
  "event_id": "evt_01H...",
  "event_type": "orders.updated.v1",
  "occurred_at": "2026-05-25T10:15:30Z",
  "producer": "orders-service",
  "tenant_id": "tenant_123",
  "aggregate_id": "orderOrBooking_123",
  "aggregate_version": 13,
  "idempotency_key": "idem_123",
  "actor": {
    "type": "user|service|system",
    "id": "user_123"
  },
  "payload": {}
}
```

### Core Events

- `orders.created.v1`
- `orders.updated.v1`
- `orders.state_changed.v1`
- `orders.deleted_or_expired.v1`
- `orders.policy_denied.v1`
- `orders.operation_failed.v1`

## 5. High-Level Architecture

### Architecture Design

```text
Kubernetes-like scheduler Architecture

Actors / Clients / Partner Systems
        |
        v
DNS / Global Traffic Manager / CDN where useful
        |
        v
API Gateway / WAF / Auth / Rate Limits / Request Router
        |
        +--> Synchronous Command Path
        |       -> Cart or quote service -> Inventory availability service -> Reservation/hold service -> Order/booking orchestrator -> Catalog/search service
        |       -> Source-of-Truth Write + Transactional Outbox
        |
        +--> Query / Serving Path
        |       -> Catalog/search service
        |       -> Canonical Store fallback when strong freshness is required
        |
        +--> Async/Event Path
        |       -> Event Bus / Stream Processing / Workflow Queues
        |       -> Payment adapter / Fulfillment/partner integration / Notification service
        |
        +--> Operations Path
                -> Admin Console / Audit / Reconciliation / Backfill / Disaster Recovery

Data Stores: Config/metadata store + hot policy/cache/counter store + request/event audit log + metrics warehouse
Ops/Integrations: Control plane rollout + edge health checks + traffic shifting + abuse/rate-limit operations
```

### Request And Data Flow

1. **Request entry:** actors enter through edge controls that authenticate, authorize, rate-limit, route, and attach trace context before reaching the Kubernetes-like scheduler service boundary.
2. **Synchronous command path:** correctness-sensitive mutations stay inside Cart or quote service -> Inventory availability service -> Reservation/hold service -> Order/booking orchestrator -> Catalog/search service; this path performs validation, idempotency checks, source-of-truth writes, and outbox publication.
3. **Query path:** read-heavy traffic is served by Catalog/search service; strong reads fall back to the canonical store when stale projections are unsafe.
4. **Async path:** Payment adapter / Fulfillment/partner integration / Notification service consume committed events for notifications, indexing, analytics, provider calls, ML/risk feedback, cleanup, and reconciliation.
5. **Operations path:** admin, audit, replay, reconciliation, backfill, and disaster-recovery workflows are isolated from user-facing latency but use the same immutable event/audit history.

### Component Responsibilities

- **Catalog/search service**: Builds and serves query indexes from canonical events, supports ranking/filtering/facets, and tolerates bounded staleness.
- **Cart or quote service**: Computes user-facing quotes/estimates from current policy, availability, taxes/fees, discounts, and freshness/confidence metadata.
- **Inventory availability service**: Owns scarce availability state, holds/reservations, conflict checks, expiry, and reconciliation against derived projections.
- **Reservation/hold service**: Owns the core aggregate lifecycle, versioned state transitions, idempotency, compensation hooks, and domain event emission.
- **Order/booking orchestrator**: Owns the core aggregate lifecycle, versioned state transitions, idempotency, compensation hooks, and domain event emission.
- **Payment adapter**: Owns money state, provider interactions, ledger/audit records, idempotency, refunds/reversals, and reconciliation.
- **Fulfillment/partner integration**: Coordinates downstream partner/fulfillment actions, tracks acknowledgements, retries idempotently, and reconciles external state with internal orders.
- **Notification service**: Delivers push/email/SMS/in-app notifications using preferences, templates, priority queues, retries, and provider failover.

### Service Responsibility Matrix

| Layer | Services | Responsibility |
| --- | --- | --- |
| Edge/API boundary | API Gateway / WAF / Load Balancer | Authentication, authorization handoff, request validation, rate limits, routing, TLS termination, coarse abuse controls, and trace context propagation. |
| Core domain services | Cart or quote service, Inventory availability service, Reservation/hold service, Order/booking orchestrator, Catalog/search service | Own Kubernetes-like scheduler business invariants, source-of-truth writes, state transitions, idempotency, and synchronous API responses. |
| Query/serving services | Catalog/search service | Serve low-latency reads from caches, read models, indexes, or specialized serving stores while exposing freshness/consistency guarantees. |
| Async workers and integrations | Payment adapter, Fulfillment/partner integration, Notification service | Consume committed events, call external systems, retry safely, update projections, run cleanup, and isolate slow dependencies from user-facing latency. |
| Data and governance | OLTP DB / cache / search index / object store / warehouse / audit log | Separate canonical state from derived stores; support rebuild, partitioning, retention, encryption, backup, and analytical access. |
| Operations | Admin console / reconciliation / observability / runbooks | Provide support investigation, replay/backfill, manual correction, compliance evidence, SLO dashboards, and incident response. |

### Data Stores

- Catalog/listing store.
- Search index for browse/discovery.
- Cart/session store.
- Inventory/reservation store with strong consistency.
- Order/booking DB.
- Payment/outbox event log.

## 6. Low-Level Design

### Core Modules

- `OrderOrBookingController`: validates requests, extracts identity, enforces coarse rate limits, and maps errors to API responses.
- `OrderOrBookingApplicationService`: owns use-case orchestration, idempotency, retries, and state transitions.
- `OrderOrBookingDomainModel`: contains state machine rules, validation, and invariants that must not leak into controllers.
- `OrderOrBookingRepository`: hides database access, optimistic locking, partitioning, and pagination details.
- `OrderOrBookingPolicyEvaluator`: centralizes authorization, tenant isolation, quota, and abuse decisions.
- `OrderOrBookingEventPublisher`: writes outbox records and publishes domain events to the broker.
- `OrderOrBookingReadModelProjector`: builds caches, search documents, counters, and dashboard projections asynchronously.

### Interfaces

```java
interface OrderOrBookingRepository {
    Optional<OrderOrBooking> findById(OrderOrBookingId id, ReadConsistency consistency);
    Page<OrderOrBooking> list(OrderOrBookingQuery query, Cursor cursor, int limit);
    OrderOrBooking save(OrderOrBooking aggregate, ExpectedVersion expectedVersion);
}

interface OrderOrBookingPolicyEvaluator {
    PolicyDecision canRead(Principal principal, OrderOrBooking resource);
    PolicyDecision canMutate(Principal principal, OrderOrBooking resource, Action action);
}

interface IdempotencyStore {
    Optional<StoredResponse> find(String scope, String key, String requestHash);
    void reserve(String scope, String key, String requestHash, Instant expiresAt);
    void complete(String scope, String key, StoredResponse response);
}
```

### State Machine

```text
CREATED -> ACTIVE -> PAUSED -> ARCHIVED -> DELETED
   |         |          |          |
   |         |          |          -> RESTORE if policy allows
   |         |          -> ACTIVE after validation
   |         -> SUSPENDED by abuse/security workflow
   -> FAILED when creation side effects cannot complete
```

Adapt the state names to the domain, but always make transitions explicit, versioned, idempotent, and auditable.

## 7. Database Modeling And DB Design

### Logical Model

```text
Tenant/User
  -> owns or can access -> OrderOrBooking
  -> emits -> OrderOrBookingEvent
  -> produces -> ReadModel / SearchDocument / Metric
  -> audited by -> AuditLog
```

### Core Tables

| Table | Important Columns |
|---|---|
| `catalog_items` | `id, seller_id, title, attributes_json, price_ref, availability_state, updated_at` |
| `availability_units` | `id, item_id, location_or_slot, total_qty, available_qty, version, updated_at` |
| `reservations` | `id, item_id, user_id, qty, expires_at, state, fencing_token, created_at` |
| `orders` | `id, buyer_id, quote_ref, reservation_id, payment_id, state, version, created_at` |
| `payments` | `id, order_id, provider, amount, currency, state, idempotency_key, updated_at` |

### Database Technology Choice

| Workload / Data | Recommended Database / Store | Why This Choice Fits |
| --- | --- | --- |
| Source of truth / primary store | PostgreSQL/MySQL with strong transactions, or CockroachDB/Spanner for global inventory/order consistency; separate ledger DB for money if payments are in scope | orders, bookings, inventory holds, payments, and disputes require constraints, state machines, and auditability |
| Hot serving / cache | Redis Cluster for availability summaries, carts, quotes, seat/slot holds with TTL, dispatch candidates, and rate limits | keeps hot reads, sessions, counters, quotas, and derived views away from the OLTP source of truth |
| Event stream / outbox | Kafka/Pulsar/Kinesis with compacted topics for keys and retained topics for replay | decouples projections, notifications, analytics, search indexing, and recovery from the write path |
| Search / analytics | OpenSearch/Elasticsearch for discovery; ClickHouse/Druid/Pinot for marketplace, funnel, and operational analytics | serves text/filter/OLAP queries without overloading transactional tables |
| Large immutable payloads | object storage for invoices, tickets, contracts, images, proof, and support attachments | large or immutable data is cheaper, durable, and easier to lifecycle outside OLTP rows |

Interview stance: name the source-of-truth database first, then explicitly separate caches, indexes, event logs, and analytics stores. The cache, search index, and warehouse are derived systems; they must be rebuildable from canonical state and immutable events.

### Replication Strategy

- Primary store: multi-AZ synchronous or quorum replication for the primary store; asynchronous cross-region replicas for DR and read locality.
- Event log: replicate each partition across at least 3 brokers/nodes, require quorum acknowledgements for critical events, and monitor under-replicated partitions.
- Cache/read models: replicate for availability, but treat them as disposable; rebuild from source-of-truth rows plus events after corruption or cache loss.
- Object storage: use multi-AZ durability by default; enable cross-region replication only for disaster recovery, compliance, or locality requirements.
- Analytics/search stores: replicate shards for query availability, but recover by replaying events or rebuilding from snapshots when correctness is in doubt.

### Sharding And Partitioning Strategy

- Primary partition key: `market/city/tenant + aggregate_id; inventory_key for scarce resources; time bucket for transitions and audit`. Choose the key that matches the hottest write/read path, not just the entity name.
- Primary lookup path: `order_id/booking_id/reservation_id/listing_id` should be single-partition whenever possible.
- Time-partition append-heavy data such as events, audit logs, metrics, and delivery attempts so retention, archival, replay, and backfills do not scan the full corpus.
- Hot partition mitigation: serialize scarce inventory per resource, use short TTL holds, virtual shards for hot sellers/events, and queue isolation per market/provider.
- Keep tenant/cell/region boundaries explicit so one large customer, city, celebrity, event, or provider cannot overload the whole system.

### Indexing Strategy

- Required secondary indexes: `buyer_id + created_at, seller_id + created_at, inventory_key + state, state + expires_at, provider_reference`.
- Keep OLTP indexes minimal on high-write tables; move broad filtering, text search, ranking, and analytics to dedicated search/OLAP stores.
- Use composite indexes that match real query order: equality columns first, then range/sort columns such as `created_at`, `updated_at`, or `score`.
- For mutable state machines, index `(state, updated_at)` or `(state, next_attempt_at)` for workers and repair jobs.
- For audit and event tables, prefer append-only writes with time-bucketed partitions and compact indexes over many mutable secondary indexes.

### CAP Theorem And Consistency Choices

| Data / Operation | CAP Bias During Partition | Consistency Model | Interview Notes |
| --- | --- | --- | --- |
| Canonical command path | CP for scarce inventory and money-facing transitions | strong consistency for inventory holds, booking/order state, payment authorization, refunds, and entitlement issuance | Prefer rejecting or queuing unsafe writes over accepting divergent state. |
| Derived read models | AP/eventual for discovery, ETA/tracking projections, and read-only availability summaries with explicit staleness | Eventual consistency for search availability, recommendations, notifications, dashboards, tracking views, and analytics | Expose `pending`, `processing`, `stale_at`, or version metadata when users may observe lag. |
| Cache | AP with bounded TTL, unless used for a lock/fencing decision | Eventually consistent and invalidated by events or short TTL | Cache is never the only source of truth for correctness-critical state. |
| Search / analytics | AP/eventual | Asynchronous ingestion with replay/backfill | Results can lag; define freshness SLO and rebuild path. |
| Audit / ledger / immutable events | CP for append acceptance; replicated for durability | Append-only, immutable, replayable | Used for reconciliation, forensics, and projection rebuilds. |

### Data Lifecycle, Backups, And Rebuilds

- PITR backups, periodic restore drills, immutable event retention, and projection rebuilds from source-of-truth plus event log.
- Use transactional outbox or change-data-capture so database commits and emitted events cannot silently diverge.
- Define retention per data class: hot OLTP rows, warm history, cold object-store archives, legal holds, and deletion/anonymization workflows.
- Run checksum/control-total reconciliation between source-of-truth tables, event streams, search indexes, warehouses, and external providers.
- Document restore order: primary metadata first, immutable events second, object payloads third, then rebuild caches/search/read models.

## 8. Critical Flows

### Write / Mutation Flow

1. Client sends a mutation with authentication, idempotency key, and expected version when updating existing state.
2. API gateway applies coarse authentication, quotas, WAF rules, request size limits, and routing.
3. Application service validates input, checks policy, reserves idempotency key, and loads current aggregate state.
4. Domain model evaluates the transition and writes primary state plus outbox event in the same transaction.
5. Async workers publish events, update caches/search/read models, and invoke side effects.
6. Response returns the committed state, version, request ID, and retry-safe result.

### Read / Serving Flow

1. Client requests a resource or list endpoint with identity and cursor/filter parameters.
2. Service checks cache/read model for hot data and falls back to primary or search store when needed.
3. Authorization filters are applied before returning data, not only at ingestion time.
4. Response includes cache headers, pagination cursor, resource version, and trace/request ID.

### Replay / Recovery Flow

1. Identify the affected tenant, shard, time window, or aggregate IDs.
2. Pause dangerous side effects if replay can duplicate external calls.
3. Rebuild read models from the event log or primary source of truth.
4. Compare counts/checksums against expected control totals.
5. Resume normal processing and keep an audit note with operator, reason, and evidence.

## 9. Deep-Dive Focus Areas

- **bin packing**: Score placements by resource fit, constraints, affinity, and fragmentation.
- **constraints**: Represent hard constraints separately from soft preferences.
- **priorities**: Make priorities explicit in the data model, APIs, scaling plan, and operational dashboards.
- **preemption**: Preempt lower-priority work with disruption budgets and audit.
- **failures**: Make failures explicit in the data model, APIs, scaling plan, and operational dashboards.

## 10. Scaling Bottlenecks And Mitigations

| Bottleneck | Why It Happens | Mitigation |
|---|---|---|
| Hot partition or celebrity object | A small number of keys receives a disproportionate share of reads/writes. | Key splitting, local caches, write buffering, async aggregation, and hybrid fanout. |
| Synchronous dependency chain | User-visible request waits on too many downstream systems. | Move non-critical work to events, use timeouts, fallbacks, and circuit breakers. |
| Cache stampede | Popular key expires or is invalidated under high concurrency. | Soft TTL, request coalescing, jittered expiration, stale-while-revalidate. |
| Large tenant noisy neighbor | One tenant consumes shared pool capacity. | Per-tenant quotas, partitioning, fairness queues, and dedicated capacity for top tenants. |
| Reindex/rebuild pressure | Backfills or rebuilds compete with online serving. | Separate backfill pools, rate limits, shadow indexes, and atomic cutover. |
| Operational blind spots | Failures occur without enough context to debug. | Correlate logs, metrics, traces, audit events, and deployment versions. |

## 11. Security, Privacy, Abuse Prevention, And Compliance

- Authenticate every request with user, service, or device identity; use mTLS for internal service calls.
- Authorize by tenant, ownership, role, resource state, and contextual policy. Do not rely on front-end checks.
- Encrypt data in transit and at rest. Use tenant-scoped or domain-scoped keys for sensitive data.
- Store secrets in a managed vault and rotate credentials. Never log tokens, passwords, private keys, or raw sensitive payloads.
- Apply input validation, WAF rules, bot detection, rate limits, and abuse reputation checks.
- Keep immutable audit logs for administrative actions, policy decisions, state transitions, and data exports.
- Implement data retention, deletion, legal hold, and privacy export workflows if the domain stores personal data.
- Use least privilege for operators and services; require break-glass approvals for emergency access.

## 12. Reliability, Failure Modes, And Recovery

| Failure Mode | Impact | Recovery Strategy |
|---|---|---|
| Primary DB shard unavailable | Mutations for affected shard fail or degrade. | Multi-AZ failover, circuit breaker, queued writes only if semantics allow, clear user messaging. |
| Cache cluster loss | Higher latency and DB load. | Request coalescing, local cache, rate limiting, and progressive cache warmup. |
| Event broker lag | Search, analytics, notifications, or projections become stale. | Lag alerts, autoscale consumers, replay from offsets, and expose freshness to users/internal teams. |
| Region outage | Users in region lose access or move to remote region. | Global traffic failover, replicated critical data, documented RPO/RTO, and dependency evacuation runbooks. |
| Bad deployment or config | Elevated errors or wrong decisions. | Canary, automatic rollback, config version pinning, kill switches, and audit trail. |
| Poison message or corrupt record | Consumer stalls or produces bad projection. | DLQ, quarantine, schema validation, replay tooling, and repair jobs. |

## 13. Deployment And Operations

- Run stateless services on Kubernetes or an equivalent orchestrator across at least three availability zones.
- Use infrastructure as code for networking, IAM, databases, queues, caches, alarms, and dashboards.
- Deploy with canary or blue/green releases. Gate rollout on error rate, latency, saturation, and domain-specific correctness metrics.
- Apply backward-compatible database migrations: expand, dual-write/backfill if needed, verify, then contract.
- Separate control plane and data plane where the hot path must survive admin-plane outages.
- Use feature flags and kill switches for risky paths, expensive jobs, and external integrations.
- Maintain runbooks for failover, replay, data repair, provider outage, abuse incident, and privacy/security incident.

## 14. Observability: SLIs, SLOs, Dashboards, Alerts

### SLIs And SLOs

| Area | SLI | Example SLO |
|---|---|---|
| Availability | successful requests / total requests | 99.9% to 99.99% depending on product criticality |
| Latency | p50/p95/p99 by endpoint and tenant | p99 under the stated latency target for hot APIs |
| Correctness | duplicate, lost, or invalid state transitions | zero known correctness violations for critical workflows |
| Freshness | event lag, projection lag, index lag | 95% of projections within agreed freshness window |
| Durability | acknowledged writes later readable/replayable | no acknowledged write loss |
| Saturation | CPU, memory, queue depth, broker lag, DB connections | alert before user-visible impact |

### Dashboards

- API RED metrics: request rate, error rate, duration by endpoint, tenant, region, and deployment version.
- Dependency metrics: DB latency, cache hit ratio, broker lag, search latency, provider errors.
- Domain metrics: created/updated/deleted counts, state transition rates, policy denials, retries, DLQ depth.
- Capacity metrics: shard size, hot keys, queue depth, worker utilization, storage growth, egress.
- Security metrics: auth failures, suspicious IPs/devices, abuse reports, admin actions, data export/delete requests.

### Alerts

- Page on sustained SLO burn, correctness violations, write unavailability, severe broker lag, or security incidents.
- Ticket on slow capacity trends, moderate projection lag, rising retries, or low-priority DLQ growth.
- Suppress duplicate alerts through incident correlation and route to service owners with runbook links.

## 15. Cost Model And Trade-Offs

### Cost Drivers

- search index and cache size.
- reservation DB write capacity.
- partner API retries and queues.
- payment processing operations.
- fraud/risk checks and observability.

### Cost Formula

```text
monthly_cost = compute_hours
             + primary_storage_tb_months
             + replicated_storage_tb_months
             + cache_memory_gb_hours
             + event_log_retention_gb_months
             + search_or_olap_storage_tb_months
             + network_egress_tb
             + observability_ingest_gb
             + third_party_api_calls
```

Use current provider pricing during real planning. In interviews, explain the relative drivers and the levers rather than memorizing vendor-specific prices.

### Cost Controls

- Increase cache hit ratio and use request coalescing for expensive reads.
- Tier cold data to cheaper storage and compact event/log retention.
- Autoscale workers from queue depth and isolate expensive backfills from online traffic.
- Sample high-volume telemetry while retaining all errors, audits, and business-critical events.
- Use quotas and per-tenant budgets to prevent runaway cost.

## 16. Key Trade-Offs

| Decision | Option A | Option B | Interview Guidance |
|---|---|---|---|
| Consistency | Strong consistency | Eventual consistency | Use strong consistency for money, scarce inventory, access control, and metadata that gates safety; use eventual consistency for counters, feeds, analytics, and search. |
| Fanout/projection | Compute on write | Compute on read | Write-time projections reduce read latency but increase write amplification; read-time computation is flexible but can fail at peak. |
| Storage | Single general-purpose DB | Polyglot stores | Start simple, then split when access patterns, scale, or correctness boundaries justify it. |
| Multi-region | Active-passive | Active-active | Active-passive is simpler; active-active needs conflict handling, data residency design, and stronger operational maturity. |
| Build vs buy | Managed service | Custom platform | Buy undifferentiated primitives unless scale, cost, compliance, or product semantics require ownership. |

## 17. Common Interview Follow-Ups

- How does the design change at 10x traffic or with one extremely large tenant?
- Which data must be strongly consistent and which can lag?
- What is the exact partition key and how do you migrate when it becomes hot?
- How do you replay events or rebuild projections without duplicating side effects?
- What breaks during a regional outage and what is the expected RPO/RTO?
- How do you detect abuse, data leakage, or unauthorized access?
- What metrics prove the system is healthy from the user perspective?

## 18. Final Interview Checklist

- Clarify product scope and non-goals first.
- State scale assumptions and convert them into QPS, storage, bandwidth, and partition counts.
- Draw the read path, write path, async path, and operational path separately.
- Identify the source of truth for every entity and every derived view.
- Explain idempotency, retries, ordering, backpressure, and failure recovery.
- Cover security, privacy, compliance, deployment, observability, and cost before closing.

## 19. World-Class Interview Review

### What A Strong Interview Answer Must Demonstrate

- **Correctness boundary:** the canonical aggregate store and immutable event/audit history is the authority; derived caches, search indexes, dashboards, and analytics must be rebuildable.
- **Hot path clarity:** start from `bin packing` and walk the synchronous command path before discussing secondary features.
- **Service ownership:** explicitly assign responsibilities to Catalog/search service, Cart or quote service, Inventory availability service, Reservation/hold service, Order/booking orchestrator, Payment adapter; avoid vague boxes that do not own data or decisions.
- **Data ownership:** ground the design in `canonical aggregate, idempotency, event, and audit tables` and explain partitioning, indexes, retention, and replay.
- **Event model:** use `orders.created.v1, orders.updated.v1, orders.state_changed.v1, orders.deleted_or_expired.v1, orders.policy_denied.v1, orders.operation_failed.v1` to decouple slow work while preserving idempotency and ordering per aggregate.
- **Operational maturity:** include backpressure, DLQs, reconciliation, runbooks, audit trails, and safe manual correction.

### Bar-Raiser Drill-Down Prompts

- Which service owns the final decision for `bin packing`, and what exact write makes it durable?
- What is the idempotency key scope, and what happens if the same key is retried with a different payload?
- Which read paths can be stale, and which user actions must revalidate against the source of truth?
- What breaks during a dependency outage, and how does the system converge after callbacks or reports arrive late?
- Which metric would page the on-call engineer before user-visible correctness, data safety, or money correctness is impacted?

### Common Weak Answers To Avoid

- Drawing only a generic API -> service -> database diagram without ownership boundaries.
- Skipping idempotency, retries, duplicate callbacks, and reconciliation.
- Putting all features on the synchronous path and ignoring backpressure or degradation.
- Treating cache/search/analytics as source of truth for critical decisions.
- Listing databases without explaining partition key, consistency model, retention, and recovery.

### Domain-Specific Bar Raiser Notes
- Separate global routing/control plane from hot edge data plane.
- State rollout, health checks, policy propagation, and fail-open/fail-closed choices.
- Show how abuse/rate-limit decisions stay local and observable.

### 5-Minute Whiteboard Structure

- First minute: scope actors, constraints, and `bin packing`.
- Minutes 2-3: draw edge, command path, query path, async path, and data stores; name Catalog/search service, Cart or quote service, Inventory availability service, Reservation/hold service, Order/booking orchestrator, Payment adapter.
- Minute 4: walk one critical flow and call out idempotency, consistency, and failure recovery.
- Minute 5: close with scale bottlenecks, security/privacy, observability, cost, and trade-offs.
