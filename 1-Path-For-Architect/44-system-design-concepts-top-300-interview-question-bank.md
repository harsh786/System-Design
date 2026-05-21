# Top 300 System Design Concepts Interview Question Bank

Purpose: master the concepts behind system design interviews so any problem statement can be reduced to known primitives, trade-offs, and failure modes.

Use this with:

- `02-system-design-hld.md` for the answer structure.
- `41-system-design-top-100-problem-bank.md` for app-level practice problems.
- `17-caching-scaling-rate-limiting-resilience.md` for deeper scaling patterns.
- `08-distributed-systems.md` for distributed coordination and consistency.

How to practice:

1. Answer each question in 2-4 minutes.
2. Always explain the trade-off, not only the definition.
3. Include failure modes, metrics, and how you would verify the design in production.
4. Connect each concept to a real system: URL shortener, payment system, chat, feed, search, CDN, object storage, or workflow engine.

## Category Map

| Category | Range | What It Trains |
|---|---:|---|
| Requirements, scale, APIs, and SLOs | 1-15 | Problem framing and interview structure |
| Networking, protocols, and communication | 16-30 | HTTP, TCP, TLS, gRPC, WebSockets, SSE, long polling |
| Load balancing and traffic management | 31-45 | L4/L7, routing, health checks, global traffic |
| CDN, edge, and static content delivery | 46-60 | Edge caching, TTL, invalidation, origin protection |
| Caching strategies and cache correctness | 61-75 | Cache-aside, stampede, hot keys, invalidation |
| Rate limiting, quotas, and abuse control | 76-90 | Token bucket, distributed limits, fairness |
| Microservices, gateways, and service design patterns | 91-105 | Boundaries, discovery, gateway, mesh, config |
| Resilience, retries, and graceful degradation | 106-120 | Timeouts, circuit breakers, bulkheads, fallbacks |
| Data modeling, indexing, and query design | 121-135 | Access patterns, indexes, OLTP, NoSQL |
| Partitioning, sharding, and consistent hashing | 136-150 | Horizontal data scale and rebalancing |
| Replication, consistency, and transactions | 151-165 | Quorums, CAP, isolation, conflict resolution |
| Distributed coordination, locks, leases, and split brain | 166-180 | Fencing tokens, Chubby-style locking, leader election |
| Messaging, streaming, and event-driven architecture | 181-195 | Kafka, queues, outbox, CDC, ordering |
| Realtime delivery, presence, and collaboration | 196-210 | WebSockets, SSE, fanout, offline delivery |
| Search, ranking, feeds, and recommendation systems | 211-225 | Indexes, ranking, fanout, personalization |
| Object storage, file systems, and media pipelines | 226-240 | S3, chunks, replication, transcoding |
| Observability, SRE, and incident response | 241-255 | SLIs, SLOs, tracing, capacity, postmortems |
| Security, privacy, compliance, and multi-tenancy | 256-270 | Auth, isolation, encryption, auditability |
| Deployment, cloud, Kubernetes, and platform operations | 271-285 | Releases, autoscaling, cells, config, DR |
| Cost, performance, and architect-level synthesis | 286-300 | Trade-off judgment and senior-level reasoning |

## 1. Requirements, Scale, APIs, and SLOs

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 1 | How do you start any system design interview? | Clarify users, workflows, functional requirements, non-functional requirements, constraints, non-goals, and success metrics. |
| 2 | How do you convert vague scale into capacity estimates? | DAU, MAU, QPS, peak factor, read/write ratio, object size, retention, bandwidth, growth, and safety margin. |
| 3 | How do you estimate storage for a system? | Entity count, average payload size, indexes, replicas, metadata, compression, retention, backups, and growth. |
| 4 | How do you estimate bandwidth and network egress? | Request size, response size, fanout, media size, CDN hit ratio, cross-region replication, and peak traffic. |
| 5 | How do you define availability for an interview design? | SLA/SLO, uptime target, dependency math, regional failover, graceful degradation, and maintenance windows. |
| 6 | How do you define latency goals? | p50/p95/p99, client vs server latency, tail latency, network time, queueing, and dependency budgets. |
| 7 | How do you decide what is out of scope? | Interview timeboxing, product priorities, risk, MVP vs future extensions, and explicit assumptions. |
| 8 | How do you design APIs for a new service? | Resources or RPC methods, idempotency, pagination, filtering, versioning, errors, auth, and rate-limit headers. |
| 9 | When would you choose REST vs gRPC vs GraphQL? | Client type, schema contracts, streaming, latency, browser support, tooling, compatibility, and operational complexity. |
| 10 | How do you design idempotent APIs? | Idempotency keys, unique constraints, replay handling, status lookup, retries, and exactly-once illusion. |
| 11 | How do you design pagination? | Offset vs cursor, stable sort key, consistency, performance, page drift, and next-page tokens. |
| 12 | How do you handle API versioning? | Backward compatibility, additive changes, deprecation, consumer migration, schema evolution, and contract tests. |
| 13 | How do you model read-heavy vs write-heavy systems differently? | Caching, denormalization, materialized views, replicas, queues, batching, and consistency impact. |
| 14 | How do you identify the bottleneck in a design? | Capacity model, critical path, saturation point, queue depth, hot keys, DB limits, and dependency latency. |
| 15 | How do you explain trade-offs clearly in an interview? | State alternatives, decision criteria, why chosen option fits requirements, failure modes, and future migration path. |

