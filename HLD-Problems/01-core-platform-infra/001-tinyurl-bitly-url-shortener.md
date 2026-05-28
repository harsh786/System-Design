# Design TinyURL / Bitly URL shortener - System Design Deep Dive

**Problem #1**  
**Category:** Core web scale  
**Primary pattern:** core platform  
**Deep-dive focus:** key generation, redirects, TTL, abuse prevention, analytics

## 0. Interview Framing

A platform primitive where correctness, low latency, predictable scaling, and operability matter more than product breadth.

In an interview, start by narrowing the product scope, then anchor the design around the highest-risk path. For this problem, the highest-risk path is usually the path involving **key generation**. Keep secondary capabilities asynchronous unless they affect correctness, money, privacy, or user-visible availability.

## 1. Requirements

### Functional Requirements

- Create one or many short links for long URLs.
- Support generated short codes, optional custom aliases, custom domains, TTL, and redirect type.
- Redirect short URLs with very low latency.
- Fetch link metadata for owners/admins without exposing private data on the public redirect path.
- Track click analytics without slowing redirects.
- Serve frequently accessed short URLs from edge/cache tiers.
- Prevent code conflicts when many users create links concurrently.
- Block phishing, malware, spam, and abusive destinations.
- Expose admin operations for investigation, replay, correction, and policy changes.
- Publish domain events for analytics, search, notifications, and downstream systems.
- Support regional failover and controlled degradation for non-critical features.

### Non-Functional Requirements

- p99 latency under 150 ms for online decisions.
- 99.99% availability for the data plane.
- horizontal scale without single-node hot spots.
- bounded blast radius per tenant, region, and shard.

### Non-Goals

- Do not design every client UI screen; focus on backend, data, and platform contracts.
- Do not optimize rare administrative workflows ahead of the user-visible hot path.
- Do not couple offline analytics correctness to online request latency.
- Do not rely on one shared database node as the scalability plan.

## 2. Capacity, Traffic, And Size Estimation

Use these as interview-scale assumptions. State that numbers are adjustable and use formulas so the interviewer can change scale.

| Dimension | Baseline Assumption |
|---|---|
| Active users | 10M DAU, 80M MAU |
| Redirect path | 50K average QPS, 250K peak QPS |
| Create path | 2K average QPS, 15K peak QPS |
| Click events | one event per redirect, sampled only if cost requires it |
| Data growth | link metadata is small; click logs dominate at 1-5 TB/day |
| Latency target | p50 < 30 ms and p99 < 100-150 ms for redirects |

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

Use REST for public/admin APIs and gRPC for internal service-to-service calls. Every create/update mutation accepts an idempotency key. The public redirect endpoint is unauthenticated, but owner/admin metadata APIs require authentication.

### Public APIs

```http
POST /v1/short-links
Idempotency-Key: <uuid>
Authorization: Bearer <token>
Content-Type: application/json

{
  "long_url": "https://example.com/products/123?ref=summer",
  "custom_alias": "summer-sale",
  "domain": "sho.rt",
  "expires_at": "2026-06-25T00:00:00Z",
  "redirect_type": 302,
  "tags": ["campaign", "summer"]
}
```

Successful create response:

```http
201 Created
Content-Type: application/json

{
  "id": "lnk_01J...",
  "code": "aZ81kLm",
  "short_url": "https://sho.rt/aZ81kLm",
  "long_url": "https://example.com/products/123?ref=summer",
  "domain": "sho.rt",
  "status": "ACTIVE",
  "expires_at": "2026-06-25T00:00:00Z",
  "version": 1
}
```

```http
POST /v1/short-links:batch
Idempotency-Key: <uuid>
Authorization: Bearer <token>
Content-Type: application/json

{
  "links": [
    {"long_url": "https://example.com/a", "expires_at": "2026-06-25T00:00:00Z"},
    {"long_url": "https://example.com/b", "custom_alias": "promo-b"}
  ]
}
```

```http
GET /{code}
Host: sho.rt

302 Found
Location: https://example.com/products/123?ref=summer
Cache-Control: public, max-age=300
```

```http
GET /v1/short-links/{code}
Authorization: Bearer <token>
```

```http
GET /v1/short-links?cursor=<cursor>&limit=50&owner_id=<owner>&tag=<tag>
Authorization: Bearer <token>
```

```http
PATCH /v1/short-links/{code}
Idempotency-Key: <uuid>
Authorization: Bearer <token>
Content-Type: application/json

{
  "expected_version": 4,
  "long_url": "https://example.com/new-destination",
  "expires_at": "2026-07-01T00:00:00Z",
  "status": "ACTIVE"
}
```

```http
DELETE /v1/short-links/{code}
Idempotency-Key: <uuid>
Authorization: Bearer <token>
```

```http
GET /v1/short-links/{code}/analytics?from=2026-05-25T00:00:00Z&to=2026-05-26T00:00:00Z&group_by=country,device
Authorization: Bearer <token>
```

```http
GET /v1/resolve/{code}?preview=true
```

```http
POST /v1/short-links/{code}/admin/quarantine
Idempotency-Key: <uuid>
Authorization: Bearer <admin-token>

{
  "reason": "malware_report",
  "evidence_ref": "case_123"
}
```

### Internal APIs

