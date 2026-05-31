# Design Airline Reservation System - System Design Deep Dive

**Problem #70**  
**Category:** Booking/travel  
**Primary pattern:** fare inventory + PNR + ticketing + GDS  
**Deep-dive focus:** fare classes, PNR, ticketing, GDS, schedule changes

## 0. Interview Framing

Airline reservation requires fare rules, PNRs, ticket coupons, external host systems, and careful handling of ticketing failures.

Actors: travelers, airlines, GDS, payment providers, support agents. The highest-risk path is **search fares -> price itinerary -> create PNR -> issue ticket -> sync airline/GDS**. Keep the design centered there; move secondary work async unless it affects correctness, money, privacy, abuse prevention, or user-visible availability.

## 1. Requirements

### Functional Requirements

- Search flights by route/date/passengers/cabin and return priced offers.
- Create PNR with passengers, itinerary, fare, SSR, contacts, and payment.
- Issue tickets, assign seats, cancel, refund, exchange, and handle schedule changes.
- Integrate airline host/GDS for availability, booking, ticketing, and refunds.
- Expose support/admin operations to inspect, replay, correct, and annotate PNR history.
- Publish domain events for notifications, analytics, search, reconciliation, ML/risk, and support tooling.
- Support regional/cell-level degradation so unrelated markets, tenants, or products remain available.

### Non-Functional Requirements

- Final ticketing always revalidates host inventory.
- Fare/tax/rules snapshots are immutable.
- Search can be stale but booking path cannot trust it blindly.
- Every mutating API is idempotent and accepts an expected version or equivalent conflict guard.
- Source of truth: PNR/ticketing service plus airline host/GDS acknowledgement; caches, search indexes, dashboards, and read models are rebuildable projections.
- The design handles duplicate requests, duplicate callbacks, timeout, delayed events, and replay.
- PII, payment, identity, location, and regulated data are encrypted, access-controlled, audited, and retained by policy.
- The system provides operator-grade observability: traces, metrics, logs, audit trails, DLQs, and reconciliation reports.

### Non-Goals

- Do not design every UI screen; focus on backend contracts, ownership, data, and failure handling.
- Do not put analytics, notifications, emails, or search indexing on the synchronous correctness path.
- Do not keep scarce inventory, money movement, or security-sensitive decisions only in cache.
- Do not rely on distributed transactions across independently owned services; use sagas, outbox, and reconciliation.

## 2. Capacity, Traffic, And Size Estimation

Use interview-scale assumptions and state formulas so the interviewer can change the numbers.

| Dimension | Baseline Assumption |
| --- | --- |
| Search | 500K QPS global bursts |
| PNRs | 2M/day peak season |
| Inventory | flight x segment x fare_class |
| Provider calls | High latency, strict rate limits |
| Retention | PNR/ticket/tax multi-year |
| Peak QPS formula | peak = daily operations / 86,400 x burst multiplier |
| Event volume formula | events/day x average event size x replication x retention factor |
| Hot partition rule | dimension by tenant/region/entity/campaign, not only global average |

### Estimation Formulas

- Average QPS = daily operations / 86,400.
- Peak QPS = average QPS x product-specific burst multiplier.
- Storage/day = canonical writes/day x average row size x indexes x replication factor.
- Event log volume/day = events/day x average event size x retention multiplier.
- Cache memory = hot keys x average value size x replication x allocator overhead.
- External provider capacity = live requests + retries + callbacks + replay/backfill allowance.

### Sizing Notes

- Separate source-of-truth writes from read projections and analytics.
- Account for retries, callbacks, replay, and reconciliation in capacity, not only live requests.
- Keep the online PNR aggregate compact; move large payloads, documents, telemetry, and raw reports to object storage.
- Model hot keys separately from averages; region, tenant, campaign, show, driver, account, and instrument skew can dominate.
- Separate OLTP correctness storage from OLAP/reporting storage so analytics cannot starve live mutations.