## 2. Networking, Protocols, and Communication

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 16 | What happens when a user enters a URL in a browser? | DNS, TCP/TLS, HTTP request, CDN, load balancer, app, database, response, caching, and rendering. |
| 17 | Explain DNS and its system design implications. | Recursive resolution, authoritative servers, TTL, caching, geo DNS, failover, propagation delay, and split-horizon DNS. |
| 18 | What is TCP keep-alive and when does it matter? | Idle connection detection, NAT/firewall timeouts, long-lived connections, false liveness, and tuning. |
| 19 | Compare HTTP keep-alive and TCP keep-alive. | Connection reuse vs liveness probes, latency reduction, resource usage, idle timeout, and load balancer behavior. |
| 20 | How does TLS affect system design? | Handshake latency, certificate management, termination point, mTLS, offload, session resumption, and security. |
| 21 | Compare HTTP/1.1, HTTP/2, and HTTP/3. | Persistent connections, multiplexing, head-of-line blocking, QUIC, TLS, browser/server support, and proxy compatibility. |
| 22 | What is HTTP/2 multiplexing? | Multiple concurrent streams on one connection, prioritization, flow control, header compression, and operational caveats. |
| 23 | When would you choose gRPC? | Low-latency service-to-service calls, protobuf contracts, streaming, code generation, deadlines, and load balancing. |
| 24 | What are gRPC deadlines and why are they important? | Propagated time budgets, cancellation, avoiding resource leaks, retries, and dependency control. |
| 25 | Compare unary gRPC, server streaming, client streaming, and bidirectional streaming. | Use cases, backpressure, connection lifecycle, error handling, and observability. |
| 26 | When would you use WebSockets? | Bidirectional low-latency communication, connection state, scaling, heartbeats, fanout, and fallback strategy. |
| 27 | When would you use Server-Sent Events? | Server-to-client streaming, HTTP friendliness, automatic reconnect, browser support, and one-way limitations. |
| 28 | When would you use long polling? | Compatibility, near-realtime updates, request lifecycle, timeout tuning, load impact, and migration to SSE/WebSockets. |
| 29 | How do webhooks differ from polling? | Push delivery, retries, signatures, idempotency, replay, receiver availability, and observability. |
| 30 | How do you design protocol fallback for realtime systems? | WebSocket first, SSE fallback, long polling fallback, capability detection, load impact, and client compatibility. |

## 3. Load Balancing and Traffic Management

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 31 | What is load balancing and why is it required? | Horizontal scale, availability, health checks, routing, failover, and overload protection. |
| 32 | Compare L4 and L7 load balancers. | TCP/UDP vs HTTP awareness, routing features, TLS termination, latency, observability, and cost. |
| 33 | How does an L4 load balancer work? | Connection-level routing, NAT/direct server return, health checks, low overhead, and protocol transparency. |
| 34 | How does an L7 load balancer work? | HTTP routing, host/path/header rules, TLS termination, retries, WAF integration, and request inspection. |
| 35 | Compare round robin, least connections, weighted, and random load balancing. | Fairness, heterogeneous capacity, long-lived connections, burst behavior, and simplicity. |
| 36 | What is consistent-hashing-based load balancing? | Sticky routing, minimal remapping, cache affinity, virtual nodes, and hot-node mitigation. |
| 37 | What are sticky sessions and when are they harmful? | Session affinity, stateful apps, uneven load, failover pain, and stateless alternatives. |
| 38 | How do health checks work? | Liveness, readiness, dependency checks, false positives, check intervals, and outlier ejection. |
| 39 | What is connection draining? | Stop new requests, finish in-flight work, deployment safety, timeout, and long-lived connection handling. |
| 40 | How do global load balancers route traffic? | DNS, anycast, latency routing, geo routing, health checks, regional failover, and traffic policies. |
| 41 | How do you prevent load balancer retry storms? | Retry budgets, jitter, idempotency, circuit breakers, outlier detection, and backpressure. |
| 42 | How do load balancers handle WebSockets or long-lived connections? | Connection stickiness, idle timeout, scale limits, health checks, draining, and fanout design. |
| 43 | What is anycast routing? | Same IP announced from many regions, nearest routing, DDoS absorption, failover, and routing instability. |
| 44 | How do service meshes affect load balancing? | Sidecar routing, mTLS, retries, circuit breakers, telemetry, config complexity, and failure blast radius. |
| 45 | How do you design traffic shifting for canary releases? | Weighted routing, headers, tenants, metrics, rollback, guardrails, and state compatibility. |

## 4. CDN, Edge, and Static Content Delivery

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 46 | What is a CDN and when should you use it? | Edge caching, latency reduction, egress reduction, static/dynamic content, and global scale. |
| 47 | How does CDN cache lookup work? | Cache key, edge POP, regional cache, origin fetch, headers, TTL, and revalidation. |
| 48 | What is TTL and how do you choose it? | Freshness vs hit ratio, update frequency, cache-control headers, stale policy, and invalidation cost. |
| 49 | Explain cache invalidation at CDN scale. | Purge by URL/tag, versioned URLs, soft purge, propagation delay, and emergency rollback. |
| 50 | What is origin shielding? | Reduce origin load, regional shield cache, collapse requests, failover, and cost impact. |
| 51 | How do signed URLs and signed cookies work? | Private content delivery, expiry, token validation, path scoping, and leak risk. |
| 52 | How do you serve large video files efficiently? | Segmenting, adaptive bitrate, CDN caching, range requests, origin protection, and DRM. |
| 53 | How does CDN support range requests? | Partial content, resumable downloads, video seeking, cache fragmentation, and origin behavior. |
| 54 | How do you cache personalized content safely? | Vary headers, private cache, auth-aware keys, edge compute, and privacy risk. |
| 55 | What is stale-while-revalidate? | Serve stale content, refresh asynchronously, latency benefit, staleness bounds, and failure policy. |
| 56 | What is stale-if-error? | Serve cached content during origin failure, resilience, freshness risk, and user experience. |
| 57 | How do you protect origins from thundering herds? | Request coalescing, origin shield, rate limits, queues, circuit breakers, and cache warming. |
| 58 | What is edge compute? | Functions at edge, personalization, auth, redirects, latency, cold starts, and debugging complexity. |
| 59 | How do you design multi-CDN? | Vendor redundancy, traffic steering, monitoring, purge consistency, cost, and operational complexity. |
| 60 | How do you measure CDN effectiveness? | Hit ratio, byte hit ratio, origin offload, p95 latency, error rate, egress cost, and regional performance. |