```protobuf
service ShortLinkService {
  rpc CreateShortLink(CreateShortLinkRequest) returns (ShortLink);
  rpc CreateShortLinksBatch(CreateShortLinksBatchRequest) returns (CreateShortLinksBatchResponse);
  rpc GetShortLink(GetShortLinkRequest) returns (ShortLink);
  rpc ResolveShortCode(ResolveShortCodeRequest) returns (ResolveShortCodeResponse);
  rpc UpdateShortLink(UpdateShortLinkRequest) returns (ShortLink);
  rpc QuarantineShortLink(QuarantineShortLinkRequest) returns (ShortLink);
  rpc ListShortLinkEvents(ListShortLinkEventsRequest) returns (stream ShortLinkEvent);
}

service CodeAllocator {
  rpc AllocateCodeRange(AllocateCodeRangeRequest) returns (AllocateCodeRangeResponse);
  rpc AllocateCodes(AllocateCodesRequest) returns (AllocateCodesResponse);
}

service ClickIngestionService {
  rpc RecordClick(RecordClickRequest) returns (RecordClickResponse);
}
```

### Error Model

- `400`: invalid request or unsupported transition.
- `401/403`: missing identity or policy denial.
- `404`: code not found or intentionally hidden by authorization.
- `409`: custom alias already exists, version conflict, duplicate idempotency key with different payload, or state transition race.
- `410`: link exists but is expired, deleted, or unavailable.
- `422`: URL failed validation or synchronous safety policy.
- `429`: tenant/user/key quota exceeded with `Retry-After`.
- `301/302/307`: redirect response from `GET /{code}` when the link is active.
- `5xx`: dependency or internal failure. Return a request ID for support and tracing.

## 4. Async Event Contracts

Use an outbox table or transactional event publisher so metadata changes and emitted events cannot diverge. Redirect click events are written asynchronously and must not block the redirect response.

```json
{
  "event_id": "evt_01H...",
  "event_type": "short_links.created.v1",
  "occurred_at": "2026-05-25T10:15:30Z",
  "producer": "link-management-service",
  "tenant_id": "tenant_123",
  "aggregate_id": "lnk_01J...",
  "aggregate_version": 1,
  "idempotency_key": "idem_123",
  "actor": {
    "type": "user",
    "id": "user_123"
  },
  "payload": {
    "domain": "sho.rt",
    "code": "aZ81kLm",
    "long_url_hash": "sha256:...",
    "expires_at": "2026-06-25T00:00:00Z",
    "status": "ACTIVE"
  }
}
```

Redirect click event:

```json
{
  "event_id": "clk_01J...",
  "event_type": "redirects.clicked.v1",
  "occurred_at": "2026-05-25T10:15:31Z",
  "producer": "redirect-service",
  "domain": "sho.rt",
  "code": "aZ81kLm",
  "request_id": "req_123",
  "payload": {
    "ip_prefix_hash": "hash(/24-or-/48)",
    "user_agent_hash": "hash(user-agent)",
    "referrer_hash": "hash(referrer)",
    "country": "IN",
    "device": "mobile",
    "cache_status": "edge_hit"
  }
}
```

### Core Events

- `short_links.created.v1`
- `short_links.batch_created.v1`
- `short_links.updated.v1`
- `short_links.expired.v1`
- `short_links.quarantined.v1`
- `short_links.deleted.v1`
- `short_links.creation_failed.v1`
- `redirects.clicked.v1`
- `redirects.resolve_failed.v1`
- `abuse.scan_requested.v1`
- `abuse.scan_completed.v1`

## 5. High-Level Architecture

### Architecture Design

```text
TinyURL / Bitly URL shortener Architecture

Browser / Mobile App / API Client
        |
        v
DNS / Global Traffic Manager
        |
        v
CDN / Edge Worker / WAF
        |
        +--> Create / Management Path
        |       POST /v1/short-links
        |       -> API Gateway
        |       -> Link Management Service
        |       -> URL Normalizer + Safety Precheck
        |       -> Code Allocator
        |       -> Link Metadata Store + Idempotency Store + Outbox
        |
        +--> Redirect Data Path
        |       GET /{code}
        |       -> Redirect Service
        |       -> Local Hot Cache
        |       -> Redis Cluster / Edge KV
        |       -> Link Metadata Store fallback
        |       -> 301/302/307 response
        |
        +--> Async Path
        |       -> Kafka/Pulsar/Kinesis
        |       -> Click Analytics Pipeline
        |       -> Abuse Scanner
        |       -> Cache Warmer / Expiry Worker / Reconciliation
        |
        +--> Operations Path
                -> Admin Console / Audit / Reconciliation / Backfill / Disaster Recovery

Data Stores:
- Link metadata KV store keyed by (domain_id, code)
- Relational account/domain/admin metadata store
- Redis/Edge KV/CDN caches for hot redirects
- Event log for clicks and metadata changes
- OLAP store for dashboards and reports
- Abuse/quarantine store for safety decisions
```

### Request And Data Flow

1. **Create path:** authenticated clients call `POST /v1/short-links`; the gateway validates identity and quota, then the Link Management Service normalizes the URL, performs fast safety checks, allocates a code, conditionally writes `(domain_id, code)` to the metadata store, records idempotency, and writes an outbox event.
2. **Redirect path:** public clients call `GET /{code}`; the CDN/edge worker checks cache first, then the Redirect Service checks local cache, Redis/Edge KV, and finally the metadata store. It validates status, TTL, and quarantine state before returning a redirect.
3. **Frequent URL path:** hot links are served from CDN or Redis with short TTL and stale-while-revalidate. Click events and hot-key counters identify frequently accessed codes and warm them asynchronously.
4. **Analytics path:** redirects enqueue click events after the response decision. Stream processors aggregate clicks by time bucket, country, device, referrer, and owner into OLAP tables.
5. **Safety path:** URL scanning, user reports, reputation updates, and admin quarantine run asynchronously, but their final decision updates the metadata store and invalidates redirect caches.
6. **Operations path:** admin, audit, replay, reconciliation, backfill, and disaster-recovery workflows are isolated from user-facing redirect latency but use the same immutable event/audit history.