## 3. API Design

Use REST for public/partner APIs, gRPC for internal services, and async events for propagation. Every mutation includes `Idempotency-Key`, `Authorization`, `client_request_id`, and optionally `expected_version`.

| API | Important Request Fields | Notes |
| --- | --- | --- |
| GET /v1/flights/search | origin, destination, dates, passengers | Cached offer search. |
| POST /v1/air/prices | offer_id, passengers | Revalidated priced offer. |
| POST /v1/pnrs | priced_offer_id, passengers, payment_method | Create PNR. |
| POST /v1/pnrs/{id}/ticket | expected_version | Issue e-ticket. |
| GET /v1/pnrs/{id} | path id, caller identity | Read canonical state or authorized projection. |
| POST /v1/admin/pnrs/{id}/reconcile | scope, dry_run, reason | Operator reconciliation with audit trail. |

### Internal APIs

```protobuf
service AirlineReservationService {
  rpc Create(CreateAirlineReservationRequest) returns (AirlineReservation);
  rpc Get(GetAirlineReservationRequest) returns (AirlineReservation);
  rpc Transition(TransitionAirlineReservationRequest) returns (AirlineReservation);
  rpc Reconcile(ReconcileAirlineReservationRequest) returns (ReconcileResult);
}

service PolicyService {
  rpc Evaluate(EvaluatePolicyRequest) returns (PolicyDecision);
}

service ProjectionService {
  rpc RebuildProjection(RebuildProjectionRequest) returns (RebuildProjectionResult);
}
```

### Error Model

- `400`: invalid request or unsupported transition.
- `401/403`: missing identity, policy denial, tenant mismatch, or partner authorization failure.
- `404`: resource not found or hidden by authorization.
- `409`: duplicate idempotency key with different payload, stale version, expired hold, or conflicting transition.
- `422`: business rule failure such as insufficient balance, unavailable inventory, invalid risk/KYC state, or policy denial.
- `429`: user, tenant, partner, device, IP, or endpoint quota exceeded.
- `5xx`: dependency/internal failure; return request ID and preserve retry-safe semantics.

## 4. Async Event Contracts

Use transactional outbox/inbox. Events are immutable, versioned, replayable, and partitioned by the aggregate that needs ordering.

```json
{
  "event_id": "evt_01H...",
  "event_type": "airline_reservation.state_changed.v1",
  "occurred_at": "2026-05-25T10:15:30Z",
  "producer": "airline_reservation-service",
  "tenant_or_region_id": "region_123",
  "aggregate_id": "PNR_123",
  "aggregate_version": 42,
  "idempotency_key": "idem_123",
  "actor": {"type": "user|partner|service|system", "id": "actor_123"},
  "payload_ref": "object://event-payloads/evt_01H..."
}
```

### Core Events

- airline_reservation.created.v1
- airline_reservation.validated.v1
- airline_reservation.state_changed.v1
- airline_reservation.committed.v1
- airline_reservation.failed.v1
- airline_reservation.reversed.v1
- airline_reservation.reconciliation_completed.v1
- airline_reservation.manual_review_required.v1

### Eventing Rules

- Partition by aggregate ID or natural ordering key; avoid global ordering requirements.
- Consumers are idempotent and store processed event IDs or aggregate versions.
- Sensitive payloads carry references, not raw secrets or unnecessary PII.
- Schema changes are additive first; breaking changes require a new event version.
- DLQs include owner, runbook, replay command, first failure, and last failure metadata.

## 5. High-Level Architecture

### Architecture Design