## 5. Caching Strategies and Cache Correctness

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 61 | What problems does caching solve and create? | Latency, load, cost, staleness, invalidation, consistency, hot keys, and operational complexity. |
| 62 | Compare cache-aside, read-through, write-through, and write-behind. | Data flow, consistency, latency, failure modes, write loss risk, and operational fit. |
| 63 | What is cache invalidation and why is it hard? | Multiple copies, timing, race conditions, dependency graph, stale reads, and purge strategies. |
| 64 | How do you choose a cache key? | Identity, tenant, auth scope, version, locale, query params, permissions, and collision avoidance. |
| 65 | What is a cache stampede? | Concurrent misses, origin overload, request coalescing, locks, probabilistic refresh, and stale serving. |
| 66 | What is hot-key protection? | Key-level skew, replication, request coalescing, local cache, sharding, and load shedding. |
| 67 | What is negative caching? | Cache misses or errors, TTL bounds, preventing repeated expensive misses, and correctness risk. |
| 68 | How do you design multi-layer caching? | Browser, CDN, gateway, service local cache, distributed cache, database buffer cache, and invalidation. |
| 69 | How do you cache authorization-sensitive data? | Tenant-aware keys, permission versioning, private caches, invalidation on role change, and auditability. |
| 70 | What is write-through cache consistency risk? | Write path coupling, partial failure, retry behavior, cache/database ordering, and idempotency. |
| 71 | What is write-behind cache risk? | Data loss, ordering, durability, replay, backpressure, and reconciliation. |
| 72 | How do you design cache TTLs? | Freshness, traffic pattern, data volatility, error tolerance, randomized TTL, and business correctness. |
| 73 | What is cache warming? | Preloading hot data, deployment readiness, burst handling, stale data risk, and cost. |
| 74 | How do you monitor caches? | Hit ratio, miss latency, eviction, memory, hot keys, stampede events, stale serves, and backend load. |
| 75 | When should you not cache? | Low reuse, strict freshness, high cardinality, auth sensitivity, invalidation complexity, and memory cost. |

## 6. Rate Limiting, Quotas, and Abuse Control

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 76 | Why do systems need rate limiting? | Abuse prevention, fairness, cost control, dependency protection, SLO protection, and tenant isolation. |
| 77 | Compare token bucket and leaky bucket. | Burst allowance, steady drain, implementation, fairness, and use cases. |
| 78 | Compare fixed window, sliding window log, and sliding window counter. | Accuracy, memory, boundary burst, performance, and distributed implementation. |
| 79 | How do you design a distributed rate limiter? | Shared store, local preallocation, eventual accuracy, clock issues, sharding, and failure mode. |
| 80 | How do you rate-limit by user, IP, API key, tenant, and endpoint? | Key hierarchy, cardinality, fairness, spoofing risk, and quota policy. |
| 81 | How do you handle rate-limit responses? | HTTP 429, retry-after, headers, error body, client guidance, and observability. |
| 82 | How do you prevent a rate limiter from becoming the bottleneck? | Local cache, batching, approximate counters, sharding, async logging, and fail-open/fail-closed choice. |
| 83 | What is adaptive rate limiting? | Dynamic limits based on saturation, latency, dependency health, tenant priority, and feedback loops. |
| 84 | How do quotas differ from rate limits? | Long-term consumption, daily/monthly limits, billing, enforcement, and reset behavior. |
| 85 | How do you design abuse detection beyond rate limits? | Reputation, anomaly detection, bot signals, device fingerprinting, WAF, and manual review. |
| 86 | What is load shedding? | Reject low-priority work, protect core flows, overload signals, error semantics, and recovery. |
| 87 | How do you rate-limit WebSocket connections? | Connection count, message rate, fanout cost, heartbeat abuse, and per-tenant limits. |
| 88 | How do you rate-limit background jobs? | Queue depth, worker concurrency, downstream capacity, priority, and backpressure. |
| 89 | How do you design fair usage for multi-tenant systems? | Tenant quotas, noisy-neighbor isolation, weighted fairness, burst credits, and priority tiers. |
| 90 | When should a rate limiter fail open vs fail closed? | Security risk, availability risk, dependency state, cached decisions, and business criticality. |