### Component Responsibilities

- **CDN / Edge Worker**: Terminates public redirect traffic close to users, applies WAF/bot controls, caches safe redirect metadata, and forwards misses to the Redirect Service.
- **API Gateway**: Authenticates management APIs, enforces quotas, validates request shape, routes by tenant/domain/cell, and attaches trace context.
- **Link Management Service**: Owns create/update/delete APIs, idempotency, ownership checks, custom alias validation, TTL changes, and metadata writes.
- **Code Allocator**: Generates unique codes using Snowflake-style IDs, preallocated numeric ranges, or a random generator plus collision checks. It never decides ownership or URL policy.
- **Redirect Service**: Owns the hot read path for `(domain_id, code) -> destination`; keeps dependencies minimal and emits click events asynchronously.
- **URL Normalizer / Safety Precheck**: Canonicalizes URLs, blocks invalid schemes, rejects obvious malware/phishing, and requests deeper async scanning.
- **Abuse Scanner / Quarantine Service**: Consumes scan requests and reports, updates link status, and invalidates caches when a link becomes unsafe.
- **Analytics Pipeline**: Consumes click events, deduplicates when needed, computes rollups, and writes OLAP dashboards without touching the redirect latency budget.
- **Cache Warmer / Hot-Key Detector**: Tracks top codes from click streams and proactively warms CDN/Redis/local caches for frequently accessed links.
- **Admin and Audit Service**: Provides investigation, replay, correction, quarantine approval, and immutable audit trails.

### Service Responsibility Matrix

| Layer | Services | Responsibility |
| --- | --- | --- |
| Edge/API boundary | CDN/Edge Worker, API Gateway | Redirect caching, TLS, WAF, bot controls, auth for management APIs, quota, routing, and trace context propagation. |
| Create/control services | Link Management Service, Code Allocator, URL Normalizer | Create/update/delete short links, allocate codes, enforce idempotency, validate custom aliases, write canonical metadata, and publish outbox events. |
| Redirect serving services | Redirect Service, local cache, Redis/Edge KV | Resolve codes with low latency, enforce TTL/status/quarantine, and return redirects without waiting for analytics. |
| Async workers and integrations | Analytics Pipeline, Abuse Scanner, Cache Warmer, Expiry Worker | Consume committed events, update projections, scan URLs, roll up metrics, clean expired links, warm hot caches, and retry safely. |
| Data and governance | Link KV store, relational metadata DB, event log, cache, OLAP warehouse, audit log | Separate canonical link state from derived caches, click logs, search, analytics, and audit records. |
| Operations | Admin console / reconciliation / observability / runbooks | Provide support investigation, replay/backfill, manual correction, compliance evidence, SLO dashboards, and incident response. |

### Data Stores

- **Link metadata store:** key-value or wide-column store keyed by `(domain_id, code)`; stores destination URL, status, owner, TTL, redirect type, and version.
- **Account/domain metadata store:** relational store for users, tenants, custom domains, billing plan, domain verification, and admin cases.
- **Idempotency store:** scoped by `(tenant_id, idempotency_key)` so retries return the same create/update result.
- **Redirect cache:** CDN plus Redis/Edge KV plus small local LRU cache in the Redirect Service.
- **Event log:** append-only stream for link changes and click events.
- **Analytics warehouse:** ClickHouse/Pinot/Druid/BigQuery/Redshift for dashboard and ad hoc reporting.
- **Audit and abuse stores:** immutable admin actions, abuse reports, quarantine state, and evidence references.

## 6. Low-Level Design

### Core Modules

- `ShortLinkController`: handles create, batch create, metadata fetch, update, delete, analytics, and admin APIs.
- `RedirectController`: handles `GET /{code}` with a minimal dependency chain.
- `ShortLinkApplicationService`: orchestrates validation, idempotency, code allocation, conditional writes, and state transitions.
- `CodeAllocator`: allocates generated codes from Snowflake/range/random strategies and exposes batch allocation.
- `UrlNormalizer`: canonicalizes URL scheme, host, path, query, and strips unsafe fragments where policy requires.
- `SafetyPolicyEvaluator`: blocks invalid schemes and obvious abuse synchronously; schedules deeper async scans.
- `ShortLinkRepository`: hides conditional insert, optimistic locking, partitioning, and pagination details.
- `RedirectResolver`: resolves `(domain_id, code)` from local cache, Redis/Edge KV, then source of truth.
- `ClickEventPublisher`: writes click events to an async queue with best-effort buffering and backpressure.
- `ShortLinkEventPublisher`: writes outbox records and publishes metadata events to the broker.
- `HotLinkProjector`: builds hot-key counters and cache warming lists from redirect events.

### Interfaces

