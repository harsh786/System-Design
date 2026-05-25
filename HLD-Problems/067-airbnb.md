# Design Airbnb Home Rental Marketplace - System Design Deep Dive

**Problem #67**  
**Category:** Booking/marketplace  
**Primary pattern:** search + availability calendar + booking hold + trust  
**Deep-dive focus:** listing search, calendar availability, pricing, booking, payouts, reviews, trust

## 0. Interview Framing

Airbnb-style booking protects scarce listing-night inventory while keeping search fast and trust workflows strong.

Actors: guests, hosts, trust team, payment providers, channel managers. The highest-risk path is **search -> quote stay -> hold nights -> confirm booking -> collect payment -> host payout**. Keep the design centered there; move secondary work async unless it affects correctness, money, privacy, abuse prevention, or user-visible availability.

## 1. Requirements

### Functional Requirements

- Guests search listings by geo, dates, guests, price, amenities, cancellation policy, and rating.
- Hosts manage listings, photos, house rules, calendar, seasonal pricing, discounts, taxes, and acceptance mode.
- Guests quote, hold, instant-book or request-to-book, pay, cancel, message, and review.
- Calendar sync integrates iCal/channel managers and resolves conflicts.
- Trust workflows handle identity, fraud, party risk, disputes, and damage claims.
- Expose support/admin operations to inspect, replay, correct, and annotate booking history.
- Publish domain events for notifications, analytics, search, reconciliation, ML/risk, and support tooling.
- Support regional/cell-level degradation so unrelated markets, tenants, or products remain available.

### Non-Functional Requirements

- A listing-night can be committed to at most one booking.
- Search availability can be stale; checkout revalidates canonical calendar.
- Price, tax, and cancellation policy snapshots are immutable after booking.
- Every mutating API is idempotent and accepts an expected version or equivalent conflict guard.
- Source of truth: Booking service plus listing_calendar_days; caches, search indexes, dashboards, and read models are rebuildable projections.
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
| Guests | 50M MAU, seasonal spikes |
| Listings | 10M active listings |
| Calendar rows | listing_id x date, billions/year |
| Search | 200K QPS avg, 1M peak |
| Booking attempts | 2M/day, 20x holidays |
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

- Listing-day inventory is large but simple; compact cold history.
- Search availability is derived and can be stale.
- Keep the online booking aggregate compact; move large payloads, documents, telemetry, and raw reports to object storage.
- Model hot keys separately from averages; region, tenant, campaign, show, driver, account, and instrument skew can dominate.
- Separate OLTP correctness storage from OLAP/reporting storage so analytics cannot starve live mutations.

## 3. API Design

Use REST for public/partner APIs, gRPC for internal services, and async events for propagation. Every mutation includes `Idempotency-Key`, `Authorization`, `client_request_id`, and optionally `expected_version`.

| API | Important Request Fields | Notes |
| --- | --- | --- |
| GET /v1/listings/search | location, dates, guests, filters, cursor | Geo/date/facet discovery. |
| POST /v1/stays/quote | listing_id, date_range, guests, coupon | Returns price/policy snapshot. |
| POST /v1/stays/bookings | quote_id, payment_method_id, message | Creates booking or request. |
| POST /v1/host/bookings/{booking_id}/decision | decision | Host accept/decline. |
| PATCH /v1/listings/{listing_id}/calendar | date/range, availability, price, expected_version | Host calendar update. |
| GET /v1/bookings/{id} | path id, caller identity | Read canonical state or authorized projection. |
| POST /v1/admin/bookings/{id}/reconcile | scope, dry_run, reason | Operator reconciliation with audit trail. |

### Internal APIs

```protobuf
service StayBookingService {
  rpc Create(CreateStayBookingRequest) returns (StayBooking);
  rpc Get(GetStayBookingRequest) returns (StayBooking);
  rpc Transition(TransitionStayBookingRequest) returns (StayBooking);
  rpc Reconcile(ReconcileStayBookingRequest) returns (ReconcileResult);
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
  "event_type": "stay_booking.state_changed.v1",
  "occurred_at": "2026-05-25T10:15:30Z",
  "producer": "stay_booking-service",
  "tenant_or_region_id": "region_123",
  "aggregate_id": "booking_123",
  "aggregate_version": 42,
  "idempotency_key": "idem_123",
  "actor": {"type": "user|partner|service|system", "id": "actor_123"},
  "payload_ref": "object://event-payloads/evt_01H..."
}
```

### Core Events

