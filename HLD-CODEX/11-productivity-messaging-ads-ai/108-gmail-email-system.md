# Gmail / Email System - Complete System Design

---

### Problem Frame

| Area | Design Choice |
|---|---|
| Category | Messaging/search/storage |
| Primary Pattern | mail ingestion + mailbox index + spam filtering |
| Deep-Dive Focus | SMTP, spam, mailbox labels, threads, attachments, search |

### Interview Context

Email is durable store-and-forward messaging plus search over huge private mailboxes.

Actors: senders, recipients, SMTP servers, web/mobile clients, abuse systems. The highest-risk path is **receive mail -> authenticate/filter -> store -> index -> deliver mailbox view**. Keep the design centered there; move secondary work async unless it affects correctness, money, privacy, abuse prevention, or user-visible availability.

---

## 1. Functional Requirements

These are the product capabilities the design must support in the first version. The hot path and correctness-sensitive paths are called out explicitly so the architecture can protect them.

- Send and receive email through SMTP/API with attachments, labels, folders, filters, threads, and search.
- Authenticate using SPF/DKIM/DMARC and classify spam, malware, phishing, and promotions.
- Support mailbox quotas, deletion/trash, retention, legal hold, and account recovery.
- Provide notifications and IMAP/POP/API sync where needed.
- Expose support/admin operations to inspect, replay, correct, and annotate message history.
- Publish domain events for notifications, analytics, search, reconciliation, ML/risk, and support tooling.
- Support regional/cell-level degradation so unrelated markets, tenants, or products remain available.

---

## 2. Non-Functional Requirements

The non-functional requirements define the engineering bar. They also make clear where strong consistency, durability, latency, isolation, and compliance matter most.

- Inbound delivery is durable once accepted.
- Mailbox listing/search is low-latency over large mailboxes.
- Unsafe content is filtered before user exposure.
- Every mutating API is idempotent and accepts an expected version or equivalent conflict guard.
- Source of truth: Message blob plus per-user mailbox state; caches, search indexes, dashboards, and read models are rebuildable projections.
- The design handles duplicate requests, duplicate callbacks, timeout, delayed events, and replay.
- PII, payment, identity, location, and regulated data are encrypted, access-controlled, audited, and retained by policy.
- The system provides operator-grade observability: traces, metrics, logs, audit trails, DLQs, and reconciliation reports.

### Non-Goals

- Do not design every UI screen; focus on backend contracts, ownership, data, and failure handling.
- Do not put analytics, notifications, emails, or search indexing on the synchronous correctness path.
- Do not keep scarce inventory, money movement, or security-sensitive decisions only in cache.
- Do not rely on distributed transactions across independently owned services; use sagas, outbox, and reconciliation.

---

## 3. Capacity Estimation

Use these numbers as an interview baseline. The formulas are included so the scale can be adjusted without changing the architecture.

Use interview-scale assumptions and state formulas so the interviewer can change the numbers.

| Dimension | Baseline Assumption |
| --- | --- |
| Users | 1B+ |
| Inbound mail | Billions/day |
| Attachments | Large object-store/CDN footprint |
| Search | High per active user |
| Retention | User-controlled plus legal holds |
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
- Keep the online message aggregate compact; move large payloads, documents, telemetry, and raw reports to object storage.
- Model hot keys separately from averages; region, tenant, campaign, show, driver, account, and instrument skew can dominate.
- Separate OLTP correctness storage from OLAP/reporting storage so analytics cannot starve live mutations.

---

## 4. Data Modeling

The data model separates authoritative state from derived read models, caches, indexes, event streams, and analytical projections.

### Canonical Tables

| Table | Primary Key / Important Columns | Purpose And Notes |
| --- | --- | --- |
| messages | message_id, rfc822_id, sender, received_at, blob_ref | Canonical message. |
| mailbox_messages | user_id, message_id, labels, read_state, thread_id | Per-user state. |
| attachments | attachment_id, message_id, blob_ref, scan_state | Attachment. |
| threads | thread_id, user_id, participants, last_message_at | Conversation. |
| filter_rules | rule_id, user_id, predicate, action | Filter. |
| idempotency_keys | caller_id, endpoint, idempotency_key, request_hash, aggregate_id, response_ref | Prevents duplicate mutation on client/provider retry. |
| domain_events | event_id, aggregate_id, aggregate_version, event_type, payload_ref | Outbox, replay, and audit event log. |
| audit_log | audit_id, actor_id, action, aggregate_id, before_hash, after_hash, reason | Immutable user/admin/service audit trail. |