```java
interface ShortLinkRepository {
    Optional<ShortLink> findByDomainAndCode(DomainId domainId, ShortCode code, ReadConsistency consistency);
    Page<ShortLink> list(ShortLinkQuery query, Cursor cursor, int limit);
    ShortLink conditionalCreate(ShortLink aggregate); // fails if (domain_id, code) already exists
    ShortLink update(ShortLink aggregate, ExpectedVersion expectedVersion);
}

interface CodeAllocator {
    ShortCode allocate(DomainId domainId);
    List<ShortCode> allocateBatch(DomainId domainId, int count);
}

interface RedirectResolver {
    ResolveResult resolve(DomainId domainId, ShortCode code);
    void invalidate(DomainId domainId, ShortCode code, String reason);
}

interface SafetyPolicyEvaluator {
    SafetyDecision precheck(URL normalizedUrl, Principal principal);
    void requestAsyncScan(ShortLinkId linkId, URL normalizedUrl);
}

interface IdempotencyStore {
    Optional<StoredResponse> find(String scope, String key, String requestHash);
    void reserve(String scope, String key, String requestHash, Instant expiresAt);
    void complete(String scope, String key, StoredResponse response);
}

interface ClickEventPublisher {
    void publishAsync(ClickEvent event); // never blocks the redirect response beyond a tiny bounded timeout
}
```

### State Machine

```text
PENDING_SCAN -> ACTIVE -> PAUSED -> DELETED
      |          |          |
      |          |          -> RESTORE only by owner/admin policy
      |          -> EXPIRED when expires_at is reached
      |          -> QUARANTINED by abuse/security workflow
      -> REJECTED if synchronous or async safety policy fails
```

- `ACTIVE` links can redirect.
- `PENDING_SCAN` can either redirect with warning, redirect normally, or be blocked depending on product policy and risk score.
- `EXPIRED`, `DELETED`, `REJECTED`, and `QUARANTINED` links do not redirect to the destination.
- Every transition is versioned, idempotent, and auditable.

## 7. Database Modeling And DB Design

### Logical Model

```text
Tenant/User
  -> owns -> CustomDomain
  -> creates -> ShortLink(domain_id, code)
ShortLink
  -> resolves to -> LongUrl
  -> emits -> MetadataEvent
  -> receives -> RedirectClickEvent
RedirectClickEvent
  -> produces -> HotLinkCounter / AnalyticsRollup
AbuseReport / Scanner
  -> updates -> ShortLink.status
AdminAction
  -> audited by -> AuditLog
```

### Core Tables

| Table | Important Columns |
|---|---|
| `link_mappings` | `domain_id, code, link_id, long_url_encrypted, long_url_hash, owner_id, redirect_type, status, expires_at, version, created_at, updated_at` |
| `link_owner_index` | `owner_id, created_at, link_id, domain_id, code, status, expires_at` |
| `idempotency_keys` | `scope, idempotency_key, request_hash, response_json, state, expires_at, created_at` |
| `code_allocations` | `allocator_id, domain_id, range_start, range_end, next_value, state, leased_until` |
| `custom_domains` | `id, owner_id, hostname, tls_status, verification_token, home_region, created_at` |
| `redirect_events` | `event_id, domain_id, code, ts_bucket, country, device, referrer_hash, ip_prefix_hash, cache_status` |
| `hot_link_counters` | `time_bucket, domain_id, code, click_count, cache_hit_count, last_seen_at` |
| `abuse_reports` | `id, link_id, reporter_id, reason, evidence_ref, state, decided_by, created_at` |
| `scan_results` | `link_id, scanner, verdict, risk_score, evidence_ref, created_at` |
| `audit_log` | `event_id, actor_id, action, resource_id, reason, before_json, after_json, created_at` |

### Database Technology Choice

| Workload / Data | Recommended Database / Store | Why This Choice Fits |
| --- | --- | --- |
| Source of truth / primary store | DynamoDB/Cassandra/Bigtable/ScyllaDB for `(domain_id, code) -> URL` redirect lookup; PostgreSQL for accounts, custom domains, abuse cases, and admin metadata | redirects are key-value reads at huge scale, while account/domain/admin data needs relational constraints |
| Hot serving / cache | CDN edge cache plus Redis Cluster for hottest codes and abuse/rate-limit state | keeps hot redirect reads, abuse decisions, counters, and derived views away from the source-of-truth store |
| Event stream / outbox | Kafka/Pulsar/Kinesis with compacted topics for keys and retained topics for replay | decouples projections, notifications, analytics, search indexing, and recovery from the write path |
| Search / analytics | OpenSearch/Elasticsearch for search and ClickHouse/Druid/Pinot for analytics | serves text/filter/OLAP queries without overloading transactional tables |
| Large immutable payloads | S3/GCS/Azure Blob/object storage for payloads, exports, evidence, backups, and immutable artifacts | large or immutable data is cheaper, durable, and easier to lifecycle outside OLTP rows |

Interview stance: name the source-of-truth database first, then explicitly separate caches, indexes, event logs, and analytics stores. The cache, search index, and warehouse are derived systems; they must be rebuildable from canonical state and immutable events.

### Replication Strategy

- Primary store: multi-AZ synchronous or quorum replication for the primary store; asynchronous cross-region replicas for DR and read locality.
- Event log: replicate each partition across at least 3 brokers/nodes, require quorum acknowledgements for critical events, and monitor under-replicated partitions.
- Cache/read models: replicate for availability, but treat them as disposable; rebuild from source-of-truth rows plus events after corruption or cache loss.
- Object storage: use multi-AZ durability by default; enable cross-region replication only for disaster recovery, compliance, or locality requirements.
- Analytics/search stores: replicate shards for query availability, but recover by replaying events or rebuilding from snapshots when correctness is in doubt.

### Sharding And Partitioning Strategy

