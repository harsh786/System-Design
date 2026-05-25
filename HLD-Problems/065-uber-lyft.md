# Design Uber / Lyft Ride-Hailing Platform - System Design Deep Dive

**Problem #65**  
**Category:** Marketplace/geo realtime  
**Primary pattern:** geo marketplace + dispatch + state machine  
**Deep-dive focus:** driver location ingestion, matching, surge pricing, trip state, payment, safety

## 0. Interview Framing

Ride hailing is a two-sided real-time marketplace where noisy driver location, volatile demand, and payment/safety workflows meet a strict dispatch latency budget.

Actors: riders, drivers, dispatch operators, payment providers, safety team. The highest-risk path is **quote -> match driver -> accept -> pickup -> complete trip without double-assignment or lost payment state**. Keep the design centered there; move secondary work async unless it affects correctness, money, privacy, abuse prevention, or user-visible availability.

## 1. Requirements

### Functional Requirements

- Riders request fare/ETA quotes by pickup, dropoff, product type, and payment method.
- Drivers stream location, availability, capacity, vehicle, and accept/decline decisions.
- Dispatch matches nearby eligible drivers using ETA, supply, acceptance probability, fairness, product constraints, and safety rules.
- Support trip lifecycle, live tracking, route deviation, masked contact, cancellation, ratings, receipt, and refunds.
- Pricing supports upfront fares, surge, tolls, wait time, promotions, and post-trip adjustments.
- Expose support/admin operations to inspect, replay, correct, and annotate trip history.
- Publish domain events for notifications, analytics, search, reconciliation, ML/risk, and support tooling.
- Support regional/cell-level degradation so unrelated markets, tenants, or products remain available.

### Non-Functional Requirements

- A driver capacity slot can be assigned to at most one active trip.
- Dispatch p99 should stay below 1-2 seconds in healthy regions.
- Driver location freshness and accuracy must be represented explicitly.
- Every mutating API is idempotent and accepts an expected version or equivalent conflict guard.
- Source of truth: Trip service plus driver_status assignment row; caches, search indexes, dashboards, and read models are rebuildable projections.
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
| Riders | 20M DAU, 100M MAU |
| Drivers | 5M registered, 500K online peak |
| Trip requests | 10M/day, 10x commute/weather burst |
| Location updates | 500K active drivers / 3 sec = 167K updates/sec |
| Dispatch offers | 1-5 offers per request |
| Retention | Location hot 24-72h, trip/payment/safety multi-year |
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

- Location updates are high-write short-retention telemetry; trip/payment/safety are long-retention.
- Partition by region/city and driver/trip IDs; do not average across commute hot spots.
- Keep the online trip aggregate compact; move large payloads, documents, telemetry, and raw reports to object storage.
- Model hot keys separately from averages; region, tenant, campaign, show, driver, account, and instrument skew can dominate.
- Separate OLTP correctness storage from OLAP/reporting storage so analytics cannot starve live mutations.

## 3. API Design

Use REST for public/partner APIs, gRPC for internal services, and async events for propagation. Every mutation includes `Idempotency-Key`, `Authorization`, `client_request_id`, and optionally `expected_version`.

| API | Important Request Fields | Notes |
| --- | --- | --- |
| POST /v1/rides/quotes | pickup, dropoff, product_type, payment_method_id | Returns fare, ETA, serviceability, quote_id, TTL. |
| POST /v1/rides | quote_id, pickup_note | Creates trip and enters matching. |
| POST /v1/drivers/{driver_id}/location | lat, lon, heading, speed, recorded_at | High-write telemetry path. |
| POST /v1/ride-offers/{offer_id}/decision | decision=ACCEPTED|DECLINED | First valid accept wins via fenced assignment. |
| POST /v1/rides/{ride_id}/transitions | expected_version, transition, evidence_ref | Trip state changes. |
| GET /v1/rides/{id} | path id, caller identity | Read canonical state or authorized projection. |
| POST /v1/admin/rides/{id}/reconcile | scope, dry_run, reason | Operator reconciliation with audit trail. |

### Internal APIs

