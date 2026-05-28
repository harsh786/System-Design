# feature flag platform - Complete System Design

---

### Problem Frame

| Area | Design Choice |
|---|---|
| Category | Platform |
| Primary Pattern | infra security |
| Deep-Dive Focus | targeting, SDK caching, rollout, consistency, audit |

### Interview Context

An enterprise control-plane platform where policy, multi-tenancy, auditability, rollout safety, and high-availability data planes are the main interview themes.

In an interview, start by narrowing the product scope, then anchor the design around the highest-risk path. For this problem, the highest-risk path is usually the path involving **targeting**. Keep secondary capabilities asynchronous unless they affect correctness, money, privacy, or user-visible availability.

---

## 1. Functional Requirements

These are the product capabilities the design must support in the first version. The hot path and correctness-sensitive paths are called out explicitly so the architecture can protect them.

- Manage tenant-scoped policies and configuration.
- Propagate safe versions to a data plane.
- Evaluate access, routing, or operational decisions.
- Record audit trails and support rollback/break-glass.
- Expose admin operations for investigation, replay, correction, and policy changes.
- Publish domain events for analytics, search, notifications, and downstream systems.
- Support regional failover and controlled degradation for non-critical features.

---

## 2. Non-Functional Requirements

The non-functional requirements define the engineering bar. They also make clear where strong consistency, durability, latency, isolation, and compliance matter most.

- tenant isolation and policy correctness.
- auditable change history.
- safe rollout with versioned configs.
- regional failure isolation.
- secure secret/key handling and break-glass process where relevant.

### Non-Goals

- Do not design every client UI screen; focus on backend, data, and platform contracts.
- Do not optimize rare administrative workflows ahead of the user-visible hot path.
- Do not couple offline analytics correctness to online request latency.
- Do not rely on one shared database node as the scalability plan.

---

## 3. Capacity Estimation

Use these numbers as an interview baseline. The formulas are included so the scale can be adjusted without changing the architecture.

Use these as interview-scale assumptions. State that numbers are adjustable and use formulas so the interviewer can change scale.

| Dimension | Baseline Assumption |
|---|---|
| Tenants | 100K organizations or projects |
| Control-plane QPS | 10K QPS average, 100K peak |
| Data-plane QPS | 1M+ QPS for hot evaluation paths when applicable |
| Policy/config objects | 100M+ versions/events |
| Availability target | 99.99% control plane, 99.999% for critical data plane paths |

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

---

## 4. Data Modeling

The data model separates authoritative state from derived read models, caches, indexes, event streams, and analytical projections.

### Logical Model

```text
Tenant/User
  -> owns or can access -> FeatureFlag
  -> emits -> FeatureFlagEvent
  -> produces -> ReadModel / SearchDocument / Metric
  -> audited by -> AuditLog
```

### Core Tables

| Table | Important Columns |
|---|---|
| `feature_flags` | `id, tenant_id, key, owner_team, default_value, state, created_at` |
| `flag_versions` | `flag_id, version, rule_set_ref, rollout_percentage, created_by, created_at` |
| `targeting_rules` | `id, flag_id, version, segment_ref, predicate_json, priority` |
| `assignments` | `id, tenant_id, subject_id, flag_id, variant, reason, expires_at` |
| `evaluation_events` | `flag_id, variant, subject_hash, sdk_key_hash, latency_ms, ts` |
| `audit_log` | `id, tenant_id, actor_id, action, resource_type, resource_id, outcome, request_id, ts` |

### Database Technology Choice

