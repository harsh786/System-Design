# Design Quora / Stack Overflow Q&A feed - System Design Deep Dive

**Problem #28**  
**Category:** Knowledge/social  
**Primary pattern:** social feed  
**Deep-dive focus:** topics, dedupe, voting, reputation, expert routing

## 0. Interview Framing

A consumer graph and ranking system where feed freshness, celebrity fanout, hot-object counters, ML ranking, and moderation define the architecture.

In an interview, start by narrowing the product scope, then anchor the design around the highest-risk path. For this problem, the highest-risk path is usually the path involving **topics**. Keep secondary capabilities asynchronous unless they affect correctness, money, privacy, or user-visible availability.

## 1. Requirements

### Functional Requirements

- Create and read user-generated content.
- Build ranked feeds or discussion views.
- Apply graph/privacy filters.
- Track reactions, comments, follows, and moderation state.
- Expose admin operations for investigation, replay, correction, and policy changes.
- Publish domain events for analytics, search, notifications, and downstream systems.
- Support regional failover and controlled degradation for non-critical features.

### Non-Functional Requirements

- feed read latency stable under celebrity and viral spikes.
- eventual consistency acceptable for counters and ranking.
- strong privacy checks before serving content.
- safe degradation to cached/ranked feed.

### Non-Goals

- Do not design every client UI screen; focus on backend, data, and platform contracts.
- Do not optimize rare administrative workflows ahead of the user-visible hot path.
- Do not couple offline analytics correctness to online request latency.
- Do not rely on one shared database node as the scalability plan.

## 2. Capacity, Traffic, And Size Estimation

Use these as interview-scale assumptions. State that numbers are adjustable and use formulas so the interviewer can change scale.

| Dimension | Baseline Assumption |
|---|---|
| Active users | 100M DAU, 500M MAU |
| Content writes | 20M/day |
| Feed reads | 5B/day, 5x daily peak |
| Graph edges | 10B+ relationships |
| Latency target | p99 < 300 ms for feed reads |

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
POST /v1/social-objects
Idempotency-Key: <uuid>
Authorization: Bearer <token>
Content-Type: application/json

{
  "client_request_id": "req_123",
  "attributes": {}
}
```

```http
GET /v1/social-objects/{id}
Authorization: Bearer <token>
```

```http
GET /v1/social-objects?cursor=<cursor>&limit=50&filter=<filter>&sort=<sort>
Authorization: Bearer <token>
```

```http
PATCH /v1/social-objects/{id}
Idempotency-Key: <uuid>
Content-Type: application/json

{
  "expected_version": 12,
  "changes": {}
}
```

```http
POST /v1/social-objects/{id}/actions/{action}
Idempotency-Key: <uuid>
Content-Type: application/json

{
  "reason": "operator_or_user_reason",
  "parameters": {}
}
```

### Domain-Specific API Examples

```http
POST /v1/social-objects
Idempotency-Key: <uuid>

{
  "author_id": "user_123",
  "visibility": "public|followers|private",
  "body_ref": "object://content/body_123"
}
```

```http
GET /v1/feed/home?cursor=<rank_cursor>&limit=50
```

```http
POST /v1/social-objects/{id}/reactions
Idempotency-Key: <uuid>