### Database Technology Choice

| Workload / Data | Recommended Database / Store | Why This Choice Fits |
| --- | --- | --- |
| Source of truth / primary store | OpenSearch/Elasticsearch/Lucene-based indexes for serving; PostgreSQL/Spanner for crawl/config/metadata; object storage for raw documents, map tiles, logs, and snapshots | search queries need inverted/vector/geo indexes, while source metadata and crawl state need controlled transactions |
| Hot serving / cache | Redis/edge cache for hot queries, autocomplete prefixes, tiles, route snippets, and feature vectors | keeps hot reads, sessions, counters, quotas, and derived views away from the OLTP source of truth |
| Event stream / outbox | Kafka/Pulsar for document updates, crawl events, feature updates, and index build pipelines | decouples projections, notifications, analytics, search indexing, and recovery from the write path |
| Search / analytics | OpenSearch/Elasticsearch/Solr for inverted/geo search; vector DB or ANN index for embeddings; ClickHouse/Druid for query analytics | serves text/filter/OLAP queries without overloading transactional tables |
| Large immutable payloads | S3/GCS/Azure Blob/object storage for payloads, exports, evidence, backups, and immutable artifacts | large or immutable data is cheaper, durable, and easier to lifecycle outside OLTP rows |

Interview stance: name the source-of-truth database first, then explicitly separate caches, indexes, event logs, and analytics stores. The cache, search index, and warehouse are derived systems; they must be rebuildable from canonical state and immutable events.

### Replication Strategy

- Primary store: multi-AZ synchronous or quorum replication for the primary store; asynchronous cross-region replicas for DR and read locality.
- Event log: replicate each partition across at least 3 brokers/nodes, require quorum acknowledgements for critical events, and monitor under-replicated partitions.
- Cache/read models: replicate for availability, but treat them as disposable; rebuild from source-of-truth rows plus events after corruption or cache loss.
- Object storage: use multi-AZ durability by default; enable cross-region replication only for disaster recovery, compliance, or locality requirements.
- Analytics/search stores: replicate shards for query availability, but recover by replaying events or rebuilding from snapshots when correctness is in doubt.

### Sharding And Partitioning Strategy

- Primary partition key: `document_id/url_hash/geo_cell/query_prefix depending on workload; time bucket for logs`. Choose the key that matches the hottest write/read path, not just the entity name.
- Primary lookup path: `document_id/url_hash/place_id/route_id` should be single-partition whenever possible.
- Time-partition append-heavy data such as events, audit logs, metrics, and delivery attempts so retention, archival, replay, and backfills do not scan the full corpus.
- Hot partition mitigation: cache head queries, shard by term/doc/geocell, protect large tenants, and precompute hot routes/features.
- Keep tenant/cell/region boundaries explicit so one large customer, city, celebrity, event, or provider cannot overload the whole system.

### Indexing Strategy

- Required secondary indexes: `prefix, geohash/S2 cell, topic/category, freshness bucket, crawl_state, rank_feature_version`.
- Keep OLTP indexes minimal on high-write tables; move broad filtering, text search, ranking, and analytics to dedicated search/OLAP stores.
- Use composite indexes that match real query order: equality columns first, then range/sort columns such as `created_at`, `updated_at`, or `score`.
- For mutable state machines, index `(state, updated_at)` or `(state, next_attempt_at)` for workers and repair jobs.
- For audit and event tables, prefer append-only writes with time-bucketed partitions and compact indexes over many mutable secondary indexes.

### CAP Theorem And Consistency Choices

| Data / Operation | CAP Bias During Partition | Consistency Model | Interview Notes |
| --- | --- | --- | --- |
| Canonical command path | CP for canonical crawl/config/safety metadata and index version cutover | strong consistency for source metadata, crawl ownership, policy/safety blocks, and index version publication | Prefer rejecting or queuing unsafe writes over accepting divergent state. |
| Derived read models | AP/eventual for serving indexes because stale-but-safe results are acceptable within freshness SLO | Eventual consistency for index freshness, ranking features, autocomplete suggestions, analytics, and recommendations | Expose `pending`, `processing`, `stale_at`, or version metadata when users may observe lag. |
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