```protobuf
service RideService {
  rpc Create(CreateRideRequest) returns (Ride);
  rpc Get(GetRideRequest) returns (Ride);
  rpc Transition(TransitionRideRequest) returns (Ride);
  rpc Reconcile(ReconcileRideRequest) returns (ReconcileResult);
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
  "event_type": "ride.state_changed.v1",
  "occurred_at": "2026-05-25T10:15:30Z",
  "producer": "ride-service",
  "tenant_or_region_id": "region_123",
  "aggregate_id": "trip_123",
  "aggregate_version": 42,
  "idempotency_key": "idem_123",
  "actor": {"type": "user|partner|service|system", "id": "actor_123"},
  "payload_ref": "object://event-payloads/evt_01H..."
}
```

### Core Events

- ride.created.v1
- ride.validated.v1
- ride.state_changed.v1
- ride.committed.v1
- ride.failed.v1
- ride.reversed.v1
- ride.reconciliation_completed.v1
- ride.manual_review_required.v1

### Eventing Rules

- Partition by aggregate ID or natural ordering key; avoid global ordering requirements.
- Consumers are idempotent and store processed event IDs or aggregate versions.
- Sensitive payloads carry references, not raw secrets or unnecessary PII.
- Schema changes are additive first; breaking changes require a new event version.
- DLQs include owner, runbook, replay command, first failure, and last failure metadata.

## 5. High-Level Architecture

### Architecture Design

```text
Uber / Lyft Ride-Hailing Platform Architecture

Actors / Clients / Partner Systems
        |
        v
DNS / Global Traffic Manager / CDN where useful
        |
        v
API Gateway / WAF / Auth / Rate Limits / Request Router
        |
        +--> Synchronous Command Path
        |       -> Geo ingestion -> Dispatch orchestrator -> Pricing/ETA service -> Trip service -> Safety service -> Idempotency service
        |       -> Source-of-Truth Write + Transactional Outbox
        |
        +--> Query / Serving Path
        |       -> Geo ingestion
        |       -> Canonical Store fallback when strong freshness is required
        |
        +--> Async/Event Path
        |       -> Event Bus / Stream Processing / Workflow Queues
        |       -> Outbox/inbox workers / Admin/support console / Analytics/warehouse pipeline / Location fanout / Reconciliation worker / Projection builder
        |
        +--> Operations Path
                -> Admin Console / Audit / Reconciliation / Backfill / Disaster Recovery

Data Stores: Canonical booking/order/inventory DB + availability/search cache + payment state + event log + warehouse
Ops/Integrations: Payment/risk + partner adapters + dispatch/fulfillment + reconciliation/support
```

### Request And Data Flow

1. **Request entry:** actors enter through edge controls that authenticate, authorize, rate-limit, route, and attach trace context before reaching the Uber / Lyft Ride-Hailing Platform service boundary.
2. **Synchronous command path:** correctness-sensitive mutations stay inside Geo ingestion -> Dispatch orchestrator -> Pricing/ETA service -> Trip service -> Safety service -> Idempotency service; this path performs validation, idempotency checks, source-of-truth writes, and outbox publication.
3. **Query path:** read-heavy traffic is served by Geo ingestion; strong reads fall back to the canonical store when stale projections are unsafe.
4. **Async path:** Outbox/inbox workers / Admin/support console / Analytics/warehouse pipeline / Location fanout / Reconciliation worker / Projection builder consume committed events for notifications, indexing, analytics, provider calls, ML/risk feedback, cleanup, and reconciliation.
5. **Operations path:** admin, audit, replay, reconciliation, backfill, and disaster-recovery workflows are isolated from user-facing latency but use the same immutable event/audit history.

### Component Responsibilities

- **Geo ingestion**: Creates upload sessions, validates chunks/checksums, writes originals to object storage, records metadata, and emits processing events.
- **Availability service**: tracks driver online state, capacity, cooldowns, and policy blocks.
- **Dispatch orchestrator**: selects candidates, sends offers, handles timeout, and commits assignment.
- **Pricing/ETA service**: computes upfront fare, surge, pickup ETA, route ETA, and post-trip fare.
- **Trip service**: owns trip state, versioned transitions, rider/driver timeline, and support notes.
- **Safety service**: handles SOS, route deviation, blocked pairs, and incident escalation.
- **Idempotency service**: stores request hash, caller, endpoint, aggregate reference, and final response for safe retries.
- **Outbox/inbox workers**: publish committed domain events and dedupe consumed events.
- **Admin/support console**: offers timeline, replay, correction, escalation, and policy override workflows with audit.
- **Analytics/warehouse pipeline**: loads immutable events and snapshots for BI, ML, compliance, and cost reporting.