```text
Airline Reservation System Architecture

Actors / Clients / Partner Systems
        |
        v
DNS / Global Traffic Manager / CDN where useful
        |
        v
API Gateway / WAF / Auth / Rate Limits / Request Router
        |
        +--> Synchronous Command Path
        |       -> Fare search -> PNR service -> Idempotency service -> PNR and ticketing orchestrator -> State transition engine -> Schedule service
        |       -> Source-of-Truth Write + Transactional Outbox
        |
        +--> Query / Serving Path
        |       -> Fare search
        |       -> Canonical Store fallback when strong freshness is required
        |
        +--> Async/Event Path
        |       -> Event Bus / Stream Processing / Workflow Queues
        |       -> GDS adapter / Outbox/inbox workers / Admin/support console / Analytics/warehouse pipeline / Adapter manager / Reconciliation worker
        |
        +--> Operations Path
                -> Admin Console / Audit / Reconciliation / Backfill / Disaster Recovery

Data Stores: Canonical booking/order/inventory DB + availability/search cache + payment state + event log + warehouse
Ops/Integrations: Payment/risk + partner adapters + dispatch/fulfillment + reconciliation/support
```

### Request And Data Flow

1. **Request entry:** actors enter through edge controls that authenticate, authorize, rate-limit, route, and attach trace context before reaching the Airline Reservation System service boundary.
2. **Synchronous command path:** correctness-sensitive mutations stay inside Fare search -> PNR service -> Idempotency service -> PNR and ticketing orchestrator -> State transition engine -> Schedule service; this path performs validation, idempotency checks, source-of-truth writes, and outbox publication.
3. **Query path:** read-heavy traffic is served by Fare search; strong reads fall back to the canonical store when stale projections are unsafe.
4. **Async path:** GDS adapter / Outbox/inbox workers / Admin/support console / Analytics/warehouse pipeline / Adapter manager / Reconciliation worker consume committed events for notifications, indexing, analytics, provider calls, ML/risk feedback, cleanup, and reconciliation.
5. **Operations path:** admin, audit, replay, reconciliation, backfill, and disaster-recovery workflows are isolated from user-facing latency but use the same immutable event/audit history.

### Component Responsibilities

- **Schedule service**: flights, legs, aircraft, airports, schedule changes.
- **Fare search**: cached availability and offers.
- **PNR service**: passenger record and itinerary lifecycle.
- **Ticketing service**: e-ticket, exchange, void, refund.
- **GDS adapter**: provider rate limits, idempotency, references.
- **Idempotency service**: stores request hash, caller, endpoint, aggregate reference, and final response for safe retries.
- **Outbox/inbox workers**: publish committed domain events and dedupe consumed events.
- **Admin/support console**: offers timeline, replay, correction, escalation, and policy override workflows with audit.
- **Analytics/warehouse pipeline**: loads immutable events and snapshots for BI, ML, compliance, and cost reporting.

### Service Responsibility Matrix

| Layer | Services | Responsibility |
| --- | --- | --- |
| Edge/API boundary | API Gateway / WAF / Load Balancer | Authentication, authorization handoff, request validation, rate limits, routing, TLS termination, coarse abuse controls, and trace context propagation. |
| Core domain services | Fare search, PNR service, Idempotency service, PNR and ticketing orchestrator, State transition engine, Schedule service | Own Airline Reservation System business invariants, source-of-truth writes, state transitions, idempotency, and synchronous API responses. |
| Query/serving services | Fare search | Serve low-latency reads from caches, read models, indexes, or specialized serving stores while exposing freshness/consistency guarantees. |
| Async workers and integrations | GDS adapter, Outbox/inbox workers, Admin/support console, Analytics/warehouse pipeline, Adapter manager, Reconciliation worker | Consume committed events, call external systems, retry safely, update projections, run cleanup, and isolate slow dependencies from user-facing latency. |
| Data and governance | OLTP DB / cache / search index / object store / warehouse / audit log | Separate canonical state from derived stores; support rebuild, partitioning, retention, encryption, backup, and analytical access. |
| Operations | Admin console / reconciliation / observability / runbooks | Provide support investigation, replay/backfill, manual correction, compliance evidence, SLO dashboards, and incident response. |

## 6. Low-Level Design

### Core Services

