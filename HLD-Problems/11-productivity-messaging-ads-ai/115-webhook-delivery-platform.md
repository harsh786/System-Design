# Design Webhook Delivery Platform - System Design Deep Dive

**Problem #115**  
**Category:** Platform/integration  
**Primary pattern:** event fanout + reliable delivery + replay  
**Deep-dive focus:** endpoint registration, signing, retries, DLQ, ordering, replay

## 0. Interview Framing

Webhook delivery gives customers at-least-once event notifications while isolating slow endpoints and preserving useful replay/debug tooling.

Actors: product services, customer endpoints, developers, operators. The highest-risk path is **event -> endpoints -> sign -> deliver/retry -> logs/replay**. Keep the design centered there; move secondary work async unless it affects correctness, money, privacy, abuse prevention, or user-visible availability.

## 1. Requirements

### Functional Requirements

- Customers register endpoints, event subscriptions, secrets, filters, rate limits, and retry policy.
- Platform receives internal events, creates delivery tasks, signs payloads, sends HTTP, retries, and records attempts.
- Developers inspect logs, verify signatures, disable endpoints, rotate secrets, and replay events.
- Support ordering per endpoint/aggregate where needed.
- Expose support/admin operations to inspect, replay, correct, and annotate delivery_task history.
- Publish domain events for notifications, analytics, search, reconciliation, ML/risk, and support tooling.
- Support regional/cell-level degradation so unrelated markets, tenants, or products remain available.

### Non-Functional Requirements

- Delivery is at-least-once; consumers dedupe event_id.
- Slow endpoints do not block other tenants.
- Payload signing and secret rotation are secure.
- Every mutating API is idempotent and accepts an expected version or equivalent conflict guard.
- Source of truth: webhook_events plus delivery_tasks/attempts; caches, search indexes, dashboards, and read models are rebuildable projections.
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
| Events | 1B/day |
| Endpoints | 10M |
| Attempts | 1-10 per event |
| Failure rate | Highly skewed by endpoint |
| Retention | Logs 30-90 days |
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
- Keep the online delivery_task aggregate compact; move large payloads, documents, telemetry, and raw reports to object storage.
- Model hot keys separately from averages; region, tenant, campaign, show, driver, account, and instrument skew can dominate.
- Separate OLTP correctness storage from OLAP/reporting storage so analytics cannot starve live mutations.

## 3. API Design

Use REST for public/partner APIs, gRPC for internal services, and async events for propagation. Every mutation includes `Idempotency-Key`, `Authorization`, `client_request_id`, and optionally `expected_version`.

| API | Important Request Fields | Notes |
| --- | --- | --- |
| POST /v1/webhook-endpoints | url, events, secret_policy | Register. |
| POST /v1/internal/webhook-events | event_type, aggregate_id, payload_ref | Enqueue event. |
| GET /v1/webhook-deliveries | endpoint_id, event_id | Inspect logs. |
| POST /v1/webhook-deliveries/{id}/replay | reason | Replay. |
| GET /v1/webhook-deliveries/{id} | path id, caller identity | Read canonical state or authorized projection. |
| POST /v1/admin/webhook-deliveries/{id}/reconcile | scope, dry_run, reason | Operator reconciliation with audit trail. |

### Internal APIs

```protobuf
service WebhookDeliveryService {
  rpc Create(CreateWebhookDeliveryRequest) returns (WebhookDelivery);
  rpc Get(GetWebhookDeliveryRequest) returns (WebhookDelivery);
  rpc Transition(TransitionWebhookDeliveryRequest) returns (WebhookDelivery);
  rpc Reconcile(ReconcileWebhookDeliveryRequest) returns (ReconcileResult);
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
  "event_type": "webhook_delivery.state_changed.v1",
  "occurred_at": "2026-05-25T10:15:30Z",
  "producer": "webhook_delivery-service",
  "tenant_or_region_id": "region_123",
  "aggregate_id": "delivery_task_123",
  "aggregate_version": 42,
  "idempotency_key": "idem_123",
  "actor": {"type": "user|partner|service|system", "id": "actor_123"},
  "payload_ref": "object://event-payloads/evt_01H..."
}
```

### Core Events

- webhook_delivery.created.v1
- webhook_delivery.validated.v1
- webhook_delivery.state_changed.v1
- webhook_delivery.committed.v1
- webhook_delivery.failed.v1
- webhook_delivery.reversed.v1
- webhook_delivery.reconciliation_completed.v1
- webhook_delivery.manual_review_required.v1

### Eventing Rules

- Partition by aggregate ID or natural ordering key; avoid global ordering requirements.
- Consumers are idempotent and store processed event IDs or aggregate versions.
- Sensitive payloads carry references, not raw secrets or unnecessary PII.
- Schema changes are additive first; breaking changes require a new event version.
- DLQs include owner, runbook, replay command, first failure, and last failure metadata.

