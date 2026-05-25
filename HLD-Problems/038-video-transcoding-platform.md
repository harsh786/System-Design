# Design a video transcoding platform - System Design Deep Dive

**Problem #38**  
**Category:** Batch/media  
**Primary pattern:** data scheduling  
**Deep-dive focus:** job queue, workers, retries, priority, cost control

## 0. Interview Framing

A data or execution platform where orchestration, backpressure, isolation, retries, lineage, freshness, and cost-aware scheduling drive the design.

In an interview, start by narrowing the product scope, then anchor the design around the highest-risk path. For this problem, the highest-risk path is usually the path involving **job queue**. Keep secondary capabilities asynchronous unless they affect correctness, money, privacy, or user-visible availability.

## 1. Requirements

### Functional Requirements

- Ingest, process, and serve media assets.
- Generate renditions, thumbnails, metadata, and moderation signals.
- Support playback/browse/search flows.
- Manage rights, TTL, retention, and takedowns.
- Expose admin operations for investigation, replay, correction, and policy changes.
- Publish domain events for analytics, search, notifications, and downstream systems.
- Support regional failover and controlled degradation for non-critical features.

### Non-Functional Requirements

- durable scheduling state and exactly-once-or-idempotent execution semantics.
- backpressure and fair sharing across tenants.
- replay/backfill without corrupting current state.
- observable job lifecycle and lineage.
- cost-aware autoscaling and workload isolation.

### Non-Goals

- Do not design every client UI screen; focus on backend, data, and platform contracts.
- Do not optimize rare administrative workflows ahead of the user-visible hot path.
- Do not couple offline analytics correctness to online request latency.
- Do not rely on one shared database node as the scalability plan.

## 2. Capacity, Traffic, And Size Estimation

Use these as interview-scale assumptions. State that numbers are adjustable and use formulas so the interviewer can change scale.

| Dimension | Baseline Assumption |
|---|---|
| Tenants/workspaces | 10K tenants with noisy-neighbor isolation |
| Ingest/events | 1M events/sec or 100K jobs/day depending on system |
| State/checkpoints | TB/day of operational metadata and logs |
| Retention | hot days, warm months, archive years |
| Freshness target | sub-second to 15 minutes depending on workload tier |

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
POST /v1/media-assets
Idempotency-Key: <uuid>
Authorization: Bearer <token>
Content-Type: application/json

{
  "client_request_id": "req_123",
  "attributes": {}
}
```

```http
GET /v1/media-assets/{id}
Authorization: Bearer <token>
```

```http
GET /v1/media-assets?cursor=<cursor>&limit=50&filter=<filter>&sort=<sort>
Authorization: Bearer <token>
```

```http
PATCH /v1/media-assets/{id}
Idempotency-Key: <uuid>
Content-Type: application/json

{
  "expected_version": 12,
  "changes": {}
}
```

```http
POST /v1/media-assets/{id}/actions/{action}
Idempotency-Key: <uuid>
Content-Type: application/json

{
  "reason": "operator_or_user_reason",
  "parameters": {}
}
```

### Domain-Specific API Examples

```http
POST /v1/media-assets/runs
Idempotency-Key: <uuid>

{
  "trigger": "manual|schedule|event",
  "parameters": {},
  "priority": "normal"
}
```

```http
POST /v1/media-assets/runs/{run_id}/cancel
Idempotency-Key: <uuid>