| Workload / Data | Recommended Database / Store | Why This Choice Fits |
| --- | --- | --- |
| Source of truth / primary store | strongly consistent store such as Spanner/CockroachDB/PostgreSQL or Raft-backed etcd/Consul/ZooKeeper for identity, config, secrets metadata, locks, and policy versions | security and control-plane decisions must avoid split-brain, stale revocation, and conflicting ownership |
| Hot serving / cache | local sidecar/SDK cache plus Redis for non-authoritative sessions, evaluation caches, and rate limits with short TTLs | keeps hot reads, sessions, counters, quotas, and derived views away from the OLTP source of truth |
| Event stream / outbox | Kafka/Pulsar for audit events, deployment events, incident timelines, and projection rebuilds | decouples projections, notifications, analytics, search indexing, and recovery from the write path |
| Search / analytics | OpenSearch for audit/incident/config search; ClickHouse/TSDB for metrics/traces/operational analytics | serves text/filter/OLAP queries without overloading transactional tables |
| Large immutable payloads | object storage for artifacts, trace blocks, long-retention audit exports, backups, and signed bundles | large or immutable data is cheaper, durable, and easier to lifecycle outside OLTP rows |

Interview stance: name the source-of-truth database first, then explicitly separate caches, indexes, event logs, and analytics stores. The cache, search index, and warehouse are derived systems; they must be rebuildable from canonical state and immutable events.

### Replication Strategy

- Primary store: multi-AZ synchronous or quorum replication for the primary store; asynchronous cross-region replicas for DR and read locality.
- Event log: replicate each partition across at least 3 brokers/nodes, require quorum acknowledgements for critical events, and monitor under-replicated partitions.
- Cache/read models: replicate for availability, but treat them as disposable; rebuild from source-of-truth rows plus events after corruption or cache loss.
- Object storage: use multi-AZ durability by default; enable cross-region replication only for disaster recovery, compliance, or locality requirements.
- Analytics/search stores: replicate shards for query availability, but recover by replaying events or rebuilding from snapshots when correctness is in doubt.

### Sharding And Partitioning Strategy

- Primary partition key: `tenant_id + resource_id; service_id/config_key; trace_id or metric_series for observability workloads`. Choose the key that matches the hottest write/read path, not just the entity name.
- Primary lookup path: `resource_id/config_key/secret_id/lock_name/trace_id` should be single-partition whenever possible.
- Time-partition append-heavy data such as events, audit logs, metrics, and delivery attempts so retention, archival, replay, and backfills do not scan the full corpus.
- Hot partition mitigation: cache read-heavy config/flag/secret metadata at edge, shard by tenant/resource, and isolate noisy observability tenants.
- Keep tenant/cell/region boundaries explicit so one large customer, city, celebrity, event, or provider cannot overload the whole system.

### Indexing Strategy

- Required secondary indexes: `tenant_id + state, subject_id + permission, updated_at, version, expires_at`.
- Keep OLTP indexes minimal on high-write tables; move broad filtering, text search, ranking, and analytics to dedicated search/OLAP stores.
- Use composite indexes that match real query order: equality columns first, then range/sort columns such as `created_at`, `updated_at`, or `score`.
- For mutable state machines, index `(state, updated_at)` or `(state, next_attempt_at)` for workers and repair jobs.
- For audit and event tables, prefer append-only writes with time-bucketed partitions and compact indexes over many mutable secondary indexes.

### CAP Theorem And Consistency Choices

| Data / Operation | CAP Bias During Partition | Consistency Model | Interview Notes |
| --- | --- | --- | --- |
| Canonical command path | CP for security/control-plane ownership and revocation | strong consistency for authorization policy, secret versions, config publication, lock ownership, and incident escalation state | Prefer rejecting or queuing unsafe writes over accepting divergent state. |
| Derived read models | AP/eventual for SDK caches and observability projections with bounded TTL and version checks | Eventual consistency for audit search, metrics, trace search, dashboards, notifications, and historical reports | Expose `pending`, `processing`, `stale_at`, or version metadata when users may observe lag. |
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

For this design, use strong control-plane storage for policy/config/ownership, local or Redis caches for data-plane speed, Kafka/outbox for audit and change events, Debezium/CDC for projections when useful, S3/Iceberg for audit retention, and OpenTelemetry/Prometheus/Grafana for operations.

