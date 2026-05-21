# Performance and Capacity Engineering

Architect interviews often separate senior engineers from architects through performance reasoning. You need to model load before building, identify bottlenecks under stress, and explain how you will preserve latency, throughput, and cost under growth.

## Architect-Level Outcome

You should be able to predict, test, observe, and improve performance across application code, databases, caches, queues, networks, Kubernetes, and cloud infrastructure.

## Performance Answer Formula

```text
Define user journey -> Define SLO -> Estimate load -> Build capacity model -> Identify bottleneck -> Test under realistic traffic -> Observe saturation -> Optimize highest constraint -> Add headroom -> Re-test
```

## Core Concepts

| Concept | Meaning | Interview Use |
| --- | --- | --- |
| Throughput | Work completed per unit time. | QPS, events/sec, jobs/min, MB/sec. |
| Latency | Time to complete one operation. | p50, p95, p99, p999, timeout budget. |
| Utilization | Fraction of resource capacity used. | CPU, memory, disk, network, DB connections. |
| Saturation | Resource has queued work it cannot immediately serve. | Queue depth, thread pool backlog, Kafka lag. |
| Back-pressure | Slowing producers when consumers are overloaded. | Bounded queues, rate limits, 429, consumer lag. |
| Headroom | Reserved spare capacity for bursts and failover. | N+1, regional failover, peak traffic. |
| Tail latency | Slowest user-visible requests. | Critical for fanout systems. |

## Little's Law

```text
L = lambda * W
```

- `L`: average number of items in the system.
- `lambda`: arrival rate.
- `W`: average time in system.

Interview use:

- If a service handles 1,000 requests/sec and average latency is 200 ms, about 200 requests are concurrently in flight.
- If latency rises while arrival rate is stable, concurrency and queue depth grow.
- If a thread pool or DB pool is smaller than required concurrency, requests wait.

## Queueing Intuition

- As utilization approaches 100%, latency grows nonlinearly.
- A system can have acceptable average latency but bad p99 latency.
- Fanout makes tail latency worse because the slowest dependency controls the aggregate response.
- Retry storms increase arrival rate exactly when capacity is already weak.
- Back-pressure is better than unbounded queues because it preserves system stability.

## Capacity Model Template

Use this for every HLD:

| Dimension | Estimate |
| --- | --- |
| Users | DAU, MAU, concurrent users, peak factor. |
| Requests | Average QPS, peak QPS, write QPS, read QPS. |
| Payload | Request/response size, compression, bandwidth. |
| Storage | New data/day, retention, replication, indexes, backups. |
| Compute | CPU per request, memory per instance, startup time. |
| Database | Reads/sec, writes/sec, transactions/sec, connection count. |
| Cache | Working set, hit ratio, item size, eviction policy. |
| Queue | Events/sec, partition count, consumer parallelism, lag target. |
| Region | Failover capacity, data residency, cross-region replication. |
| Cost | Unit cost per request, user, GB, event, query, or tenant. |

## Latency Budgeting

For a 300 ms p95 endpoint:

| Component | Budget |
| --- | --- |
| Edge and TLS | 20 ms |
| API gateway/auth | 25 ms |
| Application logic | 60 ms |
| Cache lookup | 10 ms |
| Database query | 80 ms |
| Downstream service | 70 ms |
| Serialization/network | 25 ms |
| Buffer | 10 ms |

Rules:

- Every dependency must have a timeout below the caller timeout.
- Retry budget must fit within the end-to-end latency budget.
- Expensive work should move async if it is not required for the immediate response.
- Fanout calls need hedging, aggregation limits, caching, or precomputation.

## Load Testing Strategy

| Test | Purpose |
| --- | --- |
| Smoke test | Confirm the path works with tiny traffic. |
| Load test | Validate expected traffic and SLO. |
| Stress test | Find the breaking point. |
| Spike test | Validate sudden traffic jumps. |
| Soak test | Find leaks, fragmentation, connection exhaustion, slow degradation. |
| Failover test | Validate N+1 or regional failover under load. |
| Chaos test | Validate fault handling and graceful degradation. |
| Benchmark | Compare implementations under controlled inputs. |

Test design checklist:

- Use realistic request mix.
- Use realistic payload sizes.
- Include authentication, TLS, serialization, and network path.
- Warm caches separately from cold-cache tests.
- Test both read-heavy and write-heavy cases.
- Track p50, p90, p95, p99, p999, error rate, saturation, and cost.
- Run long enough to expose memory leaks and compaction/GC effects.