- Primary partition key: `hash(domain_id, code)` with virtual shards for link mappings; `tenant_id` or `owner_id` for admin/account tables.
- Primary lookup path: `(domain_id, code)` must be single-partition whenever possible.
- Time-partition append-heavy data such as events, audit logs, metrics, and delivery attempts so retention, archival, replay, and backfills do not scan the full corpus.
- Hot partition mitigation: cache viral links at edge, split analytics writes by code hash + time bucket, and rate-limit abusive codes or tenants.
- Keep tenant/cell/region boundaries explicit so one large customer, city, celebrity, event, or provider cannot overload the whole system.
- Multi-region write ownership: assign each custom domain or generated-code namespace to a home region/cell. Active-active writes need region bits in generated IDs or a globally consistent conditional write path.

### Indexing Strategy

- Required secondary indexes: `owner_id + created_at, domain_id + code, expires_at, status + updated_at, long_url_hash`.
- Keep OLTP indexes minimal on high-write tables; move broad filtering, text search, ranking, and analytics to dedicated search/OLAP stores.
- Use composite indexes that match real query order: equality columns first, then range/sort columns such as `created_at`, `updated_at`, or `score`.
- For mutable state machines, index `(state, updated_at)` or `(state, next_attempt_at)` for workers and repair jobs.
- For audit and event tables, prefer append-only writes with time-bucketed partitions and compact indexes over many mutable secondary indexes.

### CAP Theorem And Consistency Choices

| Data / Operation | CAP Bias During Partition | Consistency Model | Interview Notes |
| --- | --- | --- | --- |
| Canonical command path | CP for core state transitions that must not diverge during a partition | strong consistency for source-of-truth writes and policy gates | Prefer rejecting or queuing unsafe writes over accepting divergent state. |
| Derived read models | AP/eventual for derived or disposable views where stale data is acceptable | Eventual consistency for click analytics, abuse scoring, search/admin dashboards, and redirect metrics | Expose `pending`, `processing`, `stale_at`, or version metadata when users may observe lag. |
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
| Hot-path caching | CDN, Redis Cluster, Memcached, local in-process cache, request coalescing, stale-while-revalidate | Cache `(domain_id, code) -> redirect metadata` for hot links. Invalidate on update, expiry, delete, or quarantine. | Cache can accelerate redirects, but the metadata store remains the source of truth for status, TTL, and destination. |
| Async processing | Kafka, Pulsar, Kinesis, RabbitMQ/SQS, transactional outbox/inbox, DLQ, retry with jitter | Move click analytics, safety scanning, cache warming, search indexing, and cleanup off the redirect path. | Redirects must continue when analytics consumers lag. Consumers must be idempotent. |
| Stream processing | Apache Flink, Kafka Streams, Spark Structured Streaming, Beam | Build click rollups, hot-link top-K lists, abuse signals, and near-real-time dashboards. | Use event time, watermarks, replay, and exactly-once/effectively-once sinks only where the business needs it. |
| Batch jobs and workflows | Airflow, Dagster, Argo Workflows, Temporal, Cadence, Step Functions, Spark | Run expiry cleanup, range-pool refill, safety backfills, analytics repair, reconciliation, and lifecycle management. | Keep batch workers isolated from online redirect capacity and make every job restartable and idempotent. |
| CDC and projections | Debezium, database CDC, Kafka Connect, outbox table relay | Feed search indexes, CQRS read models, lakehouse tables, caches, and audit pipelines from committed changes. | CDC is for propagation; business commands still go through domain services. |
| Event contracts | Schema Registry, Avro, Protobuf, JSON Schema, AsyncAPI, compatibility checks | Version domain events, enforce backward/forward compatibility, and document owners and consumers. | Breaking schema changes require new event versions and migration windows. |
| CQRS and read models | Command store, query projections, materialized views, search indexes | Keep canonical writes small and strongly owned; serve read-heavy views from projections optimized for query shape. | Expose freshness/version metadata and rebuild projections from events. |
| Microservice consistency patterns | Saga/process manager, transactional outbox, inbox dedupe, idempotency keys, compensating actions | Coordinate multi-service workflows without distributed transactions. | Make every state transition explicit and auditable; avoid hidden side effects. |
| Event storming and domain modeling | Commands, aggregates, events, policies, read models, bounded contexts | Identify aggregate owners, event names, invariants, side effects, and read projections before drawing service boxes. | Services should map to ownership boundaries, not arbitrary technical layers. |
| Object storage and lakehouse | S3/GCS/Azure Blob, Iceberg, Hudi, Delta Lake, Glue/Hive catalog | Store raw events, media, attachments, audit exports, feature data, and replayable history in immutable partitions. | Keep object/lake data partitioned by date/tenant/domain key and govern retention/privacy. |
| Analytics serving | Pinot, ClickHouse, Druid, Redshift, BigQuery, Snowflake, Athena/Trino/Presto | Serve dashboards, funnels, investigations, operational analytics, ad hoc SQL, and historical reports outside OLTP. | Do not run exploratory analytics against the primary transactional database. |
| Service runtime and governance | Spring Boot, Quarkus, Micronaut, Go/gRPC, Node.js, Kubernetes, service mesh, mTLS, API gateway, OpenTelemetry, config service, feature flags | Deploy independently, enforce auth, collect traces/metrics/logs, and roll out safely with canaries and kill switches. | More services increase operational load; split only when ownership, scale, or reliability justifies it. |

For this design, use Redis/CDN/local caches for the hot read path, Kafka or Pulsar for async domain events, Flink/Spark for stream enrichment when needed, S3 + Iceberg for long-retention history, and ClickHouse/Pinot/Druid/Redshift/Athena for analytical access.