### Service Responsibility Matrix

| Layer | Services | Responsibility |
| --- | --- | --- |
| Edge/API boundary | API Gateway / WAF / Load Balancer | Authentication, authorization handoff, request validation, rate limits, routing, TLS termination, coarse abuse controls, and trace context propagation. |
| Core domain services | Geo ingestion, Dispatch orchestrator, Pricing/ETA service, Trip service, Safety service, Idempotency service | Own Uber / Lyft Ride-Hailing Platform business invariants, source-of-truth writes, state transitions, idempotency, and synchronous API responses. |
| Query/serving services | Geo ingestion | Serve low-latency reads from caches, read models, indexes, or specialized serving stores while exposing freshness/consistency guarantees. |
| Async workers and integrations | Outbox/inbox workers, Admin/support console, Analytics/warehouse pipeline, Location fanout, Reconciliation worker, Projection builder | Consume committed events, call external systems, retry safely, update projections, run cleanup, and isolate slow dependencies from user-facing latency. |
| Data and governance | OLTP DB / cache / search index / object store / warehouse / audit log | Separate canonical state from derived stores; support rebuild, partitioning, retention, encryption, backup, and analytical access. |
| Operations | Admin console / reconciliation / observability / runbooks | Provide support investigation, replay/backfill, manual correction, compliance evidence, SLO dashboards, and incident response. |

## 6. Low-Level Design

### Core Services

- **Candidate generation**: queries S2/geohash cells and filters product/capacity/risk constraints.
- **Offer manager**: uses OFFERED leases and compare-and-swap driver_status transitions.
- **Location fanout**: pushes throttled significant tracking changes to rider/support.
- **State transition engine**: validates allowed trip transitions using expected_version, policy decisions, and source-of-truth reads.
- **Reconciliation worker**: compares internal state, external provider reports, projections, ledger/audit rows, and emitted events.
- **Projection builder**: rebuilds search/read models from immutable events and snapshots after data loss or schema migration.

### Important Algorithms And Data Structures

- Use S2/geohash cell expansion for nearby driver lookup.
- Rank drivers by pickup ETA, detour, acceptance probability, cancellation risk, fairness, and marketplace balance.
- Use hysteresis for surge multipliers to prevent oscillation.
- Smooth location with freshness/accuracy filters before exposing to riders.
- Use transactional outbox so state changes and events commit together.
- Use optimistic concurrency for normal writes and short leases/fencing tokens for contested scarce resources.
- Use exponential backoff with jitter, DLQ, and replay tooling for external dependencies.
- Use deterministic policy/rule versions so old decisions can be explained during support or audit.

### State Machines

- Trip: REQUESTED -> MATCHING -> OFFERED -> ACCEPTED -> DRIVER_ARRIVING -> IN_PROGRESS -> COMPLETED -> PAID.
- Driver: OFFLINE -> ONLINE -> OFFERED -> ON_TRIP -> COOLDOWN -> ONLINE.
- Payment: AUTH_REQUIRED -> AUTHORIZED -> CAPTURE_PENDING -> CAPTURED -> REFUNDED.

### Consistency Model

- Strong consistency for source-of-truth transitions, scarce inventory, funds/ledger, entitlement, identity, and policy gates.
- Eventual consistency for search, feed, notification, analytics, ML features, dashboards, and cache refresh.
- Optimistic concurrency with version columns for normal writes; leases/fencing for contested resources.
- Sagas with explicit compensation for multi-service workflows; no hidden distributed transaction.

## 7. Database Modeling And DB Design

### Storage Choices

- Relational OLTP for canonical aggregates, constraints, idempotency keys, and audit metadata.
- Distributed KV/wide-column store for high-write time series, hot counters, sessions, or location/score data where needed.
- Search/geo/vector index for discovery and filtering where the source of truth is elsewhere.
- Cache for hot projections, availability summaries, quotes, rate-limit state, and read-heavy timelines.
- Object storage for evidence, payloads, statements, attachments, model artifacts, and long-retention raw files.
- Warehouse/lakehouse for analytics, reconciliation, ML training, compliance reporting, and historical replay.

### Canonical Tables