For this design, use Kafka plus Schema Registry for document/update streams, Flink/Spark for enrichment and feature generation, S3 + Iceberg/Hudi/Delta for raw crawl/query logs, OpenSearch/Lucene/vector indexes for serving, and Pinot/ClickHouse/Druid for query analytics.

Implementation rule: start with the simplest reliable building block, then introduce Kafka/Flink/lakehouse/OLAP/microservice patterns when scale, replay, ownership, or query shape demands them. Every added component must have a clear owner, SLO, retention policy, replay story, and failure mode.

### Data Integrity Rules

- Each mutating request records idempotency key, request hash, caller, endpoint, response, and aggregate ID.
- Each state transition checks expected version and allowed transition from current state.
- External callbacks are deduped by provider event/reference ID before changing domain state.
- Financial or entitlement corrections are compensating records, not destructive edits.
- Reconciliation reports must be explainable back to source rows, events, provider files, and operator actions.

---

## 5. High-Level Design (HLD)

The high-level design keeps the synchronous user path small and pushes enrichment, analytics, notifications, search indexing, and reconciliation into asynchronous pipelines.

### Architecture Design

```text
Gmail / Email System Architecture

Actors / Clients / Partner Systems
        |
        v
DNS / Global Traffic Manager / CDN where useful
        |
        v
API Gateway / WAF / Auth / Rate Limits / Request Router
        |
        +--> Synchronous Command Path
        |       -> Idempotency service -> Mailbox delivery service -> State transition engine -> Mailbox service -> Threading service -> SMTP/API ingress
        |       -> Source-of-Truth Write + Transactional Outbox
        |
        +--> Query / Serving Path
        |       -> Mailbox service / Mailbox delivery service
        |       -> Canonical Store fallback when strong freshness is required
        |
        +--> Async/Event Path
        |       -> Event Bus / Stream Processing / Workflow Queues
        |       -> Abuse pipeline / Search indexer / Outbox/inbox workers / Admin/support console / Analytics/warehouse pipeline / Adapter manager
        |
        +--> Operations Path
                -> Admin Console / Audit / Reconciliation / Backfill / Disaster Recovery

Data Stores: Message/event store + session/presence TTL store + fanout queues + search/archive + notification state
Ops/Integrations: Connection health + delivery retries + moderation/abuse + notification providers + sync repair
```

### Request And Data Flow

1. **Request entry:** actors enter through edge controls that authenticate, authorize, rate-limit, route, and attach trace context before reaching the Gmail / Email System service boundary.
2. **Synchronous command path:** correctness-sensitive mutations stay inside Idempotency service -> Mailbox delivery service -> State transition engine -> Mailbox service -> Threading service -> SMTP/API ingress; this path performs validation, idempotency checks, source-of-truth writes, and outbox publication.
3. **Query path:** read-heavy traffic is served by Mailbox service / Mailbox delivery service; strong reads fall back to the canonical store when stale projections are unsafe.
4. **Async path:** Abuse pipeline / Search indexer / Outbox/inbox workers / Admin/support console / Analytics/warehouse pipeline / Adapter manager consume committed events for notifications, indexing, analytics, provider calls, ML/risk feedback, cleanup, and reconciliation.
5. **Operations path:** admin, audit, replay, reconciliation, backfill, and disaster-recovery workflows are isolated from user-facing latency but use the same immutable event/audit history.

### Component Responsibilities

- **SMTP/API ingress**: accepts mail, validates auth, rate limits, durable queue.
- **Abuse pipeline**: SPF/DKIM/DMARC, reputation, malware, phishing ML.
- **Mailbox service**: message metadata, labels, per-user state, quota.
- **Search indexer**: per-user inverted indexes.
- **Threading service**: references/subject/participants grouping.
- **Idempotency service**: stores request hash, caller, endpoint, aggregate reference, and final response for safe retries.
- **Outbox/inbox workers**: publish committed domain events and dedupe consumed events.
- **Admin/support console**: offers timeline, replay, correction, escalation, and policy override workflows with audit.
- **Analytics/warehouse pipeline**: loads immutable events and snapshots for BI, ML, compliance, and cost reporting.

### Service Responsibility Matrix

