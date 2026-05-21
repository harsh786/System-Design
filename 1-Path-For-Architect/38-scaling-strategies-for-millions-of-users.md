# Scaling Strategies for Millions of Users

This file is a dedicated scaling strategy roadmap for systems that must support millions of users. It focuses on architecture evolution, bottleneck removal, operational readiness, and cost-aware growth.

## Architect-Level Outcome

You should be able to explain how a system evolves from first production release to millions of users without premature complexity or dangerous rewrites.

## Scaling Answer Formula

```text
Clarify workload -> Estimate traffic -> Identify hot path -> Remove single bottleneck -> Add caching -> Partition data -> Async non-critical work -> Add observability -> Add resilience -> Add regional strategy -> Control cost
```

## Scaling Stages

| Stage | Users | Architecture Goal |
| --- | --- | --- |
| Stage 0 | prototype | prove product behavior |
| Stage 1 | thousands | simple reliable monolith or few services |
| Stage 2 | tens of thousands | cache, async jobs, read replicas, basic observability |
| Stage 3 | hundreds of thousands | service boundaries, queues, CDN, database tuning |
| Stage 4 | millions | sharding, multi-region reads, event-driven workflows, SLOs |
| Stage 5 | tens/hundreds of millions | cell architecture, active-active, platform automation, strict cost controls |

## Million-User Baseline Architecture

```text
Users -> CDN/WAF -> Global LB -> API Gateway -> Services
                                      |       -> Cache
                                      |       -> Primary DB / Shards
                                      |       -> Queue/Event Bus
                                      |       -> Search Index
                                      |       -> Object Storage
                                      |       -> Analytics Pipeline
                                      -> Observability/Security/Rate Limits
```

## Step 1: Know the Workload

Scaling depends on access pattern:

- Read-heavy feed.
- Write-heavy chat.
- Transactional payment.
- Search-heavy catalog.
- Media-heavy streaming.
- Low-latency bidding.
- Batch/analytics pipeline.
- Real-time dashboard.

For each workload, identify:

- Read/write ratio.
- Peak factor.
- Payload size.
- Consistency requirement.
- Fanout pattern.
- Hot keys.
- Data growth.
- Retention.
- Geography.
- Cost per unit.

## Step 2: Scale Reads

Strategies:

- CDN for static and cacheable content.
- Edge caching.
- Application cache.
- Database read replicas.
- Materialized views.
- Search indexes.
- Precomputed feeds.
- CQRS read models.
- Client caching.

Trade-offs:

- Staleness.
- Invalidation complexity.
- Cache stampede.
- Read-your-writes expectations.
- Extra storage and pipeline cost.

## Step 3: Scale Writes

Strategies:

- Keep write path short.
- Use idempotency keys.
- Move non-critical work async.
- Batch writes where acceptable.
- Partition by natural key.
- Use append-only logs for high-throughput events.
- Use optimistic concurrency when conflicts are rare.
- Use queues to absorb bursts.

Trade-offs:

- Eventual consistency.
- Reconciliation.
- Duplicate processing.
- Hot partitions.
- Back-pressure behavior.

## Step 4: Cache Correctly

Cache layers:

- Browser/mobile cache.
- CDN cache.
- API gateway cache.
- Application local cache.
- Distributed cache.
- Database buffer cache.

Common patterns:

- Cache-aside.
- Read-through.
- Write-through.
- Write-behind.
- Refresh-ahead.
- Negative caching.
- Request coalescing.

Failure modes:

- Cache stampede.
- Hot key.
- Stale data.
- Thundering herd after expiry.
- Cache outage.
- Memory pressure and eviction.

Mitigations:

- TTL jitter.
- Single-flight/request coalescing.
- Soft TTL plus background refresh.
- Hot-key replication.
- Local fallback.
- Circuit breaker.

## Step 5: Partition and Shard

Partition dimensions:

- User ID.
- Tenant ID.
- Region.
- Time.
- Entity ID.
- Business domain.

Good partition key:

- High cardinality.
- Even distribution.
- Query-aligned.
- Stable over time.
- Supports locality when needed.

Bad partition key:

- Low cardinality.
- Monotonic timestamp without bucketing.
- Celebrity/user hotspot.
- Tenant key without handling large tenants.

Shard management:

- Consistent hashing.
- Virtual shards.
- Directory service.
- Resharding workflow.
- Hot-shard detection.
- Rebalancing.
- Per-shard SLOs.

## Step 6: Async Processing