## 7. Microservices, Gateways, and Service Design Patterns

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 91 | How do you choose microservice boundaries? | Business capability, data ownership, team ownership, coupling, transactions, and change rate. |
| 92 | What is the difference between microservices and distributed monoliths? | Independent deployability, data ownership, API contracts, coupling, and operational maturity. |
| 93 | What is an API gateway responsible for? | Routing, auth, rate limits, quotas, transformation, observability, canary, and policy enforcement. |
| 94 | What should not live in an API gateway? | Deep business logic, complex orchestration, service-specific rules, and hidden coupling. |
| 95 | What is BFF architecture? | Client-specific APIs, frontend needs, aggregation, security, ownership, and duplication tradeoffs. |
| 96 | What is service discovery? | Registry, health, DNS vs client discovery, dynamic endpoints, and stale instances. |
| 97 | How does centralized configuration work? | Dynamic config, validation, rollout, audit, secrets separation, and blast radius. |
| 98 | What is the strangler fig pattern? | Incremental migration, facade, routing, data sync, rollback, and risk reduction. |
| 99 | What is the saga pattern? | Distributed transaction alternative, choreography/orchestration, compensation, idempotency, and observability. |
| 100 | What is the outbox pattern? | Atomic DB write plus event publish, relay, idempotent consumers, ordering, and cleanup. |
| 101 | What is CQRS? | Separate read/write models, materialized views, eventual consistency, complexity, and fit. |
| 102 | What is event sourcing? | Event log as source of truth, projections, replay, schema evolution, and auditability. |
| 103 | How do services share data safely? | API ownership, events, CDC, read models, avoiding shared databases, and consistency choices. |
| 104 | What is a service mesh? | mTLS, routing, retries, telemetry, policy, sidecar overhead, and control-plane risk. |
| 105 | How do you manage service contract compatibility? | Backward-compatible APIs, schema evolution, consumer-driven contracts, versioning, and deprecation. |

## 8. Resilience, Retries, and Graceful Degradation

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 106 | Why are timeouts mandatory in distributed systems? | Resource protection, bounded latency, cascading failure prevention, and end-to-end deadlines. |
| 107 | How do you choose timeout values? | Latency percentiles, dependency budgets, user SLO, retry budget, and false timeout tradeoff. |
| 108 | How do retries cause outages? | Retry storms, amplification, non-idempotent operations, queue buildup, and dependency overload. |
| 109 | What is exponential backoff with jitter? | Spreading retries, avoiding synchronization, capped retries, and retry budgets. |
| 110 | What is a circuit breaker? | Closed/open/half-open states, failure thresholds, recovery, fallback, and observability. |
| 111 | What is a bulkhead? | Isolation by pool/queue/tenant/dependency, noisy-neighbor protection, and capacity partitioning. |
| 112 | What is graceful degradation? | Disable noncritical features, serve stale data, reduced quality, and preserving core workflows. |
| 113 | What is a fallback and when is it dangerous? | Alternative response, stale/default data, silent correctness loss, and user transparency. |
| 114 | What is hedged request design? | Duplicate slow requests, tail latency reduction, cost amplification, cancellation, and idempotency. |
| 115 | What is backpressure? | Producer slowdown, bounded queues, flow control, rejection, and overload signaling. |
| 116 | How do you avoid cascading failures? | Timeouts, bulkheads, circuit breakers, load shedding, fallbacks, and dependency health. |
| 117 | What is brownout mode? | Disable optional work during overload, priority preservation, feature flags, and recovery automation. |
| 118 | How do you design safe retries for payments or orders? | Idempotency keys, state machine, dedupe table, external provider reconciliation, and audit log. |
| 119 | How do you design priority-based degradation? | Critical vs best-effort traffic, queues, admission control, tenant tiers, and SLO policies. |
| 120 | How do you test resilience patterns? | Fault injection, chaos testing, dependency simulation, load tests, and SLO validation. |

## 9. Data Modeling, Indexing, and Query Design

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 121 | How do you start data modeling in system design? | Access patterns, entities, relationships, cardinality, query shapes, retention, and consistency. |
| 122 | When do you normalize vs denormalize data? | Write amplification, read latency, consistency, storage cost, and update complexity. |
| 123 | How do indexes work conceptually? | Search structures, lookup vs scan, write overhead, storage overhead, and selectivity. |
| 124 | What makes a good database index? | Query pattern, cardinality, selectivity, sort support, covering index, and maintenance cost. |
| 125 | What is a composite index? | Column order, equality/range predicates, sort order, prefix usage, and query planning. |
| 126 | What is a covering index? | Query served from index, reduced IO, storage cost, and write overhead. |
| 127 | Why can too many indexes hurt performance? | Write amplification, storage, cache pressure, slower updates, and planner complexity. |
| 128 | How do you design indexes for pagination? | Stable sort key, cursor, composite index, tie-breaker, and avoiding large offsets. |
| 129 | How do you model many-to-many relationships at scale? | Join table, denormalized edges, secondary indexes, graph store, and query constraints. |
| 130 | When would you choose SQL vs NoSQL? | Query flexibility, transactions, schema, scale pattern, operational maturity, and consistency. |
| 131 | When would you choose document databases? | Aggregate-oriented data, flexible schema, read patterns, indexing limits, and update concerns. |
| 132 | When would you choose wide-column stores? | High write throughput, partition-key access, time-series, large scale, and limited ad hoc queries. |
| 133 | When would you choose graph databases? | Relationship traversal, graph algorithms, fraud/social/identity use cases, and scaling limits. |
| 134 | How do you model time-series data? | Time partitioning, downsampling, retention, tags, high cardinality, and query windows. |
| 135 | How do you avoid hot rows and hot indexes? | Key design, randomization, bucketing, sharding, batching, and write distribution. |