| Layer | Services | Responsibility |
| --- | --- | --- |
| Edge/API boundary | API Gateway / WAF / Load Balancer | Authentication, authorization handoff, request validation, rate limits, routing, TLS termination, coarse abuse controls, and trace context propagation. |
| Core domain services | Idempotency service, Mailbox delivery service, State transition engine, Mailbox service, Threading service, SMTP/API ingress | Own Gmail / Email System business invariants, source-of-truth writes, state transitions, idempotency, and synchronous API responses. |
| Query/serving services | Mailbox service, Mailbox delivery service | Serve low-latency reads from caches, read models, indexes, or specialized serving stores while exposing freshness/consistency guarantees. |
| Async workers and integrations | Abuse pipeline, Search indexer, Outbox/inbox workers, Admin/support console, Analytics/warehouse pipeline, Adapter manager | Consume committed events, call external systems, retry safely, update projections, run cleanup, and isolate slow dependencies from user-facing latency. |
| Data and governance | OLTP DB / cache / search index / object store / warehouse / audit log | Separate canonical state from derived stores; support rebuild, partitioning, retention, encryption, backup, and analytical access. |
| Operations | Admin console / reconciliation / observability / runbooks | Provide support investigation, replay/backfill, manual correction, compliance evidence, SLO dashboards, and incident response. |

### Async Event Contracts

Use transactional outbox/inbox. Events are immutable, versioned, replayable, and partitioned by the aggregate that needs ordering.

```json
{
  "event_id": "evt_01H...",
  "event_type": "email.state_changed.v1",
  "occurred_at": "2026-05-25T10:15:30Z",
  "producer": "email-service",
  "tenant_or_region_id": "region_123",
  "aggregate_id": "message_123",
  "aggregate_version": 42,
  "idempotency_key": "idem_123",
  "actor": {"type": "user|partner|service|system", "id": "actor_123"},
  "payload_ref": "object://event-payloads/evt_01H..."
}
```

### Core Events

- email.created.v1
- email.validated.v1
- email.state_changed.v1
- email.committed.v1
- email.failed.v1
- email.reversed.v1
- email.reconciliation_completed.v1
- email.manual_review_required.v1

### Eventing Rules

- Partition by aggregate ID or natural ordering key; avoid global ordering requirements.
- Consumers are idempotent and store processed event IDs or aggregate versions.
- Sensitive payloads carry references, not raw secrets or unnecessary PII.
- Schema changes are additive first; breaking changes require a new event version.
- DLQs include owner, runbook, replay command, first failure, and last failure metadata.

---

## 6. Low-Level Design (LLD)

The low-level design describes service contracts, module boundaries, state transitions, and idempotency/concurrency controls.

### API Contracts

Use REST for public/partner APIs, gRPC for internal services, and async events for propagation. Every mutation includes `Idempotency-Key`, `Authorization`, `client_request_id`, and optionally `expected_version`.

| API | Important Request Fields | Notes |
| --- | --- | --- |
| POST /v1/messages/send | to, cc, subject, body, attachments | Send mail. |
| GET /v1/mailbox/messages | label, q, cursor | List/search. |
| PATCH /v1/messages/{id} | labels, read_state | Update mailbox state. |
| POST /v1/filter-rules | predicate, action | Create filter. |
| GET /v1/messages/{id} | path id, caller identity | Read canonical state or authorized projection. |
| POST /v1/admin/messages/{id}/reconcile | scope, dry_run, reason | Operator reconciliation with audit trail. |

### Internal APIs

```protobuf
service EmailService {
  rpc Create(CreateEmailRequest) returns (Email);
  rpc Get(GetEmailRequest) returns (Email);
  rpc Transition(TransitionEmailRequest) returns (Email);
  rpc Reconcile(ReconcileEmailRequest) returns (ReconcileResult);
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

### Core Services

- **Mailbox delivery service**: owns message state machine, policy checks, outbox events, and compensation.
- **Adapter manager**: normalizes provider/partner callbacks and retries.
- **State transition engine**: validates allowed message transitions using expected_version, policy decisions, and source-of-truth reads.
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

- Gmail / Email System: CREATED -> VALIDATED -> PENDING -> COMMITTED -> RECONCILED.
- Failure: PENDING -> FAILED -> COMPENSATION_PENDING -> REVERSED or MANUAL_REVIEW.
- External callback: RECEIVED -> DEDUPED -> APPLIED -> ACKED.

### Consistency Model

- Strong consistency for source-of-truth transitions, scarce inventory, funds/ledger, entitlement, identity, and policy gates.
- Eventual consistency for search, feed, notification, analytics, ML features, dashboards, and cache refresh.
- Optimistic concurrency with version columns for normal writes; leases/fencing for contested resources.
- Sagas with explicit compensation for multi-service workflows; no hidden distributed transaction.

---

## 7. Architecture Components

Each component has one clear owner and a rebuild story for derived state. This avoids coupling operational workflows to the latency budget of the primary user path.

### Component And Store Ownership

The architecture should be read as a set of ownership boundaries: command services own mutations, query services own low-latency reads, async workers own projections, and operators own audit/replay workflows.

### Architecture Design

```text
Gmail / Email System Architecture