## 5. High-Level Architecture

### Architecture Design

```text
Webhook Delivery Platform Architecture

Actors / Clients / Partner Systems
        |
        v
DNS / Global Traffic Manager / CDN where useful
        |
        v
API Gateway / WAF / Auth / Rate Limits / Request Router
        |
        +--> Synchronous Command Path
        |       -> Dispatcher -> Idempotency service -> State transition engine -> Endpoint service -> Developer portal
        |       -> Source-of-Truth Write + Transactional Outbox
        |
        +--> Query / Serving Path
        |       -> Cache / Read model / Search or specialized index
        |       -> Canonical Store fallback when strong freshness is required
        |
        +--> Async/Event Path
        |       -> Event Bus / Stream Processing / Workflow Queues
        |       -> Delivery workers / Retry scheduler / Outbox/inbox workers / Admin/support console / Analytics/warehouse pipeline / Webhook dispatch service
        |
        +--> Operations Path
                -> Admin Console / Audit / Reconciliation / Backfill / Disaster Recovery

Data Stores: Message/event store + session/presence TTL store + fanout queues + search/archive + notification state
Ops/Integrations: Connection health + delivery retries + moderation/abuse + notification providers + sync repair
```

### Request And Data Flow

1. **Request entry:** actors enter through edge controls that authenticate, authorize, rate-limit, route, and attach trace context before reaching the Webhook Delivery Platform service boundary.
2. **Synchronous command path:** correctness-sensitive mutations stay inside Dispatcher -> Idempotency service -> State transition engine -> Endpoint service -> Developer portal; this path performs validation, idempotency checks, source-of-truth writes, and outbox publication.
3. **Query path:** read-heavy traffic is served by Cache / Read model / Search or specialized index; strong reads fall back to the canonical store when stale projections are unsafe.
4. **Async path:** Delivery workers / Retry scheduler / Outbox/inbox workers / Admin/support console / Analytics/warehouse pipeline / Webhook dispatch service consume committed events for notifications, indexing, analytics, provider calls, ML/risk feedback, cleanup, and reconciliation.
5. **Operations path:** admin, audit, replay, reconciliation, backfill, and disaster-recovery workflows are isolated from user-facing latency but use the same immutable event/audit history.

### Component Responsibilities

- **Endpoint service**: URL, secret versions, subscriptions, filters.
- **Dispatcher**: matches events to endpoints and tasks.
- **Delivery workers**: signed HTTP and retry scheduling.
- **Retry scheduler**: backoff, max age, DLQ, health suppression.
- **Developer portal**: logs, payloads, signatures, replay.
- **Idempotency service**: stores request hash, caller, endpoint, aggregate reference, and final response for safe retries.
- **Outbox/inbox workers**: publish committed domain events and dedupe consumed events.
- **Admin/support console**: offers timeline, replay, correction, escalation, and policy override workflows with audit.
- **Analytics/warehouse pipeline**: loads immutable events and snapshots for BI, ML, compliance, and cost reporting.

### Service Responsibility Matrix

| Layer | Services | Responsibility |
| --- | --- | --- |
| Edge/API boundary | API Gateway / WAF / Load Balancer | Authentication, authorization handoff, request validation, rate limits, routing, TLS termination, coarse abuse controls, and trace context propagation. |
| Core domain services | Dispatcher, Idempotency service, State transition engine, Endpoint service, Developer portal | Own Webhook Delivery Platform business invariants, source-of-truth writes, state transitions, idempotency, and synchronous API responses. |
| Query/serving services | Cache / Read model / Search or specialized index | Serve low-latency reads from caches, read models, indexes, or specialized serving stores while exposing freshness/consistency guarantees. |
| Async workers and integrations | Delivery workers, Retry scheduler, Outbox/inbox workers, Admin/support console, Analytics/warehouse pipeline, Webhook dispatch service | Consume committed events, call external systems, retry safely, update projections, run cleanup, and isolate slow dependencies from user-facing latency. |
| Data and governance | OLTP DB / cache / search index / object store / warehouse / audit log | Separate canonical state from derived stores; support rebuild, partitioning, retention, encryption, backup, and analytical access. |
| Operations | Admin console / reconciliation / observability / runbooks | Provide support investigation, replay/backfill, manual correction, compliance evidence, SLO dashboards, and incident response. |

## 6. Low-Level Design

### Core Services

- **Webhook dispatch service**: owns delivery_task state machine, policy checks, outbox events, and compensation.
- **Adapter manager**: normalizes provider/partner callbacks and retries.
- **State transition engine**: validates allowed delivery_task transitions using expected_version, policy decisions, and source-of-truth reads.
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