## 10. Partitioning, Sharding, and Consistent Hashing

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 136 | What is partitioning? | Splitting data by range/hash/list/time, query routing, scale, and operational tradeoffs. |
| 137 | What is sharding? | Horizontal partitioning across nodes, shard key, routing, rebalancing, and failure domains. |
| 138 | How do you choose a shard key? | Access pattern, cardinality, distribution, tenant isolation, locality, and future growth. |
| 139 | What is the difference between range and hash partitioning? | Range scans/locality vs distribution, hot partitions, rebalancing, and query support. |
| 140 | How do you handle hot partitions? | Better key, salting, sub-shards, caching, write buffering, and tenant isolation. |
| 141 | What is consistent hashing? | Hash ring, minimal remapping, virtual nodes, replication, and node churn. |
| 142 | Why are virtual nodes used in consistent hashing? | Better balance, heterogeneous capacity, smoother rebalancing, and operational control. |
| 143 | How do you rebalance shards safely? | Dual writes, backfill, routing table updates, verification, throttling, and rollback. |
| 144 | What is a shard map or routing table? | Key-to-shard mapping, metadata service, cache, versioning, and failover. |
| 145 | How do cross-shard queries work? | Scatter-gather, fanout cost, aggregation, pagination difficulty, and denormalized read models. |
| 146 | How do cross-shard transactions work? | Avoidance, two-phase commit, sagas, idempotency, and compensation. |
| 147 | How do you shard multi-tenant systems? | Tenant-based sharding, shared vs dedicated shards, noisy-neighbor control, and tenant migration. |
| 148 | What is time-based partitioning? | Retention, archival, time-window queries, hot current partition, and compaction. |
| 149 | How do you design partitioning for message queues? | Ordering key, consumer parallelism, hot keys, rebalancing, and lag. |
| 150 | How do you know when to shard? | Capacity evidence, single-node limits, operational cost, query pattern, and simpler alternatives first. |

## 11. Replication, Consistency, and Transactions

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 151 | What is replication and why is it used? | Availability, read scale, durability, geo locality, failover, and lag. |
| 152 | Compare synchronous and asynchronous replication. | Latency, durability, data loss window, availability, and write acknowledgement. |
| 153 | Compare leader-follower, multi-leader, and leaderless replication. | Write routing, conflicts, failover, availability, and operational complexity. |
| 154 | What is replication lag and why does it matter? | Stale reads, read-your-writes, failover risk, monitoring, and mitigation. |
| 155 | What is quorum-based replication? | Read/write quorum, consistency, availability, latency, and failure tolerance. |
| 156 | Explain CAP theorem correctly. | Network partitions, consistency, availability, partition tolerance, and real design nuance. |
| 157 | What is eventual consistency? | Convergence, stale reads, conflict handling, user experience, and monitoring. |
| 158 | What is strong consistency? | Linearizability, coordination cost, latency, availability tradeoff, and use cases. |
| 159 | What are read-your-writes and monotonic reads? | Session guarantees, routing to leader, sticky reads, tokens, and user experience. |
| 160 | What is transaction isolation? | Dirty reads, non-repeatable reads, phantoms, serializability, and database-specific behavior. |
| 161 | What is two-phase commit? | Prepare/commit, coordinator, blocking failure mode, participant recovery, and alternatives. |
| 162 | What is optimistic concurrency control? | Version checks, compare-and-swap, retries, conflicts, and high-read scenarios. |
| 163 | What is pessimistic locking? | Locks before update, contention, deadlocks, timeouts, and correctness. |
| 164 | How do you resolve conflicts in multi-writer systems? | Last-write-wins risk, vector clocks, CRDTs, merge functions, and business rules. |
| 165 | How do you design data reconciliation? | Source of truth, audit log, periodic jobs, checksums, repair, and manual exception handling. |

## 12. Distributed Coordination, Locks, Leases, and Split Brain

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 166 | What is distributed coordination? | Agreement among nodes, membership, leader election, locks, metadata, and failure detection. |
| 167 | Why is distributed locking hard? | Partial failures, pauses, clock drift, network partitions, stale holders, and split brain. |
| 168 | What is a lease? | Time-bound ownership, expiry, renewal, clock assumptions, and safe handoff. |
| 169 | What is a fencing token? | Monotonic token, stale owner protection, storage-side validation, and correctness beyond locks. |
| 170 | How do fencing tokens prevent stale writes? | Every lock acquisition gets higher token, resource rejects old token, and handles paused clients. |
| 171 | What is split brain? | Multiple leaders, partitioned cluster, conflicting writes, quorum, and remediation. |
| 172 | How do quorum systems reduce split brain risk? | Majority requirement, odd node counts, leader election, availability tradeoffs, and partition behavior. |
| 173 | What is leader election? | Candidate, term/epoch, quorum, heartbeat, failover, and avoiding dual leaders. |
| 174 | How do systems like Chubby or ZooKeeper support locking? | Ephemeral nodes, sessions, watches, sequencing, leases, and coordination service availability. |
| 175 | What is Chubby-style locking? | Coarse-grained coordination, advisory locks, sessions, keepalives, lock delay, and operational use. |
| 176 | What are ephemeral nodes and watches? | Session-bound metadata, change notification, missed events, re-read requirement, and herd effect. |
| 177 | What is the herd effect in coordination systems? | Many clients awakened together, overload, watch granularity, and staggered retries. |
| 178 | How do clock drift and pauses affect leases? | Expiry ambiguity, GC pauses, NTP issues, monotonic clocks, and fencing. |
| 179 | How would you critique Redis-based distributed locks? | Single instance risk, Redlock assumptions, clock timing, fencing absence, and safe use cases. |
| 180 | When should you avoid distributed locks? | Prefer partition ownership, idempotency, queues, database constraints, or single-writer design. |