Implementation rule: start with the simplest reliable building block, then introduce Kafka/Flink/lakehouse/OLAP/microservice patterns when scale, replay, ownership, or query shape demands them. Every added component must have a clear owner, SLO, retention policy, replay story, and failure mode.

## 8. Critical Flows

### Create Short URL Flow

1. Client calls `POST /v1/short-links` with an idempotency key.
2. API Gateway authenticates the caller, checks tenant/user quotas, and routes to the link's home cell.
3. Link Management Service normalizes the long URL and runs synchronous safety prechecks.
4. If the user provided `custom_alias`, the service validates allowed characters, length, reserved words, and domain ownership.
5. If no custom alias was provided, Code Allocator returns a generated short code.
6. Repository performs a conditional insert into `link_mappings` using unique key `(domain_id, code)`.
7. If the conditional insert fails for a generated code, retry with another code a small bounded number of times. If it fails for a custom alias, return `409`.
8. In the same transaction or atomic write unit, store the idempotency result and write an outbox event.
9. Response returns `201` with `short_url`, `code`, `status`, `expires_at`, and `version`.
10. Async workers publish events, run deep safety scans, update search/read models, and warm caches if needed.

### Batch Create Flow

1. Client calls `POST /v1/short-links:batch` with one idempotency key for the whole batch and stable client item IDs for each row.
2. Service validates every URL first and separates custom aliases from generated links.
3. Code Allocator reserves `N` generated codes in one call. With Snowflake/range allocation, each service instance owns a non-overlapping numeric range and Base62-encodes values.
4. Service writes each link with conditional `(domain_id, code)` uniqueness.
5. Custom alias conflicts return item-level `409` results. Generated-code collisions are retried internally and should be extremely rare.
6. Response can be all-or-nothing for strict APIs or partial-success for large imports. In both cases, retrying the same idempotency key returns the same item results.

### Redirect / Serving Flow

1. Client requests `https://sho.rt/aZ81kLm`.
2. DNS/GTM routes to the nearest healthy edge.
3. CDN/Edge Worker checks whether redirect metadata is cached and still valid.
4. On cache miss, Redirect Service checks local LRU cache, then Redis/Edge KV, then the link metadata store by `(domain_id, code)`.
5. Service verifies `status == ACTIVE`, `expires_at > now`, domain state, and quarantine decision.
6. Service returns `301`, `302`, or `307` with `Location`. Most shorteners use `302` by default because destinations may change and analytics need fresh checks.
7. Service emits `redirects.clicked.v1` asynchronously. If the event broker is slow, redirects continue with local buffering, sampling, or controlled dropping based on policy.

### Frequently Accessed URL Flow

1. Every redirect emits a click event with `domain_id`, `code`, timestamp bucket, and cache status.
2. Stream processor maintains top-K hot links per region and time window.
3. Cache Warmer writes hot mappings into Redis/Edge KV and optionally preloads CDN edge cache.
4. Redirect Service uses local LRU cache for ultra-hot links and Redis/Edge KV for shared hot links.
5. Cache entries use short TTL, soft TTL, and stale-while-revalidate. A cached link must still include status, expiration, and policy version so unsafe or expired links can be invalidated quickly.
6. When a link is updated, expired, deleted, or quarantined, the outbox event invalidates CDN, Redis, and local caches.

### Conflict-Free Code Creation

1. The final uniqueness guard is always the metadata store key `(domain_id, code)`.
2. Generated codes should come from a large enough namespace, usually 7-10 Base62 characters. Seven Base62 characters give about `62^7`, roughly 3.5 trillion combinations.
3. Recommended default: use Snowflake-style or range-allocated numeric IDs and Base62-encode them. This avoids random collisions and supports high write throughput.
4. Alternative: use secure random Base62 codes and conditional insert. If a collision occurs, generate another code and retry.
5. Custom aliases do not retry with a different value. If `(domain_id, custom_alias)` exists, return `409 alias already exists`.
6. Multi-region writes either route each domain/code namespace to one home region or include region/worker bits in generated IDs. Do not allow two regions to allocate from the same range.

### Background Jobs And Workers

Not every short-code creation needs a background job. With Snowflake/range allocation or random-plus-conditional-insert, a single short URL can be created synchronously. Background jobs are still useful for the surrounding system:

| Job | Required? | Purpose |
|---|---:|---|
| Code range allocator / pool refill | Optional but useful | Keeps create latency low by leasing non-overlapping ID ranges to app instances. Required only if using a pre-generated code pool strategy. |
| Deep URL safety scanner | Usually yes | Runs malware/phishing/reputation checks that are too slow for the create request. |
| Click analytics consumer | Yes for analytics | Aggregates click events without blocking redirects. |
| Hot-link detector and cache warmer | Recommended at scale | Finds frequently accessed codes and preloads Redis/CDN/local caches. |
| Expiry worker | Yes for cleanup | Marks/deletes expired links and removes stale cache entries. Redirect correctness still checks `expires_at`, so cleanup lag is safe. |
| Reconciliation/backfill worker | Recommended | Compares metadata, events, caches, and analytics rollups after failures or deploys. |
| Abuse report processor | Yes if abuse reporting is in scope | Handles user reports, takedown decisions, and audit records. |

### Replay / Recovery Flow