Actors / Clients / Partner Systems
        |
        v
DNS / Global Traffic Manager / CDN where useful
        |
        v
API Gateway / WAF / Auth / Rate Limits / Request Router
        |
        +--> Synchronous Command Path
        |       -> Idempotency service -> Mailbox delivery service -> State transition engine -> Mailbox service -> Threading service -> SMTP/API ingress
        |       -> Source-of-Truth Write + Transactional Outbox
        |
        +--> Query / Serving Path
        |       -> Mailbox service / Mailbox delivery service
        |       -> Canonical Store fallback when strong freshness is required
        |
        +--> Async/Event Path
        |       -> Event Bus / Stream Processing / Workflow Queues
        |       -> Abuse pipeline / Search indexer / Outbox/inbox workers / Admin/support console / Analytics/warehouse pipeline / Adapter manager
        |
        +--> Operations Path
                -> Admin Console / Audit / Reconciliation / Backfill / Disaster Recovery

Data Stores: Message/event store + session/presence TTL store + fanout queues + search/archive + notification state
Ops/Integrations: Connection health + delivery retries + moderation/abuse + notification providers + sync repair
```

### Request And Data Flow

1. **Request entry:** actors enter through edge controls that authenticate, authorize, rate-limit, route, and attach trace context before reaching the Gmail / Email System service boundary.
2. **Synchronous command path:** correctness-sensitive mutations stay inside Idempotency service -> Mailbox delivery service -> State transition engine -> Mailbox service -> Threading service -> SMTP/API ingress; this path performs validation, idempotency checks, source-of-truth writes, and outbox publication.
3. **Query path:** read-heavy traffic is served by Mailbox service / Mailbox delivery service; strong reads fall back to the canonical store when stale projections are unsafe.
4. **Async path:** Abuse pipeline / Search indexer / Outbox/inbox workers / Admin/support console / Analytics/warehouse pipeline / Adapter manager consume committed events for notifications, indexing, analytics, provider calls, ML/risk feedback, cleanup, and reconciliation.
5. **Operations path:** admin, audit, replay, reconciliation, backfill, and disaster-recovery workflows are isolated from user-facing latency but use the same immutable event/audit history.

### Component Responsibilities

- **SMTP/API ingress**: accepts mail, validates auth, rate limits, durable queue.
- **Abuse pipeline**: SPF/DKIM/DMARC, reputation, malware, phishing ML.
- **Mailbox service**: message metadata, labels, per-user state, quota.
- **Search indexer**: per-user inverted indexes.
- **Threading service**: references/subject/participants grouping.
- **Idempotency service**: stores request hash, caller, endpoint, aggregate reference, and final response for safe retries.
- **Outbox/inbox workers**: publish committed domain events and dedupe consumed events.
- **Admin/support console**: offers timeline, replay, correction, escalation, and policy override workflows with audit.
- **Analytics/warehouse pipeline**: loads immutable events and snapshots for BI, ML, compliance, and cost reporting.

### Service Responsibility Matrix

| Layer | Services | Responsibility |
| --- | --- | --- |
| Edge/API boundary | API Gateway / WAF / Load Balancer | Authentication, authorization handoff, request validation, rate limits, routing, TLS termination, coarse abuse controls, and trace context propagation. |
| Core domain services | Idempotency service, Mailbox delivery service, State transition engine, Mailbox service, Threading service, SMTP/API ingress | Own Gmail / Email System business invariants, source-of-truth writes, state transitions, idempotency, and synchronous API responses. |
| Query/serving services | Mailbox service, Mailbox delivery service | Serve low-latency reads from caches, read models, indexes, or specialized serving stores while exposing freshness/consistency guarantees. |
| Async workers and integrations | Abuse pipeline, Search indexer, Outbox/inbox workers, Admin/support console, Analytics/warehouse pipeline, Adapter manager | Consume committed events, call external systems, retry safely, update projections, run cleanup, and isolate slow dependencies from user-facing latency. |
| Data and governance | OLTP DB / cache / search index / object store / warehouse / audit log | Separate canonical state from derived stores; support rebuild, partitioning, retention, encryption, backup, and analytical access. |
| Operations | Admin console / reconciliation / observability / runbooks | Provide support investigation, replay/backfill, manual correction, compliance evidence, SLO dashboards, and incident response. |

---

## 8. Deep Dive of Each Component/Service

These are the areas interviewers usually drill into because they determine whether the design survives real production traffic and failure modes.

1. Inbound SMTP stores raw blob, authenticates/scans, then delivers per-recipient mailbox state.
2. Search queries per-user index and hydrates metadata.
3. Send stores sent copy and queues SMTP delivery with retries.
4. Archive/delete changes labels and retention state.
5. Event publication: the aggregate write commits with an outbox event; publisher emits to the bus; consumers dedupe and update projections.
6. Reconciliation: scheduled worker compares source of truth with provider reports/read models/ledger and creates correction tasks for mismatches.
7. Operator correction: support action requires authorization, reason, expected version, immutable audit log, and compensating event.

- Per-recipient mailbox state avoids copying large bodies.
- Per-user index simplifies privacy and deletion.
- Spam uses reputation, content, URL, attachment, and user feedback.
- Source-of-truth boundary: Message blob plus per-user mailbox state owns correctness; all low-latency read models are disposable projections.
- Idempotency boundary: key scope includes caller, endpoint, method, request hash, and business aggregate to prevent accidental replay with different payload.
- Consistency boundary: strong for money/inventory/security decisions; eventual for search, analytics, notifications, and dashboards.
- Replay boundary: events are versioned and payloads are immutable so projections and audit evidence can be rebuilt.

---

## 9. Component Optimization

Optimization focuses on hot keys, fanout, cache behavior, backpressure, partitioning, cost, and safe degradation before adding more infrastructure.

- Hot accounts/entities/campaigns create partition skew; use virtual shards and per-entity throttles.
- Provider timeouts create retry storms; isolate queues per provider.
- Backfills/replays must be throttled and observable.
- Hot tenants/entities can overload a shard; use virtual shards, adaptive throttles, and queue isolation.
- External dependencies can create retry storms; isolate queues per provider and apply circuit breakers plus load shedding.
- Large historical queries and exports run on analytical replicas/object-store snapshots, not primary OLTP.
- Backfills and replays are rate-limited and observable so they do not compete with live traffic.

### Cost Model

- Provider/API fees, event/audit write amplification, search/index storage, and support workflows dominate cost.
- Cold history moves to object storage/warehouse; OLTP keeps working set compact.
- Primary cost drivers usually include write amplification from events/audit, provider/API fees, search/index storage, telemetry retention, and peak capacity.
- Move cold immutable history to object storage/warehouse and keep the OLTP working set compact.
- Cache hot read models with short TTL and explicit invalidation only where correctness is not compromised.
- Quantify trade-offs between latency, correctness, provider calls, operational support, and storage retention.

---

## 10. Observability

Observability must prove the design is healthy from the user journey down to queues, storage, workers, cache tiers, and external dependencies.

- SLIs: message mutation success rate, read latency, transition error rate, idempotency replay rate, queue lag, and reconciliation mismatch rate.
- Dashboards by tenant, region, aggregate state, provider, dependency, app version, and release version.
- Alerts for stuck state machines, DLQ growth, provider error spikes, hot partitions, reconciliation drift, and p99 latency regressions.
- Distributed traces carry request_id, idempotency_key, aggregate_id, aggregate_version, and downstream provider reference.
- Audit dashboards expose manual overrides, policy changes, replay actions, and data export access.

### Deployment And Operations

- Deploy services independently behind API gateway routing with backward-compatible API and event schema versions.
- Use canary or blue/green deployments for orchestrators, risk/pricing engines, and provider adapters.
- Run schema migrations as expand-migrate-contract and keep rollback playbooks for hot paths.
- Use per-region feature flags, kill switches, and dependency circuit breakers.
- Maintain runbooks for backlog growth, provider outage, stuck aggregate, reconciliation mismatch, and data replay.

---

## 11. Considerations & Assumptions

These considerations make the design defensible: security, privacy, failure handling, cost, trade-offs, and follow-up answers.

### Security, Privacy, Abuse Prevention, And Compliance

- Protect email content, attachments, contacts, tokens, and search queries.
- Detect spam, phishing, malware, ATO, mass-mailing abuse, and OAuth app abuse.
- Use least-privilege RBAC/ABAC for users, partners, services, support, and break-glass access.
- Encrypt sensitive fields, rotate secrets, sign webhooks/callbacks, and tokenize payment/bank identifiers where applicable.
- Audit policy changes, manual overrides, exports, refunds/adjustments, and privileged reads.
- Run abuse detection on velocity, device, IP, account graph, payment instrument, partner behavior, and anomalous state transitions.

### Reliability, Failure Modes, And Recovery

- Keep pending/unknown as explicit state on timeout.
- Reconcile internal state against provider reports and immutable events.
- Use replay to rebuild projections after bugs or schema migrations.
- Use durable queues for asynchronous work and DLQs with owner, retry policy, replay command, and runbook.
- If a dependency times out, keep the aggregate in explicit pending/unknown state and converge through callback, status poll, or reconciliation.
- Use backups plus event replay to recover projections; test restore and replay regularly.
- Prefer graceful degradation: pause risky mutations while preserving reads, active sessions, safety flows, and support access.

### Key Trade-Offs

- Stronger correctness increases latency but prevents expensive business errors.
- Eventual read models scale but require pending/stale UX states.
- More fraud/risk checks reduce loss but increase false positives.
- Strong consistency on the core aggregate adds latency but prevents expensive business errors.
- Eventual consistency in projections improves scale but requires UX states for pending/stale data.
- Richer risk checks reduce losses but can increase false positives and support load.
- Provider abstraction simplifies product services but must not hide provider-specific edge cases needed for reconciliation.

### Common Interview Follow-Ups

- How do you store one email for many recipients?
- How do labels differ from folders?
- How do you build mailbox search?
- Where exactly is message source of truth stored?
- What happens when the external provider succeeds but the internal callback is delayed?
- How would you rebuild read models after a bad deployment?
- Which parts are strongly consistent and which are eventually consistent?

### Final Interview Checklist

- Clarify scope, actors, success metrics, and the hottest correctness path before drawing components.
- Name the source of truth and the consistency boundary for the core aggregate.
- Show APIs, event contracts, HLD, LLD, data model, indexes, partitioning, and retention.
- Cover idempotency, state transitions, retries, reconciliation, and operator recovery.
- Discuss security, privacy, abuse, compliance, deployment, observability, and cost trade-offs.

---

## Summary: Interview Talking Points

Use this section to drive the final five-minute whiteboard summary and to prepare for bar-raiser follow-ups.

### What A Strong Interview Answer Must Demonstrate

- **Correctness boundary:** Message blob plus per-user mailbox state is the authority; derived caches, search indexes, dashboards, and analytics must be rebuildable.
- **Hot path clarity:** start from `receive mail -> authenticate/filter -> store -> index -> deliver mailbox view` and walk the synchronous command path before discussing secondary features.
- **Service ownership:** explicitly assign responsibilities to SMTP/API ingress, Abuse pipeline, Mailbox service, Search indexer, Threading service, Idempotency service; avoid vague boxes that do not own data or decisions.
- **Data ownership:** ground the design in `messages, mailbox_messages, attachments, threads, filter_rules, idempotency_keys` and explain partitioning, indexes, retention, and replay.
- **Event model:** use `email.created.v1, email.validated.v1, email.state_changed.v1, email.committed.v1, email.failed.v1, email.reversed.v1` to decouple slow work while preserving idempotency and ordering per aggregate.
- **Operational maturity:** include backpressure, DLQs, reconciliation, runbooks, audit trails, and safe manual correction.

### Bar-Raiser Drill-Down Prompts

- Which service owns the final decision for `receive mail -> authenticate/filter -> store -> index -> deliver mailbox view`, and what exact write makes it durable?
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

- First minute: scope actors, constraints, and `receive mail -> authenticate/filter -> store -> index -> deliver mailbox view`.
- Minutes 2-3: draw edge, command path, query path, async path, and data stores; name Mailbox delivery service, Adapter manager, State transition engine, Reconciliation worker, Projection builder.
- Minute 4: walk one critical flow and call out idempotency, consistency, and failure recovery.
- Minute 5: close with scale bottlenecks, security/privacy, observability, cost, and trade-offs.