{"reaction_type": "like"}
```

### Internal APIs

```protobuf
service SocialObjectService {
  rpc CreateSocialObject(CreateSocialObjectRequest) returns (SocialObject);
  rpc GetSocialObject(GetSocialObjectRequest) returns (SocialObject);
  rpc UpdateSocialObject(UpdateSocialObjectRequest) returns (SocialObject);
  rpc EvaluateSocialObject(EvaluateSocialObjectRequest) returns (EvaluateSocialObjectResponse);
  rpc ListSocialObjectEvents(ListSocialObjectEventsRequest) returns (stream SocialObjectEvent);
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
  "event_type": "social.objects.updated.v1",
  "occurred_at": "2026-05-25T10:15:30Z",
  "producer": "social-objects-service",
  "tenant_id": "tenant_123",
  "aggregate_id": "socialObject_123",
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

- `social.objects.created.v1`
- `social.objects.updated.v1`
- `social.objects.state_changed.v1`
- `social.objects.deleted_or_expired.v1`
- `social.objects.policy_denied.v1`
- `social.objects.operation_failed.v1`

## 5. High-Level Architecture

### Architecture Design

```text
Quora / Stack Overflow Q&A feed Architecture

Actors / Clients / Partner Systems
        |
        v
DNS / Global Traffic Manager / CDN where useful
        |
        v
API Gateway / WAF / Auth / Rate Limits / Request Router
        |
        +--> Synchronous Command Path
        |       -> Graph service -> Feed ranking service -> Media service -> Content write API -> Feed cache
        |       -> Source-of-Truth Write + Transactional Outbox
        |
        +--> Query / Serving Path
        |       -> Feed ranking service / Feed cache
        |       -> Canonical Store fallback when strong freshness is required
        |
        +--> Async/Event Path
        |       -> Event Bus / Stream Processing / Workflow Queues
        |       -> Fanout service / Moderation pipeline / Notification service / Analytics/feature pipeline
        |
        +--> Operations Path
                -> Admin Console / Audit / Reconciliation / Backfill / Disaster Recovery

Data Stores: Raw event log + feature/index stores + serving cache + OLAP/warehouse + model artifacts where needed
Ops/Integrations: Stream/batch processors + ranking/model serving + experimentation + data quality monitors
```

### Request And Data Flow

1. **Request entry:** actors enter through edge controls that authenticate, authorize, rate-limit, route, and attach trace context before reaching the Quora / Stack Overflow Q&A feed service boundary.
2. **Synchronous command path:** correctness-sensitive mutations stay inside Graph service -> Feed ranking service -> Media service -> Content write API -> Feed cache; this path performs validation, idempotency checks, source-of-truth writes, and outbox publication.
3. **Query path:** read-heavy traffic is served by Feed ranking service / Feed cache; strong reads fall back to the canonical store when stale projections are unsafe.
4. **Async path:** Fanout service / Moderation pipeline / Notification service / Analytics/feature pipeline consume committed events for notifications, indexing, analytics, provider calls, ML/risk feedback, cleanup, and reconciliation.
5. **Operations path:** admin, audit, replay, reconciliation, backfill, and disaster-recovery workflows are isolated from user-facing latency but use the same immutable event/audit history.

### Component Responsibilities

- **Content write API**: Validates content mutations, stores canonical metadata, enforces ownership/privacy/moderation gates, and emits events for fanout/indexing.
- **Graph service**: Owns relationship edges, privacy rules, graph mutations, fanout eligibility, and graph-derived query projections.
- **Fanout service**: Expands committed events to recipients/subscribers, handles retries, ordering where scoped, backpressure, and DLQs.
- **Feed ranking service**: Generates/ranks candidates using features, business rules, freshness constraints, online feedback, and experimentation controls.
- **Feed cache**: Serves hot derived data with TTLs/invalidation, protects backing stores, and never becomes source of truth for critical state.
- **Media service**: Stores large binary payloads outside OLTP, performs validation/scanning/transcoding where needed, and serves via signed URLs/CDN.
- **Moderation pipeline**: Scores abuse/fraud/safety risk, applies policy actions, records explainable decisions, and routes uncertain cases to review.
- **Notification service**: Delivers push/email/SMS/in-app notifications using preferences, templates, priority queues, retries, and provider failover.
- **Analytics/feature pipeline**: Consumes immutable events, computes rollups, powers dashboards/exports, and stays off the synchronous correctness path.

### Service Responsibility Matrix

| Layer | Services | Responsibility |
| --- | --- | --- |
| Edge/API boundary | API Gateway / WAF / Load Balancer | Authentication, authorization handoff, request validation, rate limits, routing, TLS termination, coarse abuse controls, and trace context propagation. |
| Core domain services | Graph service, Feed ranking service, Media service, Content write API, Feed cache | Own Quora / Stack Overflow Q&A feed business invariants, source-of-truth writes, state transitions, idempotency, and synchronous API responses. |
| Query/serving services | Feed ranking service, Feed cache | Serve low-latency reads from caches, read models, indexes, or specialized serving stores while exposing freshness/consistency guarantees. |
| Async workers and integrations | Fanout service, Moderation pipeline, Notification service, Analytics/feature pipeline | Consume committed events, call external systems, retry safely, update projections, run cleanup, and isolate slow dependencies from user-facing latency. |
| Data and governance | OLTP DB / cache / search index / object store / warehouse / audit log | Separate canonical state from derived stores; support rebuild, partitioning, retention, encryption, backup, and analytical access. |
| Operations | Admin console / reconciliation / observability / runbooks | Provide support investigation, replay/backfill, manual correction, compliance evidence, SLO dashboards, and incident response. |

### Data Stores

- User/profile store.
- Graph store for follow/friend edges.
- Content metadata store.
- Feed cache/materialized timeline store.
- Object storage and CDN for media.
- Search and recommendation indexes.

## 6. Low-Level Design

### Core Modules

- `SocialObjectController`: validates requests, extracts identity, enforces coarse rate limits, and maps errors to API responses.
- `SocialObjectApplicationService`: owns use-case orchestration, idempotency, retries, and state transitions.
- `SocialObjectDomainModel`: contains state machine rules, validation, and invariants that must not leak into controllers.
- `SocialObjectRepository`: hides database access, optimistic locking, partitioning, and pagination details.
- `SocialObjectPolicyEvaluator`: centralizes authorization, tenant isolation, quota, and abuse decisions.
- `SocialObjectEventPublisher`: writes outbox records and publishes domain events to the broker.
- `SocialObjectReadModelProjector`: builds caches, search documents, counters, and dashboard projections asynchronously.

### Interfaces

```java
interface SocialObjectRepository {
    Optional<SocialObject> findById(SocialObjectId id, ReadConsistency consistency);
    Page<SocialObject> list(SocialObjectQuery query, Cursor cursor, int limit);
    SocialObject save(SocialObject aggregate, ExpectedVersion expectedVersion);
}

interface SocialObjectPolicyEvaluator {
    PolicyDecision canRead(Principal principal, SocialObject resource);
    PolicyDecision canMutate(Principal principal, SocialObject resource, Action action);
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
  -> owns or can access -> SocialObject
  -> emits -> SocialObjectEvent
  -> produces -> ReadModel / SearchDocument / Metric
  -> audited by -> AuditLog
```

### Core Tables

| Table | Important Columns |
|---|---|
| `users` | `id, tenant_id, handle, profile_ref, privacy_level, state, created_at` |
| `posts` | `id, author_id, body_ref, media_refs, visibility, rank_seed, moderation_state, created_at` |
| `follows` | `follower_id, followee_id, state, created_at, source` |
| `feed_items` | `user_id, feed_type, score_bucket, item_id, rank_features_ref, inserted_at` |
| `reactions` | `target_id, user_id, reaction_type, created_at, state` |
| `comments` | `id, parent_id, root_id, author_id, body_ref, depth, score, moderation_state` |
| `social_objects` | `id, owner_id, object_type, visibility, payload_ref, moderation_state, created_at` |

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

- **topics**: Model topics/tags as sparse many-to-many entities and denormalize for ranking.
- **dedupe**: Deduplicate alerts by fingerprint and suppress during maintenance.
- **voting**: Use idempotent votes and aggregate counters asynchronously with anti-fraud checks.
- **reputation**: Make reputation updates idempotent and fraud-aware.
- **expert routing**: Rank candidates by expertise, availability, reputation, and freshness.

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

- timeline cache memory.
- fanout write amplification.
- media processing and egress.
- ML feature generation and ranking.
- moderation review queues.

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
- **Hot path clarity:** start from `topics` and walk the synchronous command path before discussing secondary features.
- **Service ownership:** explicitly assign responsibilities to Content write API, Graph service, Fanout service, Feed ranking service, Feed cache, Media service; avoid vague boxes that do not own data or decisions.
- **Data ownership:** ground the design in `canonical aggregate, idempotency, event, and audit tables` and explain partitioning, indexes, retention, and replay.
- **Event model:** use `social.objects.created.v1, social.objects.updated.v1, social.objects.state_changed.v1, social.objects.deleted_or_expired.v1, social.objects.policy_denied.v1, social.objects.operation_failed.v1` to decouple slow work while preserving idempotency and ordering per aggregate.
- **Operational maturity:** include backpressure, DLQs, reconciliation, runbooks, audit trails, and safe manual correction.

### Bar-Raiser Drill-Down Prompts

- Which service owns the final decision for `topics`, and what exact write makes it durable?
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
- Separate raw ingestion, normalization, indexing/features, serving, and offline analytics.
- Call out freshness, backfills, dedupe, quality checks, and ranking/model rollout.
- Avoid making the online serving path depend on slow batch jobs.

### 5-Minute Whiteboard Structure

- First minute: scope actors, constraints, and `topics`.
- Minutes 2-3: draw edge, command path, query path, async path, and data stores; name Content write API, Graph service, Fanout service, Feed ranking service, Feed cache, Media service.
- Minute 4: walk one critical flow and call out idempotency, consistency, and failure recovery.
- Minute 5: close with scale bottlenecks, security/privacy, observability, cost, and trade-offs.