1. Identify the affected tenant, shard, time window, or aggregate IDs.
2. Pause dangerous side effects such as external takedown calls if replay can duplicate them.
3. Rebuild redirect caches from the metadata store and rebuild analytics/search/read models from events.
4. Compare counts/checksums between `link_mappings`, outbox events, click events, and analytics rollups.
5. Resume normal processing and keep an audit note with operator, reason, and evidence.

## 9. Deep-Dive Focus Areas

- **Key generation:** The create path asks Code Allocator for a code, then the metadata store enforces uniqueness with `(domain_id, code)`. Generated codes can use Snowflake/range allocation for no collisions, or random Base62 with conditional-insert retries.
- **Custom aliases:** Custom aliases are user-selected and must be unique within a domain. They use a conditional insert and return `409` on conflict.
- **Frequently accessed URLs:** Serve from CDN/edge cache first, then local cache, Redis/Edge KV, and finally metadata DB. Hot-link detection and cache warming are async.
- **Redirects:** Make the redirect path read-only, cache-heavy, and independent from analytics ingestion so spikes do not slow user-visible redirects.
- **TTL:** Represent expiration as indexed metadata plus async cleanup; do not rely only on physical deletion for correctness.
- **Abuse prevention:** Combine rate limits, reputation, content scanning, user reports, and fast takedown workflows. Cache invalidation must happen when a link is quarantined.
- **Analytics:** Write analytics asynchronously through an event log and aggregate into OLAP tables for dashboards.

## 10. Scaling Bottlenecks And Mitigations

| Bottleneck | Why It Happens | Mitigation |
|---|---|---|
| Viral short link | A small number of codes receives a disproportionate share of redirects. | CDN/edge cache, local LRU cache, Redis hot-key replication, request coalescing, and async click aggregation. |
| Code allocation bottleneck | One central counter or allocator becomes a write hot spot. | Lease ID ranges per app instance, use Snowflake-style IDs, or use random Base62 with conditional insert retries. |
| Custom alias conflicts | Many users request the same human-readable alias. | Conditional insert on `(domain_id, code)`, return `409`, and suggest alternatives asynchronously. |
| Synchronous dependency chain | User-visible request waits on too many downstream systems. | Move non-critical work to events, use timeouts, fallbacks, and circuit breakers. |
| Cache stampede | Popular key expires or is invalidated under high concurrency. | Soft TTL, request coalescing, jittered expiration, stale-while-revalidate. |
| Stale unsafe redirect | A quarantined or expired link remains cached. | Short TTLs, policy version in cache entries, event-driven invalidation, and edge purge APIs. |
| Large tenant noisy neighbor | One tenant consumes shared pool capacity. | Per-tenant quotas, partitioning, fairness queues, and dedicated capacity for top tenants. |
| Reindex/rebuild pressure | Backfills or rebuilds compete with online serving. | Separate backfill pools, rate limits, shadow indexes, and atomic cutover. |
| Operational blind spots | Failures occur without enough context to debug. | Correlate logs, metrics, traces, audit events, and deployment versions. |

## 11. Security, Privacy, Abuse Prevention, And Compliance

- Authenticate every request with user, service, or device identity; use mTLS for internal service calls.
- Authorize by tenant, ownership, role, resource state, and contextual policy. Do not rely on front-end checks.
- Encrypt data in transit and at rest. Use tenant-scoped or domain-scoped keys for sensitive data.
- Store secrets in a managed vault and rotate credentials. Never log tokens, passwords, private keys, or raw sensitive payloads.
- Apply input validation, WAF rules, bot detection, rate limits, and abuse reputation checks.
- Validate URL schemes and block `javascript:`, `data:`, private-network targets, obvious open-redirect abuse, and known malicious domains.
- Store raw destination URLs encrypted and avoid logging full URLs when they may contain tokens or personal data.
- Keep immutable audit logs for administrative actions, policy decisions, state transitions, and data exports.
- Implement data retention, deletion, legal hold, and privacy export workflows if the domain stores personal data.
- Use least privilege for operators and services; require break-glass approvals for emergency access.

## 12. Reliability, Failure Modes, And Recovery

| Failure Mode | Impact | Recovery Strategy |
|---|---|---|
| Primary DB shard unavailable | Mutations for affected shard fail or degrade. | Multi-AZ failover, circuit breaker, queued writes only if semantics allow, clear user messaging. |
| Cache cluster loss | Higher latency and DB load. | Request coalescing, local cache, rate limiting, and progressive cache warmup. |
| Code allocator unavailable | New generated links fail or slow down. | Use locally leased ranges, fallback to random code plus conditional insert, or degrade only create APIs while redirects continue. |
| Event broker lag | Search, analytics, notifications, or projections become stale. | Lag alerts, autoscale consumers, replay from offsets, and expose freshness to users/internal teams. |
| Abuse scanner outage | New risky links may stay pending longer. | Apply stricter synchronous precheck, cap creation rate for risky tenants, and process scan backlog after recovery. |
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
| Redirect availability | successful active redirects / valid redirect requests | 99.99% for public redirect path |
| Create availability | successful creates / valid create requests | 99.9% to 99.99% depending on product tier |
| Redirect latency | p50/p95/p99 by domain, region, cache status | p99 under 100-150 ms for redirects |
| Correctness | duplicate codes, wrong destinations, invalid state transitions | zero known duplicate `(domain_id, code)` or wrong-destination redirects |
| Freshness | event lag, projection lag, index lag | 95% of projections within agreed freshness window |
| Durability | acknowledged writes later readable/replayable | no acknowledged write loss |
| Saturation | CPU, memory, queue depth, broker lag, DB connections | alert before user-visible impact |