## Bottleneck Playbook

### CPU Bound

Symptoms:

- High CPU utilization.
- Run queue grows.
- p99 latency increases.
- Flame graph shows hot functions.

Actions:

- Profile first.
- Reduce algorithmic complexity.
- Remove avoidable serialization/deserialization.
- Batch small operations.
- Cache expensive pure computations.
- Use better data structures.
- Scale horizontally if work is stateless.

### Memory Bound

Symptoms:

- High allocation rate.
- Frequent GC.
- OOM kills.
- Cache eviction spikes.

Actions:

- Profile heap and allocation.
- Reduce object churn.
- Stream large payloads.
- Bound queues and caches.
- Use pagination and projection.
- Tune GC after fixing allocation patterns.

### Database Bound

Symptoms:

- Slow query p95/p99.
- Lock waits.
- High connection usage.
- Buffer cache misses.
- Replication lag.

Actions:

- Inspect execution plans.
- Add or adjust indexes.
- Reduce query fanout.
- Avoid N+1 queries.
- Tune transaction scope.
- Partition or shard by access pattern.
- Add read replicas only if read scaling is the bottleneck.

### Queue Bound

Symptoms:

- Consumer lag grows.
- Processing latency increases.
- DLQ rate spikes.
- Rebalancing or partition skew.

Actions:

- Increase consumer parallelism within partition limits.
- Fix slow consumer logic.
- Repartition by better key.
- Add back-pressure to producers.
- Separate hot event types.
- Use retry topics with delay instead of tight retry loops.

### Network Bound

Symptoms:

- High egress.
- Packet loss/retransmits.
- Large payload latency.
- Cross-region calls dominate.

Actions:

- Co-locate services.
- Compress where useful.
- Reduce payload size.
- Cache near users.
- Avoid synchronous cross-region calls.
- Use CDN and object storage for large media.

## Tail Latency Deep Dive

Tail latency gets worse when:

- One request fans out to many services.
- Dependencies have correlated load spikes.
- GC pauses or compaction pauses occur.
- Queues grow near saturation.
- Retries multiply traffic.
- Hot partitions overload one shard.

Mitigations:

- Timeouts, circuit breakers, and bulkheads.
- Hedged requests for idempotent reads.
- Request collapsing and caching.
- Precomputed read models.
- Adaptive concurrency limits.
- Load shedding for non-critical work.
- Priority queues for critical traffic.
- Partition rebalancing and hot-key mitigation.

## JVM Performance Checklist

- Allocation rate and live-set size.
- GC algorithm and pause target.
- Thread pool sizing and queue bounds.
- Lock contention and blocked threads.
- Virtual thread suitability.
- JIT warmup and code cache.
- HTTP client connection pooling.
- Serialization overhead.
- Logging volume and synchronous appenders.
- Database connection pool saturation.

## Kubernetes Capacity Checklist

- Requests and limits based on measured usage.
- HPA signal: CPU, memory, RPS, queue depth, Kafka lag, custom SLO metric.
- Pod startup and warmup time.
- Readiness gate for dependency health.
- Pod disruption budget.
- Node bin packing and resource fragmentation.
- Cluster autoscaler behavior.
- Multi-zone spread and failover capacity.
- Load balancer connection draining.
- Cost per replica and idle headroom.

## Performance Interview Questions

1. A service has 100 ms p50 and 4 second p99 latency. How do you debug it?
2. How do you design a capacity model for a notification system?
3. How do you size Kafka partitions for 1 million events/sec?
4. Why can adding retries make an outage worse?
5. How do you choose between caching, indexing, sharding, and denormalization?
6. How do you load test a payment system without corrupting state?
7. How do you handle p99 latency in a service that fans out to 20 dependencies?
8. How do you design autoscaling for queue consumers?
9. What metrics prove a database is CPU-bound vs lock-bound vs I/O-bound?
10. How do you estimate cost per request?

## Capstone Lab

Take one service from the commerce capstone and produce:

- Capacity model.
- Latency budget.
- Load test script.
- Baseline report.
- Flame graph or profiler output.
- Bottleneck analysis.
- Optimization change.
- Before/after metrics.
- Scaling policy.
- Cost estimate.

## Official Reference Anchors

- Google SRE Service Level Objectives: https://sre.google/sre-book/service-level-objectives/
- Google SRE Production Services Best Practices: https://sre.google/sre-book/service-best-practices/