| Table | Primary Key / Important Columns | Purpose And Notes |
| --- | --- | --- |
| drivers | driver_id, vehicle_id, verification_status, risk_flags | Driver identity and eligibility. |
| driver_status | driver_id, region_id, state, active_trip_id, version | Strong assignment capacity. |
| driver_locations_hot | driver_id, geocell, lat, lon, recorded_at, ttl | Hot geo lookup and tracking. |
| ride_quotes | quote_id, rider_id, pickup, dropoff, fare_snapshot, expires_at | Quote snapshot. |
| trips | trip_id, rider_id, driver_id, state, fare_snapshot, version | Trip aggregate. |
| ride_offers | offer_id, trip_id, driver_id, state, expires_at | Offer lifecycle. |
| payment_attempts | payment_id, trip_id, provider_ref, state | Payment lifecycle. |
| idempotency_keys | caller_id, endpoint, idempotency_key, request_hash, aggregate_id, response_ref | Prevents duplicate mutation on client/provider retry. |
| domain_events | event_id, aggregate_id, aggregate_version, event_type, payload_ref | Outbox, replay, and audit event log. |
| audit_log | audit_id, actor_id, action, aggregate_id, before_hash, after_hash, reason | Immutable user/admin/service audit trail. |

### Indexing, Partitioning, And Retention

- driver_locations_hot by geocell/time, trips by region_id + trip_id, trip_events by trip_id sequence.
- Partition canonical tables by tenant/region plus stable high-cardinality aggregate ID; use time buckets for append-heavy history.
- Build separate indexes for product reads and operator/support lookups so debugging does not overload hot user paths.
- Use TTL only for derived/replayable data; compliance, ledger, dispute, and audit records use explicit retention policy.
- Store large payloads, proofs, statements, files, and raw telemetry in object storage referenced from canonical rows.

### Data Integrity Rules

- Each mutating request records idempotency key, request hash, caller, endpoint, response, and aggregate ID.
- Each state transition checks expected version and allowed transition from current state.
- External callbacks are deduped by provider event/reference ID before changing domain state.
- Financial or entitlement corrections are compensating records, not destructive edits.
- Reconciliation reports must be explainable back to source rows, events, provider files, and operator actions.

## 8. Critical Flows

1. Quote calls ETA, pricing, surge, and serviceability.
2. Dispatch reads geo index, ranks candidates, sends offers, and commits first valid accept with driver_status CAS.
3. Trip start/end transitions update trip timeline, tracking visibility, fare, and payment capture.
4. Cancellation computes fee/refund, releases driver capacity, and optionally re-enters matching.
5. Event publication: the aggregate write commits with an outbox event; publisher emits to the bus; consumers dedupe and update projections.
6. Reconciliation: scheduled worker compares source of truth with provider reports/read models/ledger and creates correction tasks for mismatches.
7. Operator correction: support action requires authorization, reason, expected version, immutable audit log, and compensating event.

## 9. Deep-Dive Focus Areas

- Prevent double assignment with driver_status version and fencing token.
- Treat stale location as ineligible; do not match drivers beyond freshness SLA.
- Surge pricing should be explainable, capped, and auditable.
- Safety signals bypass normal queues and page the correct operations path.
- Source-of-truth boundary: Trip service plus driver_status assignment row owns correctness; all low-latency read models are disposable projections.
- Idempotency boundary: key scope includes caller, endpoint, method, request hash, and business aggregate to prevent accidental replay with different payload.
- Consistency boundary: strong for money/inventory/security decisions; eventual for search, analytics, notifications, and dashboards.
- Replay boundary: events are versioned and payloads are immutable so projections and audit evidence can be rebuilt.

## 10. Scaling Bottlenecks And Mitigations

- Location firehose can dominate write volume; separate hot state from raw telemetry.
- Hot city cells require independent dispatch shards and autoscaling.
- Low driver acceptance can create offer storms; widen radius and backpressure new requests.
- Hot tenants/entities can overload a shard; use virtual shards, adaptive throttles, and queue isolation.
- External dependencies can create retry storms; isolate queues per provider and apply circuit breakers plus load shedding.
- Large historical queries and exports run on analytical replicas/object-store snapshots, not primary OLTP.
- Backfills and replays are rate-limited and observable so they do not compete with live traffic.

## 11. Security, Privacy, Abuse Prevention, And Compliance