### Dashboards

- API RED metrics: request rate, error rate, duration by endpoint, tenant, domain, region, and deployment version.
- Dependency metrics: metadata DB latency, cache hit ratio by tier, broker lag, scanner latency, search latency, provider errors.
- Domain metrics: create count, redirect count, generated-code retry count, alias conflict count, expired/quarantined count, policy denials, DLQ depth.
- Capacity metrics: shard size, hot keys, queue depth, worker utilization, storage growth, egress.
- Security metrics: auth failures, suspicious IPs/devices, abuse reports, admin actions, data export/delete requests.

### Alerts

- Page on sustained SLO burn, correctness violations, write unavailability, severe broker lag, or security incidents.
- Ticket on slow capacity trends, moderate projection lag, rising retries, or low-priority DLQ growth.
- Suppress duplicate alerts through incident correlation and route to service owners with runbook links.

## 15. Cost Model And Trade-Offs

### Cost Drivers

- data-plane compute at peak QPS.
- cache memory and replication factor.
- analytics/event retention volume.
- cross-region replication and egress.

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
| Code generation | Snowflake/range + Base62 | Random Base62 + conditional retry | Snowflake/range avoids collisions and is easier to reason about at high write QPS. Random is simple but needs collision retries. |
| Custom alias handling | Strict unique alias | Auto-suggest alternate alias | Always enforce uniqueness with conditional insert; suggestions are a product feature, not the correctness boundary. |
| Redirect cache | Cache full redirect metadata | Cache only code existence | Cache metadata for speed, but include status/TTL/policy version and invalidate aggressively. |
| Redirect type | 302 default | 301 permanent | Use 302 unless destinations are immutable. 301 can be cached too aggressively by browsers and CDNs. |
| Analytics | Async click event | Synchronous analytics write | Keep analytics async; redirects should not wait for counters or warehouse writes. |
| Storage | Single general-purpose DB | Polyglot stores | Start simple, then split when redirect lookups, admin metadata, click logs, and analytics have different access patterns. |
| Multi-region | Home region per domain/code namespace | Active-active writes | Home-region routing is simpler. Active-active needs conflict-free ID generation and careful cache invalidation. |
| Build vs buy | Managed service | Custom platform | Buy undifferentiated primitives unless scale, cost, compliance, or product semantics require ownership. |

## 17. Common Interview Follow-Ups

- How does the design change at 10x traffic or with one extremely large tenant?
- Which data must be strongly consistent and which can lag?
- What is the exact partition key and how do you migrate when it becomes hot?
- What happens when 1M people click the same short URL in one minute?
- How do you create 10K short URLs in a batch without duplicate codes?
- Is a background job required for code generation, or only for optimization?
- How do you invalidate caches when a URL is edited, expired, or quarantined?
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
- **Hot path clarity:** separate `POST /v1/short-links` creation from `GET /{code}` redirects and walk both paths explicitly.
- **Service ownership:** assign responsibilities to CDN/Edge Worker, API Gateway, Link Management Service, Code Allocator, Redirect Service, Abuse Scanner, Cache Warmer, and Analytics Pipeline.
- **Data ownership:** ground the design in `link_mappings`, `idempotency_keys`, `code_allocations`, `redirect_events`, analytics rollups, and audit tables.
- **Event model:** use `short_links.created.v1`, `short_links.updated.v1`, `short_links.expired.v1`, `short_links.quarantined.v1`, and `redirects.clicked.v1` to decouple slow work while preserving idempotency and ordering per link.
- **Operational maturity:** include backpressure, DLQs, reconciliation, runbooks, audit trails, and safe manual correction.

### Bar-Raiser Drill-Down Prompts

- Which service allocates a code, and what exact conditional write proves it is unique?
- What is the idempotency key scope, and what happens if the same key is retried with a different payload?
- Which cache layers can be stale, and how are edited, expired, or quarantined links invalidated?
- How does the design behave when the same short URL becomes viral?
- Is code pre-generation required, optional, or harmful for this scale?
- What breaks during a dependency outage, and how does the system converge after callbacks or reports arrive late?
- Which metric would page the on-call engineer before duplicate codes, wrong redirects, or unsafe cached redirects impact users?

### Common Weak Answers To Avoid

- Drawing only a generic API -> service -> database diagram without ownership boundaries.
- Skipping idempotency, alias conflicts, generated-code collision handling, and reconciliation.
- Putting all features on the synchronous path and ignoring backpressure or degradation.
- Treating cache/search/analytics as source of truth for critical decisions.
- Listing databases without explaining partition key, consistency model, retention, and recovery.

### Domain-Specific Bar Raiser Notes
- Separate create/control-plane writes from redirect data-plane reads.
- Prove key uniqueness, cache behavior, abuse quarantine, and analytics async path.
- Do not block redirects on analytics writes.
- Explain that background jobs are not mandatory for one generated short URL, but are important for pool refill, abuse scanning, analytics, cache warming, expiry, and repair.

### 5-Minute Whiteboard Structure

- First minute: scope actors, constraints, and `key generation`.
- Minutes 2-3: draw CDN/edge, create path, redirect path, async path, and data stores; name API Gateway, Link Management Service, Code Allocator, Redirect Service, Abuse Scanner, Cache Warmer, and Analytics Pipeline.
- Minute 4: walk one critical flow and call out idempotency, consistency, and failure recovery.
- Minute 5: close with scale bottlenecks, security/privacy, observability, cost, and trade-offs.