- Webhook Delivery Platform: CREATED -> VALIDATED -> PENDING -> COMMITTED -> RECONCILED.
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
| webhook_endpoints | endpoint_id, tenant_id, url, secret_version | Endpoint. |
| webhook_events | event_id, tenant_id, type, aggregate_id | Event. |
| delivery_tasks | task_id, endpoint_id, event_id, state | Task. |
| delivery_attempts | attempt_id, task_id, status_code, latency | Attempt. |
| endpoint_health | endpoint_id, failure_rate, disabled_reason | Health. |
| idempotency_keys | caller_id, endpoint, idempotency_key, request_hash, aggregate_id, response_ref | Prevents duplicate mutation on client/provider retry. |
| domain_events | event_id, aggregate_id, aggregate_version, event_type, payload_ref | Outbox, replay, and audit event log. |
| audit_log | audit_id, actor_id, action, aggregate_id, before_hash, after_hash, reason | Immutable user/admin/service audit trail. |

### Database Technology Choice

| Workload / Data | Recommended Database / Store | Why This Choice Fits |
| --- | --- | --- |
| Source of truth / primary store | PostgreSQL/CockroachDB for endpoints, subscriptions, signing secrets, delivery state, and replay requests; Kafka/Pulsar plus partitioned queue store for durable delivery attempts | tenant configuration and delivery lifecycle need auditable state, while delivery fanout needs durable partitioned retry streams |
| Hot serving / cache | Redis for endpoint health, rate limits, dedupe windows, and short-lived replay locks | keeps hot reads, sessions, counters, quotas, and derived views away from the OLTP source of truth |
| Event stream / outbox | Kafka/Pulsar/Kinesis with compacted topics for keys and retained topics for replay | decouples projections, notifications, analytics, search indexing, and recovery from the write path |
| Search / analytics | OpenSearch for delivery search; ClickHouse for delivery analytics and customer dashboards | serves text/filter/OLAP queries without overloading transactional tables |
| Large immutable payloads | object storage for large payload archives, signed evidence, exports, and DLQ snapshots | large or immutable data is cheaper, durable, and easier to lifecycle outside OLTP rows |

Interview stance: name the source-of-truth database first, then explicitly separate caches, indexes, event logs, and analytics stores. The cache, search index, and warehouse are derived systems; they must be rebuildable from canonical state and immutable events.

### Replication Strategy

- Primary store: multi-AZ synchronous or quorum replication for the primary store; asynchronous cross-region replicas for DR and read locality.
- Event log: replicate each partition across at least 3 brokers/nodes, require quorum acknowledgements for critical events, and monitor under-replicated partitions.
- Cache/read models: replicate for availability, but treat them as disposable; rebuild from source-of-truth rows plus events after corruption or cache loss.
- Object storage: use multi-AZ durability by default; enable cross-region replication only for disaster recovery, compliance, or locality requirements.
- Analytics/search stores: replicate shards for query availability, but recover by replaying events or rebuilding from snapshots when correctness is in doubt.

### Sharding And Partitioning Strategy

- Primary partition key: `tenant_id + endpoint_id + event_id hash; time bucket for delivery attempts`. Choose the key that matches the hottest write/read path, not just the entity name.
- Primary lookup path: `delivery_id/event_id/subscription_id` should be single-partition whenever possible.
- Time-partition append-heavy data such as events, audit logs, metrics, and delivery attempts so retention, archival, replay, and backfills do not scan the full corpus.
- Hot partition mitigation: isolate noisy endpoints, shard delivery queues, apply per-endpoint concurrency limits, and DLQ poison payloads.
- Keep tenant/cell/region boundaries explicit so one large customer, city, celebrity, event, or provider cannot overload the whole system.

### Indexing Strategy

- Required secondary indexes: `endpoint_id + state + next_attempt_at, tenant_id + created_at, idempotency_key, replay_request_id`.
- Keep OLTP indexes minimal on high-write tables; move broad filtering, text search, ranking, and analytics to dedicated search/OLAP stores.
- Use composite indexes that match real query order: equality columns first, then range/sort columns such as `created_at`, `updated_at`, or `score`.
- For mutable state machines, index `(state, updated_at)` or `(state, next_attempt_at)` for workers and repair jobs.
- For audit and event tables, prefer append-only writes with time-bucketed partitions and compact indexes over many mutable secondary indexes.

### CAP Theorem And Consistency Choices