- stay_booking.created.v1
- stay_booking.validated.v1
- stay_booking.state_changed.v1
- stay_booking.committed.v1
- stay_booking.failed.v1
- stay_booking.reversed.v1
- stay_booking.reconciliation_completed.v1
- stay_booking.manual_review_required.v1

### Eventing Rules

- Partition by aggregate ID or natural ordering key; avoid global ordering requirements.
- Consumers are idempotent and store processed event IDs or aggregate versions.
- Sensitive payloads carry references, not raw secrets or unnecessary PII.
- Schema changes are additive first; breaking changes require a new event version.
- DLQs include owner, runbook, replay command, first failure, and last failure metadata.

## 5. High-Level Architecture

### Architecture Design

```text
Airbnb Home Rental Marketplace Architecture

Actors / Clients / Partner Systems
        |
        v
DNS / Global Traffic Manager / CDN where useful
        |
        v
API Gateway / WAF / Auth / Rate Limits / Request Router
        |
        +--> Synchronous Command Path
        |       -> Calendar service -> Pricing service -> Booking service -> Idempotency service -> State transition engine -> Listing service
        |       -> Source-of-Truth Write + Transactional Outbox
        |
        +--> Query / Serving Path
        |       -> Listing service / Search service
        |       -> Canonical Store fallback when strong freshness is required
        |
        +--> Async/Event Path
        |       -> Event Bus / Stream Processing / Workflow Queues
        |       -> Outbox/inbox workers / Admin/support console / Analytics/warehouse pipeline / Reconciliation worker / Projection builder
        |
        +--> Operations Path
                -> Admin Console / Audit / Reconciliation / Backfill / Disaster Recovery

Data Stores: Canonical booking/order/inventory DB + availability/search cache + payment state + event log + warehouse
Ops/Integrations: Payment/risk + partner adapters + dispatch/fulfillment + reconciliation/support
```

### Request And Data Flow

1. **Request entry:** actors enter through edge controls that authenticate, authorize, rate-limit, route, and attach trace context before reaching the Airbnb Home Rental Marketplace service boundary.
2. **Synchronous command path:** correctness-sensitive mutations stay inside Calendar service -> Pricing service -> Booking service -> Idempotency service -> State transition engine -> Listing service; this path performs validation, idempotency checks, source-of-truth writes, and outbox publication.
3. **Query path:** read-heavy traffic is served by Listing service / Search service; strong reads fall back to the canonical store when stale projections are unsafe.
4. **Async path:** Outbox/inbox workers / Admin/support console / Analytics/warehouse pipeline / Reconciliation worker / Projection builder consume committed events for notifications, indexing, analytics, provider calls, ML/risk feedback, cleanup, and reconciliation.
5. **Operations path:** admin, audit, replay, reconciliation, backfill, and disaster-recovery workflows are isolated from user-facing latency but use the same immutable event/audit history.

### Component Responsibilities

- **Listing service**: owns listing content, amenities, rules, photos, and publication state.
- **Search service**: serves denormalized geo/facet/date availability index.
- **Calendar service**: owns listing-day availability, holds, commits, and channel sync.
- **Pricing service**: calculates nightly price, fees, taxes, discounts, and policy.
- **Booking service**: owns stay state, guest/host actions, support annotations.
- **Trust service**: scores guest, host, listing, device, payment, and message risk.
- **Idempotency service**: stores request hash, caller, endpoint, aggregate reference, and final response for safe retries.
- **Outbox/inbox workers**: publish committed domain events and dedupe consumed events.
- **Admin/support console**: offers timeline, replay, correction, escalation, and policy override workflows with audit.
- **Analytics/warehouse pipeline**: loads immutable events and snapshots for BI, ML, compliance, and cost reporting.

### Service Responsibility Matrix

| Layer | Services | Responsibility |
| --- | --- | --- |
| Edge/API boundary | API Gateway / WAF / Load Balancer | Authentication, authorization handoff, request validation, rate limits, routing, TLS termination, coarse abuse controls, and trace context propagation. |
| Core domain services | Calendar service, Pricing service, Booking service, Idempotency service, State transition engine, Listing service | Own Airbnb Home Rental Marketplace business invariants, source-of-truth writes, state transitions, idempotency, and synchronous API responses. |
| Query/serving services | Listing service, Search service | Serve low-latency reads from caches, read models, indexes, or specialized serving stores while exposing freshness/consistency guarantees. |
| Async workers and integrations | Outbox/inbox workers, Admin/support console, Analytics/warehouse pipeline, Reconciliation worker, Projection builder | Consume committed events, call external systems, retry safely, update projections, run cleanup, and isolate slow dependencies from user-facing latency. |
| Data and governance | OLTP DB / cache / search index / object store / warehouse / audit log | Separate canonical state from derived stores; support rebuild, partitioning, retention, encryption, backup, and analytical access. |
| Operations | Admin console / reconciliation / observability / runbooks | Provide support investigation, replay/backfill, manual correction, compliance evidence, SLO dashboards, and incident response. |