- Protect precise location, phone numbers, payment tokens, identity, and safety reports.
- Detect fake GPS, account takeover, collusion, referral abuse, cancellation fraud, and unsafe pairings.
- Use least-privilege RBAC/ABAC for users, partners, services, support, and break-glass access.
- Encrypt sensitive fields, rotate secrets, sign webhooks/callbacks, and tokenize payment/bank identifiers where applicable.
- Audit policy changes, manual overrides, exports, refunds/adjustments, and privileged reads.
- Run abuse detection on velocity, device, IP, account graph, payment instrument, partner behavior, and anomalous state transitions.

## 12. Reliability, Failure Modes, And Recovery

- If dispatch degrades, pause new requests per region while preserving active trip tracking and safety.
- If payment capture fails after trip, mark collection_pending and reconcile without losing ledger intent.
- If driver app disconnects, keep trip explicit and require recovery transition.
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

- SLIs: trip mutation success rate, read latency, transition error rate, idempotency replay rate, queue lag, and reconciliation mismatch rate.
- Dashboards by tenant, region, aggregate state, provider, dependency, app version, and release version.
- Alerts for stuck state machines, DLQ growth, provider error spikes, hot partitions, reconciliation drift, and p99 latency regressions.
- Distributed traces carry request_id, idempotency_key, aggregate_id, aggregate_version, and downstream provider reference.
- Audit dashboards expose manual overrides, policy changes, replay actions, and data export access.

## 15. Cost Model And Trade-Offs

- Major costs: location ingestion, maps/routing, WebSocket fanout, payment fees, telemetry retention.
- Cache ETA tiles/route segments and reserve exact routing for finalist candidates.
- Primary cost drivers usually include write amplification from events/audit, provider/API fees, search/index storage, telemetry retention, and peak capacity.
- Move cold immutable history to object storage/warehouse and keep the OLTP working set compact.
- Cache hot read models with short TTL and explicit invalidation only where correctness is not compromised.
- Quantify trade-offs between latency, correctness, provider calls, operational support, and storage retention.

## 16. Key Trade-Offs

- Sequential offers reduce driver spam but increase rider wait.
- Parallel offers improve match rate but require strict first-accept consistency.
- Precise location improves ETA and safety but raises privacy cost.
- Strong consistency on the core aggregate adds latency but prevents expensive business errors.
- Eventual consistency in projections improves scale but requires UX states for pending/stale data.
- Richer risk checks reduce losses but can increase false positives and support load.
- Provider abstraction simplifies product services but must not hide provider-specific edge cases needed for reconciliation.

## 17. Common Interview Follow-Ups

- How do you prevent one driver from accepting two rides?
- How do late/out-of-order location updates affect matching?
- How would you design surge pricing?
- Where exactly is trip source of truth stored?
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

- **Correctness boundary:** Trip service plus driver_status assignment row is the authority; derived caches, search indexes, dashboards, and analytics must be rebuildable.
- **Hot path clarity:** start from `quote -> match driver -> accept -> pickup -> complete trip without double-assignment or lost payment state` and walk the synchronous command path before discussing secondary features.
- **Service ownership:** explicitly assign responsibilities to Geo ingestion, Availability service, Dispatch orchestrator, Pricing/ETA service, Trip service, Safety service; avoid vague boxes that do not own data or decisions.
- **Data ownership:** ground the design in `drivers, driver_status, driver_locations_hot, ride_quotes, trips, ride_offers` and explain partitioning, indexes, retention, and replay.
- **Event model:** use `ride.created.v1, ride.validated.v1, ride.state_changed.v1, ride.committed.v1, ride.failed.v1, ride.reversed.v1` to decouple slow work while preserving idempotency and ordering per aggregate.
- **Operational maturity:** include backpressure, DLQs, reconciliation, runbooks, audit trails, and safe manual correction.

### Bar-Raiser Drill-Down Prompts

- Which service owns the final decision for `quote -> match driver -> accept -> pickup -> complete trip without double-assignment or lost payment state`, and what exact write makes it durable?
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

- First minute: scope actors, constraints, and `quote -> match driver -> accept -> pickup -> complete trip without double-assignment or lost payment state`.
- Minutes 2-3: draw edge, command path, query path, async path, and data stores; name Candidate generation, Offer manager, Location fanout, State transition engine, Reconciliation worker.
- Minute 4: walk one critical flow and call out idempotency, consistency, and failure recovery.
- Minute 5: close with scale bottlenecks, security/privacy, observability, cost, and trade-offs.