Use async for:

- Email/SMS/push.
- Search indexing.
- Analytics.
- Recommendations.
- Image/video processing.
- Fraud scoring that is not blocking.
- Webhook delivery.
- Audit export.

Do not use async to hide correctness requirements. If user-visible state must be correct immediately, design the consistency boundary explicitly.

Queue design:

- Partition key.
- Ordering requirement.
- Retry policy.
- DLQ.
- Idempotent consumer.
- Lag SLO.
- Back-pressure.
- Replay plan.

## Step 7: Handle Fanout

Fanout types:

- Fanout on write: precompute recipients/feed.
- Fanout on read: compute feed/query at request time.
- Hybrid: precompute for normal users, special handling for celebrities.

Decision factors:

- Follower count distribution.
- Freshness requirement.
- Storage budget.
- Read/write ratio.
- Ranking complexity.

## Step 8: Scale Databases

Progression:

1. Proper schema and indexes.
2. Query tuning.
3. Connection pooling.
4. Read replicas.
5. Caching.
6. Partitioning.
7. Sharding.
8. Specialized stores.
9. Data lifecycle and archival.

Do not shard before fixing:

- Bad queries.
- Missing indexes.
- N+1 access.
- Oversized transactions.
- Unbounded scans.
- Connection pool misuse.

## Step 9: Scale Services

Service scaling:

- Horizontal replicas.
- Stateless request handling.
- Autoscaling by RPS, CPU, queue depth, or custom metrics.
- Bulkheads by dependency.
- Circuit breakers.
- Adaptive concurrency limits.
- Load shedding.
- Priority traffic classes.

Pitfalls:

- Scaling app servers overloads the database.
- Autoscaling too slowly for traffic spikes.
- Cold starts and cache warmup.
- Shared downstream dependency becomes bottleneck.

## Step 10: Multi-Region Strategy

Options:

- Single region with global CDN.
- Active-passive.
- Active-active reads with single write region.
- Active-active writes with conflict resolution.
- Cell-based regional architecture.

Choose based on:

- Latency requirements.
- RTO/RPO.
- Consistency requirements.
- Data residency.
- Operational maturity.
- Cost.

Avoid active-active writes unless the business requirement justifies conflict complexity.

## Cell-Based Architecture

Use at very large scale to limit blast radius.

```text
Global Router -> Cell A: services + data + cache + queues
              -> Cell B: services + data + cache + queues
              -> Cell C: services + data + cache + queues
```

Benefits:

- Smaller blast radius.
- Easier capacity planning.
- Tenant/user isolation.
- Independent deploy/failover.

Costs:

- Routing complexity.
- Cross-cell workflows.
- Data movement.
- Operational overhead.

## Scaling Security and Abuse Controls

At millions of users, abuse becomes a scaling problem.

Controls:

- WAF and bot protection.
- Per-IP, per-user, per-tenant rate limits.
- Signup abuse detection.
- Credential stuffing protection.
- Fraud/risk scoring.
- Quotas.
- CAPTCHA or step-up auth where appropriate.
- Audit and anomaly detection.

## Scaling Observability

Track:

- SLO by user journey.
- RPS and error rate by route.
- p95/p99 latency.
- Saturation by dependency.
- Cache hit ratio.
- DB query latency and locks.
- Queue lag.
- Hot keys and hot shards.
- Regional traffic and failover capacity.
- Cost per request/user/tenant/event.

## Cost-Aware Scaling

Cost drivers:

- Always-on compute.
- Cross-region traffic.
- High-cardinality metrics.
- Log volume.
- Data retention.
- Replication factor.
- OLAP queries.
- AI/model inference.
- CDN egress.

Optimization levers:

- Autoscaling.
- Rightsizing.
- Storage tiering.
- Sampling logs/traces.
- Data lifecycle policies.
- Query optimization.
- Compression.
- Cache high-value reads.
- Batch low-priority work.

## Million-User Interview Questions

1. How would you scale a social feed to 10 million DAU?
2. How would you scale a notification system to 100 million messages/day?
3. How do you handle a celebrity hot key?
4. How do you scale a multi-tenant SaaS platform with one huge tenant?
5. How do you scale WebSocket presence to millions of concurrent users?
6. How do you scale search indexing for a large catalog?
7. How do you design rate limits at user, tenant, and global levels?
8. How do you move from single database to sharded database safely?
9. How do you design regional failover without data loss?
10. How do you keep observability cost under control at massive scale?