## 6. Low-Level Design

### Core Services

- **Availability materializer**: builds search bitsets per listing/date window.
- **Hold manager**: creates short TTL holds on listing-day rows.
- **Cancellation engine**: evaluates policy by local time, actor, and date.
- **State transition engine**: validates allowed booking transitions using expected_version, policy decisions, and source-of-truth reads.
- **Reconciliation worker**: compares internal state, external provider reports, projections, ledger/audit rows, and emitted events.
- **Projection builder**: rebuilds search/read models from immutable events and snapshots after data loss or schema migration.

### Important Algorithms And Data Structures

- Use per listing-day rows with unique committed occupancy.
- Use date-range bitsets for search candidate pruning.
- Use short holds and expiry events for checkout/request flows.
- Rank by relevance, price, quality, availability, conversion, reliability, and trust.
- Use transactional outbox so state changes and events commit together.
- Use optimistic concurrency for normal writes and short leases/fencing tokens for contested scarce resources.
- Use exponential backoff with jitter, DLQ, and replay tooling for external dependencies.
- Use deterministic policy/rule versions so old decisions can be explained during support or audit.

### State Machines

- Booking: QUOTED -> HELD -> PAYMENT_AUTHORIZED -> REQUESTED/CONFIRMED -> STAY_IN_PROGRESS -> COMPLETED -> PAYOUT_RELEASED.
- Calendar day: AVAILABLE -> HELD -> BOOKED or BLOCKED.
- Payout: SCHEDULED -> ELIGIBILITY_PASSED -> SENT -> SETTLED or HELD_FOR_DISPUTE.

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
| listings | listing_id, host_id, location, status, amenities | Listing metadata. |
| listing_calendar_days | listing_id, date, state, price, version | Canonical nightly inventory. |
| calendar_holds | hold_id, listing_id, date_range, expires_at | Checkout hold. |
| bookings | booking_id, listing_id, guest_id, state, date_range, price_snapshot | Booking aggregate. |
| payouts | payout_id, booking_id, host_id, amount, state | Host payout. |
| idempotency_keys | caller_id, endpoint, idempotency_key, request_hash, aggregate_id, response_ref | Prevents duplicate mutation on client/provider retry. |
| domain_events | event_id, aggregate_id, aggregate_version, event_type, payload_ref | Outbox, replay, and audit event log. |
| audit_log | audit_id, actor_id, action, aggregate_id, before_hash, after_hash, reason | Immutable user/admin/service audit trail. |

### Indexing, Partitioning, And Retention

- calendar_days by listing_id + date, bookings by listing_id/date bucket, search index by geo/date facets.
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

1. Search uses denormalized availability bitset and hydrates listing cards.
2. Quote revalidates calendar/pricing and freezes price/policy snapshot.
3. Booking holds all nights, runs trust/payment, then confirms or waits for host.
4. Cancellation releases future inventory and computes refund/host payout impact.
5. Event publication: the aggregate write commits with an outbox event; publisher emits to the bus; consumers dedupe and update projections.
6. Reconciliation: scheduled worker compares source of truth with provider reports/read models/ledger and creates correction tasks for mismatches.
7. Operator correction: support action requires authorization, reason, expected version, immutable audit log, and compensating event.

## 9. Deep-Dive Focus Areas

- Prevent double booking with per-day constraints and final checkout revalidation.
- Channel sync conflicts need source/cause audit.
- Trust can force request-to-book, extra verification, or payment hold.
- Source-of-truth boundary: Booking service plus listing_calendar_days owns correctness; all low-latency read models are disposable projections.
- Idempotency boundary: key scope includes caller, endpoint, method, request hash, and business aggregate to prevent accidental replay with different payload.
- Consistency boundary: strong for money/inventory/security decisions; eventual for search, analytics, notifications, and dashboards.
- Replay boundary: events are versioned and payloads are immutable so projections and audit evidence can be rebuilt.

## 10. Scaling Bottlenecks And Mitigations

- Popular event cities create hot search/booking attempts; shard by geo/listing.
- Calendar range edits touch many rows; use batch writes and bounded transactions.
- Hot tenants/entities can overload a shard; use virtual shards, adaptive throttles, and queue isolation.
- External dependencies can create retry storms; isolate queues per provider and apply circuit breakers plus load shedding.
- Large historical queries and exports run on analytical replicas/object-store snapshots, not primary OLTP.
- Backfills and replays are rate-limited and observable so they do not compete with live traffic.