- **PNR and ticketing orchestrator**: owns PNR state machine, policy checks, outbox events, and compensation.
- **Adapter manager**: normalizes provider/partner callbacks and retries.
- **State transition engine**: validates allowed PNR transitions using expected_version, policy decisions, and source-of-truth reads.
- **Reconciliation worker**: compares internal state, external provider reports, projections, ledger/audit rows, and emitted events.
- **Projection builder**: rebuilds search/read models from immutable events and snapshots after data loss or schema migration.

### Important Algorithms And Data Structures

- Use immutable event/audit records and rebuild projections from them.
- Use compare-and-swap transitions for contested aggregate updates.
- Use provider-specific idempotency references for every external call.
- Use transactional outbox so state changes and events commit together.
- Use optimistic concurrency for normal writes and short leases/fencing tokens for contested scarce resources.
- Use exponential backoff with jitter, DLQ, and replay tooling for external dependencies.
- Use deterministic policy/rule versions so old decisions can be explained during support or audit.

### State Machines

- Airline Reservation System: CREATED -> VALIDATED -> PENDING -> COMMITTED -> RECONCILED.
- Failure: PENDING -> FAILED -> COMPENSATION_PENDING -> REVERSED or MANUAL_REVIEW.
- External callback: RECEIVED -> DEDUPED -> APPLIED -> ACKED.

### Consistency Model

- Strong consistency for source-of-truth transitions, scarce inventory, funds/ledger, entitlement, identity, and policy gates.
- Eventual consistency for search, feed, notification, analytics, ML features, dashboards, and cache refresh.
- Optimistic concurrency with version columns for normal writes; leases/fencing for contested resources.
- Sagas with explicit compensation for multi-service workflows; no hidden distributed transaction.

## 7. Database Modeling And DB Design

### Canonical Tables

| Table | Primary Key / Important Columns | Purpose And Notes |
| --- | --- | --- |
| flights | flight_id, carrier, legs, departure_at, status | Schedule. |
| fare_classes | flight_id, segment_id, booking_class, available_count | Availability cache/allotment. |
| priced_offers | offer_id, itinerary, fare_snapshot, expires_at | Short-lived offer. |
| pnrs | pnr_id, external_ref, passenger_snapshot, state | Passenger record. |
| tickets | ticket_id, pnr_id, ticket_number, coupon_state | E-ticket. |
| idempotency_keys | caller_id, endpoint, idempotency_key, request_hash, aggregate_id, response_ref | Prevents duplicate mutation on client/provider retry. |
| domain_events | event_id, aggregate_id, aggregate_version, event_type, payload_ref | Outbox, replay, and audit event log. |
| audit_log | audit_id, actor_id, action, aggregate_id, before_hash, after_hash, reason | Immutable user/admin/service audit trail. |

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

### Platform Building Blocks And Microservice Patterns

Use these technologies only where they fit the access pattern and correctness boundary. A strong interview answer says what is on the synchronous hot path, what is asynchronous, what is derived, and what can be rebuilt.