Implementation rule: start with the simplest reliable building block, then introduce Kafka/Flink/lakehouse/OLAP/microservice patterns when scale, replay, ownership, or query shape demands them. Every added component must have a clear owner, SLO, retention policy, replay story, and failure mode.

---

## 5. High-Level Design (HLD)

The high-level design keeps the synchronous user path small and pushes enrichment, analytics, notifications, search indexing, and reconciliation into asynchronous pipelines.

### Architecture Design

```text
feature flag platform Architecture

Actors / Clients / Partner Systems
        |
        v
DNS / Global Traffic Manager / CDN where useful
        |
        v
API Gateway / WAF / Auth / Rate Limits / Request Router
        |
        +--> Synchronous Command Path
        |       -> Propagation service -> Policy engine -> Versioned config store -> Data-plane evaluator or agent -> SRE console
        |       -> Source-of-Truth Write + Transactional Outbox
        |
        +--> Query / Serving Path
        |       -> Data-plane evaluator or agent
        |       -> Canonical Store fallback when strong freshness is required
        |
        +--> Async/Event Path
        |       -> Event Bus / Stream Processing / Workflow Queues
        |       -> Admin/control-plane API / Audit/compliance service / Integration adapters
        |
        +--> Operations Path
                -> Admin Console / Audit / Reconciliation / Backfill / Disaster Recovery

Data Stores: Identity/policy store + token/session cache + key/secret store + immutable audit log + compliance warehouse
Ops/Integrations: Policy engine + key rotation + anomaly detection + access review + break-glass workflows
```

### Request And Data Flow

1. **Request entry:** actors enter through edge controls that authenticate, authorize, rate-limit, route, and attach trace context before reaching the feature flag platform service boundary.
2. **Synchronous command path:** correctness-sensitive mutations stay inside Propagation service -> Policy engine -> Versioned config store -> Data-plane evaluator or agent -> SRE console; this path performs validation, idempotency checks, source-of-truth writes, and outbox publication.
3. **Query path:** read-heavy traffic is served by Data-plane evaluator or agent; strong reads fall back to the canonical store when stale projections are unsafe.
4. **Async path:** Admin/control-plane API / Audit/compliance service / Integration adapters consume committed events for notifications, indexing, analytics, provider calls, ML/risk feedback, cleanup, and reconciliation.
5. **Operations path:** admin, audit, replay, reconciliation, backfill, and disaster-recovery workflows are isolated from user-facing latency but use the same immutable event/audit history.

### Component Responsibilities

- **Admin/control-plane API**: Owns admin/configuration mutations, tenant/resource ownership, policy changes, rollout controls, and slow-changing metadata.
- **Policy engine**: Evaluates versioned policy, quotas, eligibility, and configuration with deterministic decisions and audit-friendly reason codes.
- **Versioned config store**: Evaluates versioned policy, quotas, eligibility, and configuration with deterministic decisions and audit-friendly reason codes.
- **Data-plane evaluator or agent**: Serves latency-critical user traffic with minimal dependencies, cached policy/config, bounded fanout, and explicit backpressure.
- **Propagation service**: Distributes versioned configuration, policy, schema, or trace-context changes to serving nodes; tracks acknowledgements, lag, and rollback state.
- **Audit/compliance service**: Provides operator workflows for investigation, replay, correction, quarantine, approval, and immutable audit trails.
- **Integration adapters**: Normalizes external APIs and protocols, isolates credentials, maps provider errors, applies idempotent retries, and records provider references for reconciliation.
- **SRE console**: Gives operators topology, health, backlog, replay, quarantine, rollback, and incident runbook controls without touching primary data manually.

### Service Responsibility Matrix