## 11. Security, Privacy, Abuse Prevention, And Compliance

- Protect exact addresses until confirmation, identity docs, messages, and payout details.
- Detect fake listings, off-platform payment, account takeover, party risk, and review manipulation.
- Use least-privilege RBAC/ABAC for users, partners, services, support, and break-glass access.
- Encrypt sensitive fields, rotate secrets, sign webhooks/callbacks, and tokenize payment/bank identifiers where applicable.
- Audit policy changes, manual overrides, exports, refunds/adjustments, and privileged reads.
- Run abuse detection on velocity, device, IP, account graph, payment instrument, partner behavior, and anomalous state transitions.

## 12. Reliability, Failure Modes, And Recovery

- If payment capture succeeds but calendar commit fails, refund and alert.
- If host times out, expire request and release hold.
- Reconcile bookings, calendar days, payment, refunds, and payouts.
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

- SLIs: booking mutation success rate, read latency, transition error rate, idempotency replay rate, queue lag, and reconciliation mismatch rate.
- Dashboards by tenant, region, aggregate state, provider, dependency, app version, and release version.
- Alerts for stuck state machines, DLQ growth, provider error spikes, hot partitions, reconciliation drift, and p99 latency regressions.
- Distributed traces carry request_id, idempotency_key, aggregate_id, aggregate_version, and downstream provider reference.
- Audit dashboards expose manual overrides, policy changes, replay actions, and data export access.

## 15. Cost Model And Trade-Offs

- Search index/photo CDN dominate browse cost.
- Calendar-day storage is large but correctness-friendly.
- Primary cost drivers usually include write amplification from events/audit, provider/API fees, search/index storage, telemetry retention, and peak capacity.
- Move cold immutable history to object storage/warehouse and keep the OLTP working set compact.
- Cache hot read models with short TTL and explicit invalidation only where correctness is not compromised.
- Quantify trade-offs between latency, correctness, provider calls, operational support, and storage retention.

## 16. Key Trade-Offs

- Instant booking improves conversion but increases host/fraud risk.
- Denormalized search is fast but stale; canonical checkout is mandatory.
- Strong consistency on the core aggregate adds latency but prevents expensive business errors.
- Eventual consistency in projections improves scale but requires UX states for pending/stale data.
- Richer risk checks reduce losses but can increase false positives and support load.
- Provider abstraction simplifies product services but must not hide provider-specific edge cases needed for reconciliation.

## 17. Common Interview Follow-Ups

- How do you prevent double booking?
- How do external calendars sync?
- How do cancellation policies affect payout?
- Where exactly is booking source of truth stored?
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

- **Correctness boundary:** Booking service plus listing_calendar_days is the authority; derived caches, search indexes, dashboards, and analytics must be rebuildable.
- **Hot path clarity:** start from `search -> quote stay -> hold nights -> confirm booking -> collect payment -> host payout` and walk the synchronous command path before discussing secondary features.
- **Service ownership:** explicitly assign responsibilities to Listing service, Search service, Calendar service, Pricing service, Booking service, Trust service; avoid vague boxes that do not own data or decisions.
- **Data ownership:** ground the design in `listings, listing_calendar_days, calendar_holds, bookings, payouts, idempotency_keys` and explain partitioning, indexes, retention, and replay.
- **Event model:** use `stay_booking.created.v1, stay_booking.validated.v1, stay_booking.state_changed.v1, stay_booking.committed.v1, stay_booking.failed.v1, stay_booking.reversed.v1` to decouple slow work while preserving idempotency and ordering per aggregate.
- **Operational maturity:** include backpressure, DLQs, reconciliation, runbooks, audit trails, and safe manual correction.

### Bar-Raiser Drill-Down Prompts

- Which service owns the final decision for `search -> quote stay -> hold nights -> confirm booking -> collect payment -> host payout`, and what exact write makes it durable?
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

- First minute: scope actors, constraints, and `search -> quote stay -> hold nights -> confirm booking -> collect payment -> host payout`.
- Minutes 2-3: draw edge, command path, query path, async path, and data stores; name Availability materializer, Hold manager, Cancellation engine, State transition engine, Reconciliation worker.
- Minute 4: walk one critical flow and call out idempotency, consistency, and failure recovery.
- Minute 5: close with scale bottlenecks, security/privacy, observability, cost, and trade-offs.