| Concern | Recommended Building Blocks | How To Use In This Design | Key Interview Caveat |
| --- | --- | --- | --- |
| Hot-path caching | CDN, Redis Cluster, Memcached, local in-process cache, request coalescing, stale-while-revalidate | Cache hot reads, sessions, tokens, rate-limit counters, derived cards, and expensive computed views. Invalidate through events or short TTLs. | Never make cache the only source of truth for money, permissions, scarce inventory, or irreversible state. |
| Async processing | Kafka, Pulsar, Kinesis, RabbitMQ/SQS, transactional outbox/inbox, DLQ, retry with jitter | Move notifications, indexing, analytics, projections, provider calls, and slow side effects off the user-visible path. | Consumers must be idempotent; partition by aggregate when ordering matters. |
| Stream processing | Apache Flink, Kafka Streams, Spark Structured Streaming, Beam | Build rolling counters, fraud/risk signals, ranking features, ETA/features, alerting, and near-real-time materialized views. | Use event time, watermarks, replay, and exactly-once/effectively-once sinks only where the business needs it. |
| Batch jobs and workflows | Airflow, Dagster, Argo Workflows, Temporal, Cadence, Step Functions, Spark | Run backfills, reconciliation, compaction, expiry, report generation, settlement, lifecycle management, and ML feature generation. | Keep batch workers isolated from online capacity and make every job restartable and idempotent. |
| CDC and projections | Debezium, database CDC, Kafka Connect, outbox table relay | Feed search indexes, CQRS read models, lakehouse tables, caches, and audit pipelines from committed changes. | CDC is for propagation; business commands still go through domain services. |
| Event contracts | Schema Registry, Avro, Protobuf, JSON Schema, AsyncAPI, compatibility checks | Version domain events, enforce backward/forward compatibility, and document owners and consumers. | Breaking schema changes require new event versions and migration windows. |
| CQRS and read models | Command store, query projections, materialized views, search indexes | Keep canonical writes small and strongly owned; serve read-heavy views from projections optimized for query shape. | Expose freshness/version metadata and rebuild projections from events. |
| Microservice consistency patterns | Saga/process manager, transactional outbox, inbox dedupe, idempotency keys, compensating actions | Coordinate multi-service workflows without distributed transactions. | Make every state transition explicit and auditable; avoid hidden side effects. |
| Event storming and domain modeling | Commands, aggregates, events, policies, read models, bounded contexts | Identify aggregate owners, event names, invariants, side effects, and read projections before drawing service boxes. | Services should map to ownership boundaries, not arbitrary technical layers. |
| Object storage and lakehouse | S3/GCS/Azure Blob, Iceberg, Hudi, Delta Lake, Glue/Hive catalog | Store raw events, media, attachments, audit exports, feature data, and replayable history in immutable partitions. | Keep object/lake data partitioned by date/tenant/domain key and govern retention/privacy. |
| Analytics serving | Pinot, ClickHouse, Druid, Redshift, BigQuery, Snowflake, Athena/Trino/Presto | Serve dashboards, funnels, investigations, operational analytics, ad hoc SQL, and historical reports outside OLTP. | Do not run exploratory analytics against the primary transactional database. |
| Service runtime and governance | Spring Boot, Quarkus, Micronaut, Go/gRPC, Node.js, Kubernetes, service mesh, mTLS, API gateway, OpenTelemetry, config service, feature flags | Deploy independently, enforce auth, collect traces/metrics/logs, and roll out safely with canaries and kill switches. | More services increase operational load; split only when ownership, scale, or reliability justifies it. |

For this design, use Redis for quotes/availability/holds with canonical revalidation, Kafka/outbox for order lifecycle events, sagas/process managers for payment and fulfillment, Flink for fraud/ETA/marketplace signals, S3 + Iceberg for history, and Pinot/ClickHouse for operational dashboards.

Implementation rule: start with the simplest reliable building block, then introduce Kafka/Flink/lakehouse/OLAP/microservice patterns when scale, replay, ownership, or query shape demands them. Every added component must have a clear owner, SLO, retention policy, replay story, and failure mode.

### Data Integrity Rules

- Each mutating request records idempotency key, request hash, caller, endpoint, response, and aggregate ID.
- Each state transition checks expected version and allowed transition from current state.
- External callbacks are deduped by provider event/reference ID before changing domain state.
- Financial or entitlement corrections are compensating records, not destructive edits.
- Reconciliation reports must be explainable back to source rows, events, provider files, and operator actions.

## 8. Critical Flows

1. Search returns short-lived offers from schedule/fare cache.
2. Price revalidates fare rules/taxes.
3. PNR creation books host inventory, authorizes payment, and issues ticket.
4. Schedule change triggers re-accommodation or refund options.
5. Event publication: the aggregate write commits with an outbox event; publisher emits to the bus; consumers dedupe and update projections.
6. Reconciliation: scheduled worker compares source of truth with provider reports/read models/ledger and creates correction tasks for mismatches.
7. Operator correction: support action requires authorization, reason, expected version, immutable audit log, and compensating event.