## 13. Messaging, Streaming, and Event-Driven Architecture

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 181 | Compare queues, pub-sub, and event logs. | Consumer model, retention, replay, ordering, fanout, and use cases. |
| 182 | How does Kafka partitioning work? | Key-to-partition mapping, ordering within partition, parallelism, hot keys, and rebalancing. |
| 183 | What are consumer groups? | Parallel consumption, partition assignment, offsets, rebalancing, and lag. |
| 184 | What is consumer lag? | Offset gap, processing bottleneck, partition skew, alerting, and remediation. |
| 185 | Compare at-most-once, at-least-once, and exactly-once delivery. | Loss, duplicates, transactions, idempotency, and practical guarantees. |
| 186 | How do you design idempotent consumers? | Dedupe keys, processed-message table, business idempotency, ordering, and retries. |
| 187 | What is a dead-letter queue? | Poison messages, retry exhaustion, inspection, replay, and alerting. |
| 188 | How do you handle message ordering? | Partition key, single consumer per partition, sequence numbers, buffering, and tradeoffs. |
| 189 | What is the transactional outbox pattern? | Atomic write plus event, relay, dedupe, ordering, and cleanup. |
| 190 | What is CDC and when is it useful? | Database change capture, integration, outbox relay, schema evolution, and replay. |
| 191 | How do you evolve event schemas? | Backward/forward compatibility, schema registry, optional fields, versioning, and consumer rollout. |
| 192 | What is event replay? | Retention, rebuilding projections, idempotency, side-effect suppression, and cost. |
| 193 | How do you design delayed or scheduled messages? | Delay queue, timer wheel, sorted set, cron scheduler, persistence, and retry. |
| 194 | How do you design priority queues? | Multiple queues, starvation prevention, fairness, ordering tradeoff, and backpressure. |
| 195 | How do you monitor event-driven systems? | Lag, throughput, error rate, DLQ size, retry rate, handler latency, and schema failures. |

## 14. Realtime Delivery, Presence, and Collaboration

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 196 | How do you design a realtime connection service? | WebSockets/SSE, connection registry, authentication, heartbeats, sharding, and fanout. |
| 197 | How do you scale WebSocket servers? | Stateless handshake, connection state, sticky routing, pub-sub, shard ownership, and draining. |
| 198 | How do you detect stale realtime connections? | Heartbeats, ping/pong, timeout, TCP keep-alive, client reconnect, and cleanup. |
| 199 | How do you design online presence? | Last seen, active connections, device state, TTL, heartbeats, fanout, and privacy. |
| 200 | How do you deliver messages to offline users? | Durable inbox, push notification, unread state, sync cursor, and retry. |
| 201 | How do you design read receipts? | Per-user message state, privacy, fanout cost, batching, and consistency. |
| 202 | How do you design typing indicators? | Ephemeral events, TTL, throttling, fanout, and no persistence. |
| 203 | How do you design notification fanout? | User preferences, channels, priority, dedupe, rate limits, templates, and retries. |
| 204 | How do you design collaborative editing? | OT vs CRDT, conflict resolution, operation ordering, snapshots, and presence. |
| 205 | How do you design realtime counters? | Approximation, batching, pub-sub, materialized state, and eventual consistency. |
| 206 | How do you handle reconnect storms? | Jittered reconnect, backoff, admission control, regional health, and client guidance. |
| 207 | How do you secure realtime connections? | Auth token refresh, origin checks, message authorization, rate limits, and encryption. |
| 208 | How do you design mobile realtime delivery? | Battery, flaky network, push fallback, reconnect, offline sync, and bandwidth. |
| 209 | How do you choose between WebSockets, SSE, and long polling? | Directionality, compatibility, intermediaries, scaling, latency, and operational cost. |
| 210 | How do you observe realtime systems? | Active connections, fanout latency, disconnects, reconnect rate, message drops, and shard load. |

## 15. Search, Ranking, Feeds, and Recommendation Systems

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 211 | How does an inverted index work? | Terms, postings lists, tokenization, ranking, updates, and storage. |
| 212 | How do you design autocomplete? | Trie, prefix index, n-grams, ranking, personalization, cache, and typo tolerance. |
| 213 | How do you design full-text search at scale? | Indexing pipeline, shards, replicas, analyzers, ranking, freshness, and reindexing. |
| 214 | How do you design search indexing pipelines? | CDC/events, bulk indexing, retries, DLQ, idempotency, and consistency lag. |
| 215 | How do you handle search relevance? | Ranking signals, text score, freshness, popularity, personalization, and evaluation. |
| 216 | What is a materialized view? | Precomputed read model, freshness, invalidation, rebuild, and query performance. |
| 217 | How do you design a news feed? | Fanout-on-write, fanout-on-read, hybrid, ranking, privacy, and cache. |
| 218 | How do you handle celebrity users in feeds? | Hybrid fanout, pull model, cache, batching, and hot-key control. |
| 219 | How do you design timeline pagination? | Cursor by time/score, stable ordering, duplicates, gaps, and refresh behavior. |
| 220 | How do you design recommendation serving? | Candidate generation, ranking, features, online/offline split, cache, and feedback loop. |
| 221 | What is a Bloom filter and where is it used? | Probabilistic membership, false positives, no false negatives, cache penetration, and dedupe. |
| 222 | How do you design trending topics? | Event aggregation, windows, decay, dedupe, spam control, and regionalization. |
| 223 | How do you design a like/view counter? | Write aggregation, approximate counts, idempotency, anti-abuse, and read model. |
| 224 | How do you design ranking experiments? | A/B tests, guardrail metrics, bias, rollout, and offline/online evaluation. |
| 225 | How do you prevent search or feed abuse? | Spam detection, rate limits, trust signals, moderation, ranking penalties, and audit. |