| Layer | Services | Responsibility |
| --- | --- | --- |
| Edge/API boundary | API Gateway / WAF / Load Balancer | Authentication, authorization handoff, request validation, rate limits, routing, TLS termination, coarse abuse controls, and trace context propagation. |
| Core domain services | Propagation service, Policy engine, Versioned config store, Data-plane evaluator or agent, SRE console | Own feature flag platform business invariants, source-of-truth writes, state transitions, idempotency, and synchronous API responses. |
| Query/serving services | Data-plane evaluator or agent | Serve low-latency reads from caches, read models, indexes, or specialized serving stores while exposing freshness/consistency guarantees. |
| Async workers and integrations | Admin/control-plane API, Audit/compliance service, Integration adapters | Consume committed events, call external systems, retry safely, update projections, run cleanup, and isolate slow dependencies from user-facing latency. |
| Data and governance | OLTP DB / cache / search index / object store / warehouse / audit log | Separate canonical state from derived stores; support rebuild, partitioning, retention, encryption, backup, and analytical access. |
| Operations | Admin console / reconciliation / observability / runbooks | Provide support investigation, replay/backfill, manual correction, compliance evidence, SLO dashboards, and incident response. |

### Data Stores

- Strong metadata DB for tenants, policies, versions, and ownership.
- Read-optimized replicated config store.
- Append-only audit log.
- Event bus for propagation.
- Time-series/trace store for observability.

### Async Event Contracts

Use an outbox table or transactional event publisher so state changes and emitted events cannot diverge.

```json
{
  "event_id": "evt_01H...",
  "event_type": "feature.flags.updated.v1",
  "occurred_at": "2026-05-25T10:15:30Z",
  "producer": "feature-flags-service",
  "tenant_id": "tenant_123",
  "aggregate_id": "featureFlag_123",
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

- `feature.flags.created.v1`
- `feature.flags.updated.v1`
- `feature.flags.state_changed.v1`
- `feature.flags.deleted_or_expired.v1`
- `feature.flags.policy_denied.v1`
- `feature.flags.operation_failed.v1`

---

## 6. Low-Level Design (LLD)

The low-level design describes service contracts, module boundaries, state transitions, and idempotency/concurrency controls.

### API Contracts

Use REST for public/admin APIs and gRPC for internal service-to-service calls. Every mutation accepts an idempotency key. Every list API supports cursor pagination, filtering, and a stable sort.

### Public APIs

```http
POST /v1/feature-flags
Idempotency-Key: <uuid>
Authorization: Bearer <token>
Content-Type: application/json

{
  "client_request_id": "req_123",
  "attributes": {}
}
```

```http
GET /v1/feature-flags/{id}
Authorization: Bearer <token>
```

```http
GET /v1/feature-flags?cursor=<cursor>&limit=50&filter=<filter>&sort=<sort>
Authorization: Bearer <token>
```

```http
PATCH /v1/feature-flags/{id}
Idempotency-Key: <uuid>
Content-Type: application/json

{
  "expected_version": 12,
  "changes": {}
}
```

```http
POST /v1/feature-flags/{id}/actions/{action}
Idempotency-Key: <uuid>
Content-Type: application/json

{
  "reason": "operator_or_user_reason",
  "parameters": {}
}
```

### Domain-Specific API Examples

```http
POST /v1/feature-flags/versions
Idempotency-Key: <uuid>

{
  "change_reason": "rollout_or_policy_update",
  "spec": {},
  "validation_mode": "strict"
}
```

```http
POST /v1/feature-flags/evaluate