## 9. Deep-Dive Focus Areas

- Host/GDS is often authoritative; local state is a projection with reconciliation.
- Ticketing can fail after payment, requiring void/refund/manual queue.
- Married segment logic prevents naive per-leg availability.
- Source-of-truth boundary: PNR/ticketing service plus airline host/GDS acknowledgement owns correctness; all low-latency read models are disposable projections.
- Idempotency boundary: key scope includes caller, endpoint, method, request hash, and business aggregate to prevent accidental replay with different payload.
- Consistency boundary: strong for money/inventory/security decisions; eventual for search, analytics, notifications, and dashboards.
- Replay boundary: events are versioned and payloads are immutable so projections and audit evidence can be rebuilt.

## 10. Scaling Bottlenecks And Mitigations

- Hot accounts/entities/campaigns create partition skew; use virtual shards and per-entity throttles.
- Provider timeouts create retry storms; isolate queues per provider.
- Backfills/replays must be throttled and observable.
- Hot tenants/entities can overload a shard; use virtual shards, adaptive throttles, and queue isolation.
- External dependencies can create retry storms; isolate queues per provider and apply circuit breakers plus load shedding.
- Large historical queries and exports run on analytical replicas/object-store snapshots, not primary OLTP.
- Backfills and replays are rate-limited and observable so they do not compete with live traffic.

## 11. Security, Privacy, Abuse Prevention, And Compliance

- Protect passport, identity, payment, and itinerary data.
- Detect card testing, fake bookings, loyalty takeover, refund fraud, and agency abuse.
- Use least-privilege RBAC/ABAC for users, partners, services, support, and break-glass access.
- Encrypt sensitive fields, rotate secrets, sign webhooks/callbacks, and tokenize payment/bank identifiers where applicable.
- Audit policy changes, manual overrides, exports, refunds/adjustments, and privileged reads.
- Run abuse detection on velocity, device, IP, account graph, payment instrument, partner behavior, and anomalous state transitions.

## 12. Reliability, Failure Modes, And Recovery

- Keep pending/unknown as explicit state on timeout.
- Reconcile internal state against provider reports and immutable events.
- Use replay to rebuild projections after bugs or schema migrations.
- Use durable queues for asynchronous work and DLQs with owner, retry policy, replay command, and runbook.
- If a dependency times out, keep the aggregate in explicit pending/unknown state and converge through callback, status poll, or reconciliation.
- Use backups plus event replay to recover projections; test restore and replay regularly.
- Prefer graceful degradation: pause risky mutations while preserving reads, active sessions, safety flows, and support access.

## 13. Deployment And Operations

- Deploy services independently behind API gateway routing with backward-compatible API and event schema versions.
- Use canary or blue/green deployments for orchestrators, risk/pricing engines, and provider adapters.
- Run schema migrations as expand-migrate-contract and keep rollback playbooks for hot paths.
- Use per-region feature flags, kill switches, and dependency circuit breakers.
- Maintain runbooks for backlog growth, provider outage, stuck aggregate, reconciliation mismatch, and data replay.

## 14. Observability: SLIs, SLOs, Dashboards, Alerts

- SLIs: PNR mutation success rate, read latency, transition error rate, idempotency replay rate, queue lag, and reconciliation mismatch rate.
- Dashboards by tenant, region, aggregate state, provider, dependency, app version, and release version.
- Alerts for stuck state machines, DLQ growth, provider error spikes, hot partitions, reconciliation drift, and p99 latency regressions.
- Distributed traces carry request_id, idempotency_key, aggregate_id, aggregate_version, and downstream provider reference.
- Audit dashboards expose manual overrides, policy changes, replay actions, and data export access.

## 15. Cost Model And Trade-Offs