## 16. Object Storage, File Systems, and Media Pipelines

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 226 | How do you design object storage like S3? | Buckets, objects, metadata, partitioning, durability, replication, and access control. |
| 227 | How do you store large files? | Chunking, multipart upload, checksums, resumability, metadata, and repair. |
| 228 | How do you design file metadata storage? | Namespace, path hierarchy, permissions, versions, indexes, and consistency. |
| 229 | How do you ensure object durability? | Replication, erasure coding, checksums, scrubbing, repair, and failure domains. |
| 230 | Compare replication and erasure coding. | Storage overhead, repair cost, durability, read latency, and complexity. |
| 231 | How do you design upload pipelines? | Pre-signed URLs, multipart, virus scanning, metadata commit, retry, and idempotency. |
| 232 | How do you design image thumbnail generation? | Async jobs, queue, idempotency, variants, cache, and failure handling. |
| 233 | How do you design video transcoding? | Job queue, worker fleet, segmenting, formats, retries, progress, and cost. |
| 234 | How do you design media streaming? | HLS/DASH, segments, manifests, CDN, adaptive bitrate, and DRM. |
| 235 | How do you design backup and restore systems? | Snapshots, incremental backups, retention, encryption, restore testing, and RPO/RTO. |
| 236 | How do you design deduplication? | Content hashing, chunking, reference counts, collision risk, and security. |
| 237 | How do you design file sharing permissions? | ACLs, inherited permissions, links, expiry, audit, and revocation. |
| 238 | How do you handle object lifecycle policies? | TTL, archival tiers, legal hold, deletion, compaction, and cost. |
| 239 | How do you design geo-replicated object storage? | Replication lag, read locality, conflict handling, failover, and compliance. |
| 240 | How do you monitor storage systems? | Durability repair, latency, error rate, capacity, hot partitions, and checksum failures. |

## 17. Observability, SRE, and Incident Response

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 241 | What are SLIs, SLOs, and error budgets? | User-facing measures, targets, allowed failure, release decisions, and alerting. |
| 242 | How do you choose SLIs for an API? | Availability, latency, correctness, freshness, saturation, and dependency-aware metrics. |
| 243 | What should dashboards show? | Golden signals, saturation, dependency health, business metrics, regional breakdown, and recent deploys. |
| 244 | How do you design alerts? | Symptoms over causes, paging vs ticket, burn-rate alerts, dedupe, and actionable runbooks. |
| 245 | Compare logs, metrics, traces, and profiles. | Events, aggregates, request flow, code hotspots, and correlation. |
| 246 | How do distributed traces help system design? | Critical path, dependency latency, fanout, retries, errors, and sampling tradeoffs. |
| 247 | What is high-cardinality telemetry? | Labels, cost, query performance, tenant/user IDs, and safe cardinality control. |
| 248 | How do you monitor queues? | Lag, age of oldest message, throughput, retries, DLQ, worker saturation, and processing latency. |
| 249 | How do you monitor caches? | Hit ratio, miss latency, evictions, memory, hot keys, stampede, and backend load. |
| 250 | How do you perform capacity planning? | Current load, growth, peak factor, saturation tests, headroom, and cost model. |
| 251 | How do you design load tests? | Realistic traffic mix, ramp, soak, spike, dependency simulation, and SLO validation. |
| 252 | What is chaos engineering? | Controlled failure injection, hypotheses, blast radius, rollback, and learning. |
| 253 | How do you run an incident? | Severity, roles, communication, mitigation, timeline, decision log, and customer impact. |
| 254 | What makes a strong postmortem? | Blameless facts, root causes, contributing factors, action items, owners, and due dates. |
| 255 | How do you verify a fix after an outage? | Regression tests, dashboards, replay, canary, load test, and post-deploy monitoring. |

## 18. Security, Privacy, Compliance, and Multi-Tenancy

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 256 | How do authentication and authorization differ? | Identity vs permission, sessions/tokens, RBAC/ABAC, and enforcement points. |
| 257 | How do you design OAuth2/OIDC login? | Authorization code flow, PKCE, tokens, scopes, refresh, session management, and logout. |
| 258 | How do you design API authorization? | Resource checks, tenant checks, policy engine, caching, audit, and least privilege. |
| 259 | How do you design multi-tenant isolation? | Tenant ID everywhere, data isolation, compute isolation, quotas, encryption, and audit. |
| 260 | Compare shared database, shared schema, separate schema, and separate database tenancy. | Cost, isolation, operations, compliance, noisy neighbors, and migration. |
| 261 | How do you encrypt data in transit and at rest? | TLS/mTLS, KMS, envelope encryption, key rotation, and access control. |
| 262 | How do you manage secrets? | Secret store, rotation, least privilege, no logs, no env sprawl, and emergency revocation. |
| 263 | How do you design audit logs? | Immutable records, actor/action/resource/time, integrity, retention, and searchability. |
| 264 | How do you protect against replay attacks? | Nonces, timestamps, signatures, idempotency, expiry, and clock skew. |
| 265 | How do you secure webhooks? | Signatures, timestamp, replay protection, retries, idempotency, and secret rotation. |
| 266 | How do you design data deletion for privacy laws? | Data inventory, deletion workflow, tombstones, backups, audit, and downstream propagation. |
| 267 | How do you design data residency? | Region pinning, routing, storage, processing, replication boundaries, and compliance evidence. |
| 268 | How do you prevent tenant data leakage through caches? | Tenant-aware keys, auth scope, private caches, invalidation, and tests. |
| 269 | How do you design abuse-resistant public APIs? | Auth, rate limits, quotas, WAF, bot detection, validation, and anomaly detection. |
| 270 | How do you threat model a system design? | Assets, actors, trust boundaries, data flows, STRIDE-style risks, and mitigations. |