{
  "principal": "user_or_service_123",
  "action": "read|write|execute",
  "resource": "resource_123",
  "context": {}
}
```

```http
GET /v1/audit/events?resource_id={id}&from=2026-05-25T00:00:00Z
```

### Internal APIs

```protobuf
service FeatureFlagService {
  rpc CreateFeatureFlag(CreateFeatureFlagRequest) returns (FeatureFlag);
  rpc GetFeatureFlag(GetFeatureFlagRequest) returns (FeatureFlag);
  rpc UpdateFeatureFlag(UpdateFeatureFlagRequest) returns (FeatureFlag);
  rpc EvaluateFeatureFlag(EvaluateFeatureFlagRequest) returns (EvaluateFeatureFlagResponse);
  rpc ListFeatureFlagEvents(ListFeatureFlagEventsRequest) returns (stream FeatureFlagEvent);
}
```

### Error Model

- `400`: invalid request or unsupported transition.
- `401/403`: missing identity or policy denial.
- `404`: resource not found or intentionally hidden by authorization.
- `409`: version conflict, duplicate idempotency key with different payload, or state transition race.
- `429`: tenant/user/key quota exceeded with `Retry-After`.
- `5xx`: dependency or internal failure. Return a request ID for support and tracing.

### Core Modules

- `FeatureFlagController`: validates requests, extracts identity, enforces coarse rate limits, and maps errors to API responses.
- `FeatureFlagApplicationService`: owns use-case orchestration, idempotency, retries, and state transitions.
- `FeatureFlagDomainModel`: contains state machine rules, validation, and invariants that must not leak into controllers.
- `FeatureFlagRepository`: hides database access, optimistic locking, partitioning, and pagination details.
- `FeatureFlagPolicyEvaluator`: centralizes authorization, tenant isolation, quota, and abuse decisions.
- `FeatureFlagEventPublisher`: writes outbox records and publishes domain events to the broker.
- `FeatureFlagReadModelProjector`: builds caches, search documents, counters, and dashboard projections asynchronously.

### Interfaces

```java
interface FeatureFlagRepository {
    Optional<FeatureFlag> findById(FeatureFlagId id, ReadConsistency consistency);
    Page<FeatureFlag> list(FeatureFlagQuery query, Cursor cursor, int limit);
    FeatureFlag save(FeatureFlag aggregate, ExpectedVersion expectedVersion);
}