- Provider/API fees, event/audit write amplification, search/index storage, and support workflows dominate cost.
- Cold history moves to object storage/warehouse; OLTP keeps working set compact.
- Primary cost drivers usually include write amplification from events/audit, provider/API fees, search/index storage, telemetry retention, and peak capacity.
- Move cold immutable history to object storage/warehouse and keep the OLTP working set compact.
- Cache hot read models with short TTL and explicit invalidation only where correctness is not compromised.
- Quantify trade-offs between latency, correctness, provider calls, operational support, and storage retention.

## 16. Key Trade-Offs

- Stronger correctness increases latency but prevents expensive business errors.
- Eventual read models scale but require pending/stale UX states.
- More fraud/risk checks reduce loss but increase false positives.
- Strong consistency on the core aggregate adds latency but prevents expensive business errors.
- Eventual consistency in projections improves scale but requires UX states for pending/stale data.
- Richer risk checks reduce losses but can increase false positives and support load.
- Provider abstraction simplifies product services but must not hide provider-specific edge cases needed for reconciliation.

## 17. Common Interview Follow-Ups

- How do you handle payment success but ticketing failure?
- Why can search availability be stale?
- How do schedule changes propagate?
- Where exactly is PNR source of truth stored?
- What happens when the external provider succeeds but the internal callback is delayed?
- How would you rebuild read models after a bad deployment?
- Which parts are strongly consistent and which are eventually consistent?

## 18. Final Interview Checklist

- Clarify scope, actors, success metrics, and the hottest correctness path before drawing components.
- Name the source of truth and the consistency boundary for the core aggregate.
- Show APIs, event contracts, HLD, LLD, data model, indexes, partitioning, and retention.
- Cover idempotency, state transitions, retries, reconciliation, and operator recovery.
- Discuss security, privacy, abuse, compliance, deployment, observability, and cost trade-offs.

## 19. World-Class Interview Review

### What A Strong Interview Answer Must Demonstrate

- **Correctness boundary:** PNR/ticketing service plus airline host/GDS acknowledgement is the authority; derived caches, search indexes, dashboards, and analytics must be rebuildable.
- **Hot path clarity:** start from `search fares -> price itinerary -> create PNR -> issue ticket -> sync airline/GDS` and walk the synchronous command path before discussing secondary features.
- **Service ownership:** explicitly assign responsibilities to Schedule service, Fare search, PNR service, Ticketing service, GDS adapter, Idempotency service; avoid vague boxes that do not own data or decisions.
- **Data ownership:** ground the design in `flights, fare_classes, priced_offers, pnrs, tickets, idempotency_keys` and explain partitioning, indexes, retention, and replay.
- **Event model:** use `airline_reservation.created.v1, airline_reservation.validated.v1, airline_reservation.state_changed.v1, airline_reservation.committed.v1, airline_reservation.failed.v1, airline_reservation.reversed.v1` to decouple slow work while preserving idempotency and ordering per aggregate.
- **Operational maturity:** include backpressure, DLQs, reconciliation, runbooks, audit trails, and safe manual correction.

### Bar-Raiser Drill-Down Prompts

- Which service owns the final decision for `search fares -> price itinerary -> create PNR -> issue ticket -> sync airline/GDS`, and what exact write makes it durable?
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
- Prove scarce inventory/assignment correctness before optimizing ranking.
- Show quote/hold/commit/cancel/refund lifecycle and partner timeout handling.
- Separate discovery freshness from checkout/source-of-truth validation.

### 5-Minute Whiteboard Structure

- First minute: scope actors, constraints, and `search fares -> price itinerary -> create PNR -> issue ticket -> sync airline/GDS`.
- Minutes 2-3: draw edge, command path, query path, async path, and data stores; name PNR and ticketing orchestrator, Adapter manager, State transition engine, Reconciliation worker, Projection builder.
- Minute 4: walk one critical flow and call out idempotency, consistency, and failure recovery.
- Minute 5: close with scale bottlenecks, security/privacy, observability, cost, and trade-offs.