{"reason": "operator_request"}
```

```http
GET /v1/media-assets/runs/{run_id}/logs?cursor=<cursor>&limit=1000
```

### Internal APIs

```protobuf
service MediaAssetService {
  rpc CreateMediaAsset(CreateMediaAssetRequest) returns (MediaAsset);
  rpc GetMediaAsset(GetMediaAssetRequest) returns (MediaAsset);
  rpc UpdateMediaAsset(UpdateMediaAssetRequest) returns (MediaAsset);
  rpc EvaluateMediaAsset(EvaluateMediaAssetRequest) returns (EvaluateMediaAssetResponse);
  rpc ListMediaAssetEvents(ListMediaAssetEventsRequest) returns (stream MediaAssetEvent);
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
  "event_type": "media.assets.updated.v1",
  "occurred_at": "2026-05-25T10:15:30Z",
  "producer": "media-assets-service",
  "tenant_id": "tenant_123",
  "aggregate_id": "mediaAsset_123",
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

- `media.assets.created.v1`
- `media.assets.updated.v1`
- `media.assets.state_changed.v1`
- `media.assets.deleted_or_expired.v1`
- `media.assets.policy_denied.v1`
- `media.assets.operation_failed.v1`

## 5. High-Level Architecture

### Architecture Design

```text
a video transcoding platform Architecture

Actors / Clients / Partner Systems
        |
        v
DNS / Global Traffic Manager / CDN where useful
        |
        v
API Gateway / WAF / Auth / Rate Limits / Request Router
        |
        +--> Synchronous Command Path
        |       -> Dispatcher/queue -> State/checkpoint service -> Control-plane API -> Result serving API -> Alerting and retry manager -> Catalog/lineage service
        |       -> Source-of-Truth Write + Transactional Outbox
        |
        +--> Query / Serving Path
        |       -> Cache / Read model / Search or specialized index
        |       -> Canonical Store fallback when strong freshness is required
        |
        +--> Async/Event Path
        |       -> Event Bus / Stream Processing / Workflow Queues
        |       -> Worker pools / Scheduler
        |
        +--> Operations Path
                -> Admin Console / Audit / Reconciliation / Backfill / Disaster Recovery

Data Stores: Metadata DB + object storage for originals/renditions + CDN/origin cache + processing queues + analytics/search indexes
Ops/Integrations: Upload/transcoding workers + DRM/rights policy + moderation + CDN purge/lifecycle + QoE monitors
```

### Request And Data Flow

1. **Request entry:** actors enter through edge controls that authenticate, authorize, rate-limit, route, and attach trace context before reaching the video transcoding platform service boundary.
2. **Synchronous command path:** correctness-sensitive mutations stay inside Dispatcher/queue -> State/checkpoint service -> Control-plane API -> Result serving API -> Alerting and retry manager -> Catalog/lineage service; this path performs validation, idempotency checks, source-of-truth writes, and outbox publication.
3. **Query path:** read-heavy traffic is served by Cache / Read model / Search or specialized index; strong reads fall back to the canonical store when stale projections are unsafe.
4. **Async path:** Worker pools / Scheduler consume committed events for notifications, indexing, analytics, provider calls, ML/risk feedback, cleanup, and reconciliation.
5. **Operations path:** admin, audit, replay, reconciliation, backfill, and disaster-recovery workflows are isolated from user-facing latency but use the same immutable event/audit history.

### Component Responsibilities

- **Control-plane API**: Owns admin/configuration mutations, tenant/resource ownership, policy changes, rollout controls, and slow-changing metadata.
- **Scheduler**: Executes asynchronous work with leases, retries, idempotency, DLQ handling, and operational visibility.
- **Dispatcher/queue**: Selects eligible candidates, applies ranking/fairness constraints, issues leases/offers, and commits one valid assignment.
- **Worker pools**: Executes asynchronous work with leases, retries, idempotency, DLQ handling, and operational visibility.
- **State/checkpoint service**: Persists workflow/job progress, leases, checkpoints, dedupe state, and restart positions for exactly-once-effect processing.
- **Catalog/lineage service**: Owns searchable domain metadata, versioned publication state, moderation/status, and index-change events.
- **Result serving API**: Serves completed outputs, status, exports, or query results from read-optimized stores with authorization and freshness metadata.
- **Alerting and retry manager**: Owns retry policy, backoff, DLQ routing, escalation alerts, and operator controls for stuck or repeatedly failing work.

### Service Responsibility Matrix

| Layer | Services | Responsibility |
| --- | --- | --- |
| Edge/API boundary | API Gateway / WAF / Load Balancer | Authentication, authorization handoff, request validation, rate limits, routing, TLS termination, coarse abuse controls, and trace context propagation. |
| Core domain services | Dispatcher/queue, State/checkpoint service, Control-plane API, Result serving API, Alerting and retry manager, Catalog/lineage service | Own a video transcoding platform business invariants, source-of-truth writes, state transitions, idempotency, and synchronous API responses. |
| Query/serving services | Cache / Read model / Search or specialized index | Serve low-latency reads from caches, read models, indexes, or specialized serving stores while exposing freshness/consistency guarantees. |
| Async workers and integrations | Worker pools, Scheduler | Consume committed events, call external systems, retry safely, update projections, run cleanup, and isolate slow dependencies from user-facing latency. |
| Data and governance | OLTP DB / cache / search index / object store / warehouse / audit log | Separate canonical state from derived stores; support rebuild, partitioning, retention, encryption, backup, and analytical access. |
| Operations | Admin console / reconciliation / observability / runbooks | Provide support investigation, replay/backfill, manual correction, compliance evidence, SLO dashboards, and incident response. |

### Data Stores

- Metadata DB for jobs, DAGs, schedules, and ownership.
- Queue/event log for work dispatch.
- Checkpoint/state store.
- Object lake for raw and processed data.
- OLAP/time-series store for serving analytics.

## 6. Low-Level Design

### Core Modules

- `MediaAssetController`: validates requests, extracts identity, enforces coarse rate limits, and maps errors to API responses.
- `MediaAssetApplicationService`: owns use-case orchestration, idempotency, retries, and state transitions.
- `MediaAssetDomainModel`: contains state machine rules, validation, and invariants that must not leak into controllers.
- `MediaAssetRepository`: hides database access, optimistic locking, partitioning, and pagination details.
- `MediaAssetPolicyEvaluator`: centralizes authorization, tenant isolation, quota, and abuse decisions.
- `MediaAssetEventPublisher`: writes outbox records and publishes domain events to the broker.
- `MediaAssetReadModelProjector`: builds caches, search documents, counters, and dashboard projections asynchronously.

### Interfaces

```java
interface MediaAssetRepository {
    Optional<MediaAsset> findById(MediaAssetId id, ReadConsistency consistency);
    Page<MediaAsset> list(MediaAssetQuery query, Cursor cursor, int limit);
    MediaAsset save(MediaAsset aggregate, ExpectedVersion expectedVersion);
}

interface MediaAssetPolicyEvaluator {
    PolicyDecision canRead(Principal principal, MediaAsset resource);
    PolicyDecision canMutate(Principal principal, MediaAsset resource, Action action);
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
  -> owns or can access -> MediaAsset
  -> emits -> MediaAssetEvent
  -> produces -> ReadModel / SearchDocument / Metric
  -> audited by -> AuditLog
```

### Core Tables

| Table | Important Columns |
|---|---|
| `media_assets` | `id, owner_id, asset_type, original_object_ref, status, visibility, rights_policy_id, created_at` |
| `renditions` | `asset_id, rendition_type, codec, bitrate, dimensions, object_ref, checksum, state` |
| `processing_jobs` | `id, asset_id, job_type, priority, state, attempt, worker_id, updated_at` |
| `playback_sessions` | `id, user_id, asset_id, device_id, region, started_at, last_position_ms, quality_stats_ref` |
| `rights_policies` | `id, owner_id, regions_allowed, drm_required, valid_from, valid_to, state` |
| `workloads` | `id, tenant_id, type, schedule_or_trigger, priority, quota_class, state, created_at` |
| `runs` | `id, workload_id, attempt, state, started_at, finished_at, result_ref` |

### Storage Choices

- **Primary metadata:** relational DB when transactions, constraints, and auditability matter; wide-column or document DB when access is aggregate-oriented and ultra-high scale.
- **Cache:** Redis/Memcached/local in-process cache for hot reads, quotas, sessions, and derived views.
- **Event log:** Kafka/Pulsar/Kinesis-style append log for fanout, indexing, analytics, and replay.
- **Object storage:** large payloads, media, exports, logs, backups, and immutable artifacts.
- **Search/OLAP:** Elasticsearch/OpenSearch/Solr/ClickHouse/Druid/Pinot depending on query type.

### Indexes And Partitioning

- Partition primary records by `tenant_id`, `user_id`, `resource_id`, `conversation_id`, `object_id`, or another stable high-cardinality key that matches the hottest access pattern.
- Keep secondary indexes for lookup by status, owner, created time, expiration time, and external idempotency/provider IDs.
- Use time-bucketed partitions for event, log, metric, and audit tables.
- Use optimistic locking with `version` for normal updates; use short leases or serializable transactions only around scarce resources or correctness-critical transitions.

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

- **job queue**: Persist job state, retries, leases, and progress; workers must be idempotent.
- **workers**: Autoscale workers by queue depth, priority, and cost budget.
- **retries**: Use bounded retries with jitter, DLQs, poison-message handling, and replay tooling.
- **priority**: Separate priority queues or scheduling weights so low-priority work cannot starve critical work.
- **cost control**: Use spot/preemptible compute where safe, priority queues, and lifecycle tiers.

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

- worker compute hours.
- queue and metadata write volume.
- object storage and retention.
- OLAP/time-series serving capacity.
- log volume from jobs and tasks.

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
- **Hot path clarity:** start from `job queue` and walk the synchronous command path before discussing secondary features.
- **Service ownership:** explicitly assign responsibilities to Control-plane API, Scheduler, Dispatcher/queue, Worker pools, State/checkpoint service, Catalog/lineage service; avoid vague boxes that do not own data or decisions.
- **Data ownership:** ground the design in `canonical aggregate, idempotency, event, and audit tables` and explain partitioning, indexes, retention, and replay.
- **Event model:** use `media.assets.created.v1, media.assets.updated.v1, media.assets.state_changed.v1, media.assets.deleted_or_expired.v1, media.assets.policy_denied.v1, media.assets.operation_failed.v1` to decouple slow work while preserving idempotency and ordering per aggregate.
- **Operational maturity:** include backpressure, DLQs, reconciliation, runbooks, audit trails, and safe manual correction.

### Bar-Raiser Drill-Down Prompts

- Which service owns the final decision for `job queue`, and what exact write makes it durable?
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
- Separate upload completion from processing completion and playback availability.
- Explain object storage, CDN cache behavior, rendition generation, rights/moderation, and QoE telemetry.
- Do not put transcoding in the upload request path.

### 5-Minute Whiteboard Structure

- First minute: scope actors, constraints, and `job queue`.
- Minutes 2-3: draw edge, command path, query path, async path, and data stores; name Control-plane API, Scheduler, Dispatcher/queue, Worker pools, State/checkpoint service, Catalog/lineage service.
- Minute 4: walk one critical flow and call out idempotency, consistency, and failure recovery.
- Minute 5: close with scale bottlenecks, security/privacy, observability, cost, and trade-offs.