## 19. Deployment, Cloud, Kubernetes, and Platform Operations

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 271 | Compare rolling, blue-green, and canary deployments. | Risk, capacity, rollback, state compatibility, observability, and cost. |
| 272 | What is a feature flag platform? | Runtime control, targeting, kill switch, audit, stale flag cleanup, and blast radius. |
| 273 | How do you perform database migrations safely? | Expand/contract, backward compatibility, backfill, dual writes, verification, and rollback. |
| 274 | How do you design zero-downtime deploys? | Compatibility, draining, health checks, idempotency, migrations, and rollout guardrails. |
| 275 | What is autoscaling and what can go wrong? | CPU/RPS/queue metrics, lag, cold starts, thrashing, dependency saturation, and limits. |
| 276 | How do Kubernetes readiness and liveness probes differ? | Traffic eligibility vs restart signal, dependency checks, startup behavior, and false positives. |
| 277 | How do you design service discovery in Kubernetes? | Services, DNS, endpoints, readiness, load balancing, and mesh integration. |
| 278 | How do you handle configuration rollout? | Validation, staged rollout, dynamic reload, audit, rollback, and tenant targeting. |
| 279 | What is a control plane vs data plane? | Management decisions vs request serving, failure modes, isolation, and scalability. |
| 280 | What are regional cells? | Isolated regional units, blast-radius control, tenant routing, failover, and operations. |
| 281 | How do you design disaster recovery? | RTO/RPO, backups, replication, failover, runbooks, drills, and data integrity. |
| 282 | How do you design active-active multi-region systems? | Routing, data replication, conflict resolution, locality, failover, and consistency. |
| 283 | How do you design active-passive failover? | Standby readiness, replication lag, DNS/traffic switch, testing, and failback. |
| 284 | How do you design infrastructure as code safely? | Review, policy, drift detection, state management, secrets, and staged rollout. |
| 285 | How do you operate dependency upgrades? | Compatibility, canary, rollback, migration plan, observability, and security patches. |

## 20. Cost, Performance, and Architect-Level Synthesis

| # | Question | Strong Answer Must Cover |
|---:|---|---|
| 286 | How do you reason about cost in system design? | Compute, storage, network egress, managed services, replicas, peak capacity, and operations. |
| 287 | How do you reduce latency in a distributed system? | Critical path, caching, locality, parallelism, connection reuse, batching, and dependency reduction. |
| 288 | How do you improve throughput? | Horizontal scale, batching, async processing, partitioning, backpressure, and bottleneck removal. |
| 289 | How do you reduce tail latency? | Hedging, timeout budgets, queue control, isolation, hot-key mitigation, and p99 monitoring. |
| 290 | How do you design for one billion requests per day? | QPS conversion, peak factor, regional distribution, caching, load balancing, autoscaling, and cost. |
| 291 | How do you design for one million concurrent connections? | Event-driven servers, connection sharding, heartbeats, memory per connection, and fanout. |
| 292 | How do you evaluate build vs buy? | Core differentiation, maturity, cost, compliance, lock-in, operational skill, and exit strategy. |
| 293 | How do you choose managed services vs self-hosted? | Operational burden, control, portability, scale, cost, SLA, and customization. |
| 294 | How do you design migration from monolith to services? | Strangler, boundaries, data ownership, dual-run, observability, rollback, and team model. |
| 295 | How do you design for extensibility without overengineering? | Known variation points, contracts, modularity, YAGNI, and migration path. |
| 296 | How do you compare two architecture options in an interview? | Requirements fit, complexity, scale, reliability, cost, security, and operational risk. |
| 297 | How do you handle interviewer pushback? | Clarify requirement change, revisit assumptions, discuss alternatives, and update tradeoffs. |
| 298 | How do you identify hidden single points of failure? | Dependency map, control planes, metadata stores, DNS, queues, caches, and operational processes. |
| 299 | How do you make a design production-ready? | SLOs, monitoring, runbooks, DR, security, capacity, rollout, testing, and cost controls. |
| 300 | What separates senior system design answers from average answers? | Explicit tradeoffs, failure thinking, measurable capacity, operability, security, migration path, and crisp communication. |

## Interview Answer Framework

For each concept, use this structure:

1. Define the concept in one sentence.
2. Explain the problem it solves.
3. Name the main alternatives.
4. State the trade-offs.
5. Describe one failure mode.
6. Describe how to monitor it.
7. Connect it to a real system design problem.

## High-Frequency Deep-Dive Clusters

Interviewers often chain concepts like this:

- Load balancing -> L4 vs L7 -> health checks -> retries -> circuit breakers -> connection draining.
- Caching -> TTL -> invalidation -> stampede -> hot keys -> cache consistency.
- Rate limiting -> token bucket -> distributed counters -> abuse control -> fairness -> backpressure.
- Sharding -> shard key -> consistent hashing -> rebalancing -> hot partitions -> cross-shard queries.
- Replication -> quorum -> consistency -> failover -> split brain -> fencing tokens.
- Distributed locking -> leases -> Chubby/ZooKeeper -> fencing tokens -> avoiding locks.
- Realtime -> WebSockets/SSE/long polling -> heartbeats -> presence -> fanout -> reconnect storms.
- Messaging -> partitions -> ordering -> consumer lag -> DLQ -> outbox -> CDC -> replay.
- Microservices -> boundaries -> API gateway -> service discovery -> saga -> outbox -> observability.
- Production readiness -> SLO -> dashboard -> alert -> runbook -> incident -> postmortem.