interface FeatureFlagPolicyEvaluator {
    PolicyDecision canRead(Principal principal, FeatureFlag resource);
    PolicyDecision canMutate(Principal principal, FeatureFlag resource, Action action);
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

---

## 7. Architecture Components

Each component has one clear owner and a rebuild story for derived state. This avoids coupling operational workflows to the latency budget of the primary user path.

### Component And Store Ownership

The architecture should be read as a set of ownership boundaries: command services own mutations, query services own low-latency reads, async workers own projections, and operators own audit/replay workflows.

### Architecture Design

```text
feature flag platform Architecture

Actors / Clients / Partner Systems
        |
        v
DNS / Global Traffic Manager / CDN where useful
        |
        v
API Gateway / WAF / Auth / Rate Limits / Request Router
        |
        +--> Synchronous Command Path
        |       -> Propagation service -> Policy engine -> Versioned config store -> Data-plane evaluator or agent -> SRE console
        |       -> Source-of-Truth Write + Transactional Outbox
        |
        +--> Query / Serving Path
        |       -> Data-plane evaluator or agent
        |       -> Canonical Store fallback when strong freshness is required
        |
        +--> Async/Event Path
        |       -> Event Bus / Stream Processing / Workflow Queues
        |       -> Admin/control-plane API / Audit/compliance service / Integration adapters
        |
        +--> Operations Path
                -> Admin Console / Audit / Reconciliation / Backfill / Disaster Recovery

Data Stores: Identity/policy store + token/session cache + key/secret store + immutable audit log + compliance warehouse
Ops/Integrations: Policy engine + key rotation + anomaly detection + access review + break-glass workflows
```

### Request And Data Flow

1. **Request entry:** actors enter through edge controls that authenticate, authorize, rate-limit, route, and attach trace context before reaching the feature flag platform service boundary.
2. **Synchronous command path:** correctness-sensitive mutations stay inside Propagation service -> Policy engine -> Versioned config store -> Data-plane evaluator or agent -> SRE console; this path performs validation, idempotency checks, source-of-truth writes, and outbox publication.
3. **Query path:** read-heavy traffic is served by Data-plane evaluator or agent; strong reads fall back to the canonical store when stale projections are unsafe.
4. **Async path:** Admin/control-plane API / Audit/compliance service / Integration adapters consume committed events for notifications, indexing, analytics, provider calls, ML/risk feedback, cleanup, and reconciliation.
5. **Operations path:** admin, audit, replay, reconciliation, backfill, and disaster-recovery workflows are isolated from user-facing latency but use the same immutable event/audit history.

### Component Responsibilities

- **Admin/control-plane API**: Owns admin/configuration mutations, tenant/resource ownership, policy changes, rollout controls, and slow-changing metadata.
- **Policy engine**: Evaluates versioned policy, quotas, eligibility, and configuration with deterministic decisions and audit-friendly reason codes.
- **Versioned config store**: Evaluates versioned policy, quotas, eligibility, and configuration with deterministic decisions and audit-friendly reason codes.
- **Data-plane evaluator or agent**: Serves latency-critical user traffic with minimal dependencies, cached policy/config, bounded fanout, and explicit backpressure.
- **Propagation service**: Distributes versioned configuration, policy, schema, or trace-context changes to serving nodes; tracks acknowledgements, lag, and rollback state.
- **Audit/compliance service**: Provides operator workflows for investigation, replay, correction, quarantine, approval, and immutable audit trails.
- **Integration adapters**: Normalizes external APIs and protocols, isolates credentials, maps provider errors, applies idempotent retries, and records provider references for reconciliation.
- **SRE console**: Gives operators topology, health, backlog, replay, quarantine, rollback, and incident runbook controls without touching primary data manually.

### Service Responsibility Matrix

| Layer | Services | Responsibility |
| --- | --- | --- |
| Edge/API boundary | API Gateway / WAF / Load Balancer | Authentication, authorization handoff, request validation, rate limits, routing, TLS termination, coarse abuse controls, and trace context propagation. |
| Core domain services | Propagation service, Policy engine, Versioned config store, Data-plane evaluator or agent, SRE console | Own feature flag platform business invariants, source-of-truth writes, state transitions, idempotency, and synchronous API responses. |
| Query/serving services | Data-plane evaluator or agent | Serve low-latency reads from caches, read models, indexes, or specialized serving stores while exposing freshness/consistency guarantees. |
| Async workers and integrations | Admin/control-plane API, Audit/compliance service, Integration adapters | Consume committed events, call external systems, retry safely, update projections, run cleanup, and isolate slow dependencies from user-facing latency. |
| Data and governance | OLTP DB / cache / search index / object store / warehouse / audit log | Separate canonical state from derived stores; support rebuild, partitioning, retention, encryption, backup, and analytical access. |
| Operations | Admin console / reconciliation / observability / runbooks | Provide support investigation, replay/backfill, manual correction, compliance evidence, SLO dashboards, and incident response. |

### Data Stores

- Strong metadata DB for tenants, policies, versions, and ownership.
- Read-optimized replicated config store.
- Append-only audit log.
- Event bus for propagation.
- Time-series/trace store for observability.

---

## 8. Deep Dive of Each Component/Service

These are the areas interviewers usually drill into because they determine whether the design survives real production traffic and failure modes.

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

- **targeting**: Evaluate flag rules locally in SDKs with signed config snapshots.
- **sdk caching**: SDKs must serve cached config during control-plane outages.
- **rollout**: Use progressive rollout, kill switches, and automatic rollback.
- **consistency**: State per-operation consistency: strong for metadata/booking/money, eventual for analytics/counters.
- **audit**: Store immutable actor/action/resource/outcome logs and make them searchable.

---

## 9. Component Optimization

Optimization focuses on hot keys, fanout, cache behavior, backpressure, partitioning, cost, and safe degradation before adding more infrastructure.

| Bottleneck | Why It Happens | Mitigation |
|---|---|---|
| Hot partition or celebrity object | A small number of keys receives a disproportionate share of reads/writes. | Key splitting, local caches, write buffering, async aggregation, and hybrid fanout. |
| Synchronous dependency chain | User-visible request waits on too many downstream systems. | Move non-critical work to events, use timeouts, fallbacks, and circuit breakers. |
| Cache stampede | Popular key expires or is invalidated under high concurrency. | Soft TTL, request coalescing, jittered expiration, stale-while-revalidate. |
| Large tenant noisy neighbor | One tenant consumes shared pool capacity. | Per-tenant quotas, partitioning, fairness queues, and dedicated capacity for top tenants. |
| Reindex/rebuild pressure | Backfills or rebuilds compete with online serving. | Separate backfill pools, rate limits, shadow indexes, and atomic cutover. |
| Operational blind spots | Failures occur without enough context to debug. | Correlate logs, metrics, traces, audit events, and deployment versions. |

### Cost Model

### Cost Drivers

- replicated config storage.
- hot-path evaluator compute.
- audit retention.
- agent fleet management.
- cross-region replication and compliance controls.

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

---

## 10. Observability

Observability must prove the design is healthy from the user journey down to queues, storage, workers, cache tiers, and external dependencies.

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

### Deployment And Operations

- Run stateless services on Kubernetes or an equivalent orchestrator across at least three availability zones.
- Use infrastructure as code for networking, IAM, databases, queues, caches, alarms, and dashboards.
- Deploy with canary or blue/green releases. Gate rollout on error rate, latency, saturation, and domain-specific correctness metrics.
- Apply backward-compatible database migrations: expand, dual-write/backfill if needed, verify, then contract.
- Separate control plane and data plane where the hot path must survive admin-plane outages.
- Use feature flags and kill switches for risky paths, expensive jobs, and external integrations.
- Maintain runbooks for failover, replay, data repair, provider outage, abuse incident, and privacy/security incident.

---

## 11. Considerations & Assumptions

These considerations make the design defensible: security, privacy, failure handling, cost, trade-offs, and follow-up answers.

### Security, Privacy, Abuse Prevention, And Compliance

- Authenticate every request with user, service, or device identity; use mTLS for internal service calls.
- Authorize by tenant, ownership, role, resource state, and contextual policy. Do not rely on front-end checks.
- Encrypt data in transit and at rest. Use tenant-scoped or domain-scoped keys for sensitive data.
- Store secrets in a managed vault and rotate credentials. Never log tokens, passwords, private keys, or raw sensitive payloads.
- Apply input validation, WAF rules, bot detection, rate limits, and abuse reputation checks.
- Keep immutable audit logs for administrative actions, policy decisions, state transitions, and data exports.
- Implement data retention, deletion, legal hold, and privacy export workflows if the domain stores personal data.
- Use least privilege for operators and services; require break-glass approvals for emergency access.

### Reliability, Failure Modes, And Recovery

| Failure Mode | Impact | Recovery Strategy |
|---|---|---|
| Primary DB shard unavailable | Mutations for affected shard fail or degrade. | Multi-AZ failover, circuit breaker, queued writes only if semantics allow, clear user messaging. |
| Cache cluster loss | Higher latency and DB load. | Request coalescing, local cache, rate limiting, and progressive cache warmup. |
| Event broker lag | Search, analytics, notifications, or projections become stale. | Lag alerts, autoscale consumers, replay from offsets, and expose freshness to users/internal teams. |
| Region outage | Users in region lose access or move to remote region. | Global traffic failover, replicated critical data, documented RPO/RTO, and dependency evacuation runbooks. |
| Bad deployment or config | Elevated errors or wrong decisions. | Canary, automatic rollback, config version pinning, kill switches, and audit trail. |
| Poison message or corrupt record | Consumer stalls or produces bad projection. | DLQ, quarantine, schema validation, replay tooling, and repair jobs. |

### Key Trade-Offs

| Decision | Option A | Option B | Interview Guidance |
|---|---|---|---|
| Consistency | Strong consistency | Eventual consistency | Use strong consistency for money, scarce inventory, access control, and metadata that gates safety; use eventual consistency for counters, feeds, analytics, and search. |
| Fanout/projection | Compute on write | Compute on read | Write-time projections reduce read latency but increase write amplification; read-time computation is flexible but can fail at peak. |
| Storage | Single general-purpose DB | Polyglot stores | Start simple, then split when access patterns, scale, or correctness boundaries justify it. |
| Multi-region | Active-passive | Active-active | Active-passive is simpler; active-active needs conflict handling, data residency design, and stronger operational maturity. |
| Build vs buy | Managed service | Custom platform | Buy undifferentiated primitives unless scale, cost, compliance, or product semantics require ownership. |

### Common Interview Follow-Ups

- How does the design change at 10x traffic or with one extremely large tenant?
- Which data must be strongly consistent and which can lag?
- What is the exact partition key and how do you migrate when it becomes hot?
- How do you replay events or rebuild projections without duplicating side effects?
- What breaks during a regional outage and what is the expected RPO/RTO?
- How do you detect abuse, data leakage, or unauthorized access?
- What metrics prove the system is healthy from the user perspective?

### Final Interview Checklist

- Clarify product scope and non-goals first.
- State scale assumptions and convert them into QPS, storage, bandwidth, and partition counts.
- Draw the read path, write path, async path, and operational path separately.
- Identify the source of truth for every entity and every derived view.
- Explain idempotency, retries, ordering, backpressure, and failure recovery.
- Cover security, privacy, compliance, deployment, observability, and cost before closing.

---

## Summary: Interview Talking Points

Use this section to drive the final five-minute whiteboard summary and to prepare for bar-raiser follow-ups.

### What A Strong Interview Answer Must Demonstrate

- **Correctness boundary:** the canonical aggregate store and immutable event/audit history is the authority; derived caches, search indexes, dashboards, and analytics must be rebuildable.
- **Hot path clarity:** start from `targeting` and walk the synchronous command path before discussing secondary features.
- **Service ownership:** explicitly assign responsibilities to Admin/control-plane API, Policy engine, Versioned config store, Data-plane evaluator or agent, Propagation service, Audit/compliance service; avoid vague boxes that do not own data or decisions.
- **Data ownership:** ground the design in `canonical aggregate, idempotency, event, and audit tables` and explain partitioning, indexes, retention, and replay.
- **Event model:** use `feature.flags.created.v1, feature.flags.updated.v1, feature.flags.state_changed.v1, feature.flags.deleted_or_expired.v1, feature.flags.policy_denied.v1, feature.flags.operation_failed.v1` to decouple slow work while preserving idempotency and ordering per aggregate.
- **Operational maturity:** include backpressure, DLQs, reconciliation, runbooks, audit trails, and safe manual correction.

### Bar-Raiser Drill-Down Prompts

- Which service owns the final decision for `targeting`, and what exact write makes it durable?
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
- State identity/policy source of truth, token/session lifecycle, audit, key rotation, and break-glass.
- Treat logs and support access as sensitive surfaces.
- Explain revocation propagation and consistency.

### 5-Minute Whiteboard Structure

- First minute: scope actors, constraints, and `targeting`.
- Minutes 2-3: draw edge, command path, query path, async path, and data stores; name Admin/control-plane API, Policy engine, Versioned config store, Data-plane evaluator or agent, Propagation service, Audit/compliance service.
- Minute 4: walk one critical flow and call out idempotency, consistency, and failure recovery.
- Minute 5: close with scale bottlenecks, security/privacy, observability, cost, and trade-offs.