| Data / Operation | CAP Bias During Partition | Consistency Model | Interview Notes |
| --- | --- | --- | --- |
| Canonical command path | CP for config/secrets/replay permissions | strong consistency for subscription config, signing secrets, delivery state transitions, and replay authorization | Prefer rejecting or queuing unsafe writes over accepting divergent state. |
| Derived read models | AP/eventual for delivery metrics and endpoint health summaries | Eventual consistency for customer dashboards, search, provider health scores, and analytics | Expose `pending`, `processing`, `stale_at`, or version metadata when users may observe lag. |
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

For this design, use queues/Kafka for asynchronous execution or delivery, Redis for hot ranking/session/rate-limit state, object storage for artifacts/transcripts/payloads, Flink/Spark for streaming signals, S3 + Iceberg for history, and ClickHouse/Pinot for realtime dashboards.

Implementation rule: start with the simplest reliable building block, then introduce Kafka/Flink/lakehouse/OLAP/microservice patterns when scale, replay, ownership, or query shape demands them. Every added component must have a clear owner, SLO, retention policy, replay story, and failure mode.

### Data Integrity Rules

- Each mutating request records idempotency key, request hash, caller, endpoint, response, and aggregate ID.
- Each state transition checks expected version and allowed transition from current state.
- External callbacks are deduped by provider event/reference ID before changing domain state.
- Financial or entitlement corrections are compensating records, not destructive edits.
- Reconciliation reports must be explainable back to source rows, events, provider files, and operator actions.

## 8. Critical Flows

1. Internal event matches endpoint subscriptions.
2. Dispatcher creates per-endpoint delivery task.
3. Worker signs payload with timestamp/secret version and sends HTTP.
4. Replay creates new task referencing original event.
5. Event publication: the aggregate write commits with an outbox event; publisher emits to the bus; consumers dedupe and update projections.
6. Reconciliation: scheduled worker compares source of truth with provider reports/read models/ledger and creates correction tasks for mismatches.
7. Operator correction: support action requires authorization, reason, expected version, immutable audit log, and compensating event.

## 9. Deep-Dive Focus Areas

- Per-tenant/endpoint queues prevent broken endpoints from starving healthy ones.
- Ordering is endpoint + aggregate scoped.
- Sign raw payload with timestamp to prevent replay/tampering.
- Source-of-truth boundary: webhook_events plus delivery_tasks/attempts owns correctness; all low-latency read models are disposable projections.
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

- Protect webhook secrets, payload PII, endpoint URLs, and logs.
- Detect SSRF, malicious endpoints, replay attacks, endpoint takeover, and tenant abuse.
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

- SLIs: delivery_task mutation success rate, read latency, transition error rate, idempotency replay rate, queue lag, and reconciliation mismatch rate.
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

- What guarantee do webhooks provide?
- How do retries and ordering interact?
- How do signatures work?
- Where exactly is delivery_task source of truth stored?
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

- **Correctness boundary:** webhook_events plus delivery_tasks/attempts is the authority; derived caches, search indexes, dashboards, and analytics must be rebuildable.
- **Hot path clarity:** start from `event -> endpoints -> sign -> deliver/retry -> logs/replay` and walk the synchronous command path before discussing secondary features.
- **Service ownership:** explicitly assign responsibilities to Endpoint service, Dispatcher, Delivery workers, Retry scheduler, Developer portal, Idempotency service; avoid vague boxes that do not own data or decisions.
- **Data ownership:** ground the design in `webhook_endpoints, webhook_events, delivery_tasks, delivery_attempts, endpoint_health, idempotency_keys` and explain partitioning, indexes, retention, and replay.
- **Event model:** use `webhook_delivery.created.v1, webhook_delivery.validated.v1, webhook_delivery.state_changed.v1, webhook_delivery.committed.v1, webhook_delivery.failed.v1, webhook_delivery.reversed.v1` to decouple slow work while preserving idempotency and ordering per aggregate.
- **Operational maturity:** include backpressure, DLQs, reconciliation, runbooks, audit trails, and safe manual correction.

### Bar-Raiser Drill-Down Prompts

- Which service owns the final decision for `event -> endpoints -> sign -> deliver/retry -> logs/replay`, and what exact write makes it durable?
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
- State ordering scope, session registry semantics, fanout strategy, offline delivery, and backpressure.
- Separate connection presence from durable message state.
- Explain retry, dedupe, sync cursors, and notification fallback.

### 5-Minute Whiteboard Structure

- First minute: scope actors, constraints, and `event -> endpoints -> sign -> deliver/retry -> logs/replay`.
- Minutes 2-3: draw edge, command path, query path, async path, and data stores; name Webhook dispatch service, Adapter manager, State transition engine, Reconciliation worker, Projection builder.
- Minute 4: walk one critical flow and call out idempotency, consistency, and failure recovery.
- Minute 5: close with scale bottlenecks, security/privacy, observability, cost, and trade-offs.
