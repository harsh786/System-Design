# System Design Problems - Staff Engineer / Architect Level

## Target Level: Staff Engineer (L6) / Principal / Architect
These problems test end-to-end system design thinking with Spring Boot/WebFlux as the implementation technology. Focus on trade-offs, scalability reasoning, failure modes, and production readiness.

---

## Problem 1: Design a Distributed Rate Limiter Service

**Scenario:** Your organization has 200+ microservices. You need a centralized rate limiting service that:
- Supports per-user, per-API, per-tenant rate limiting
- Handles 500K requests/sec for rate limit checks
- Must add <2ms p99 latency to the request path
- Supports multiple algorithms (token bucket, sliding window, fixed window)
- Must work across multiple data centers

**Design Requirements:**
1. How would you architect the rate limiter as a Spring Boot service?
2. Where does the rate limiter sit in the request path (sidecar vs centralized)?
3. How do you handle the Redis/storage layer for distributed counting?
4. What happens when the rate limiter itself is down?
5. How do you handle clock skew across data centers?

**Expected Discussion Points:**
```
Architecture Options:
  A. Centralized service (all requests go through)
     - Pro: Single source of truth
     - Con: Single point of failure, added network hop

  B. Sidecar/Library approach (embedded in each service)
     - Pro: No network hop for check, resilient
     - Con: Approximate (local counts), hard to update

  C. Hybrid (local + sync to central)
     - Pro: Low latency + eventual accuracy
     - Con: Complexity, temporary over-limit allowance

Data Store Considerations:
  - Redis with Lua scripts (atomic operations)
  - Redis Cluster for partitioning across keys
  - Local cache with periodic sync (eventual consistency)

Spring Boot Implementation Considerations:
  - WebFlux for non-blocking rate limit checks
  - ReactiveRedisTemplate for async Redis access
  - Spring Cloud Gateway integration (GlobalFilter)
  - Circuit breaker around rate limiter (fail-open vs fail-closed)
  - Metrics: Micrometer counters for rate limit hits/misses
```

**Follow-up Questions:**
- How would you handle a burst of traffic from a single user during failover?
- How do you version rate limit policies without downtime?
- How would you implement a "warm-up" period for new services?

---

## Problem 2: Design a Real-Time Notification System

**Scenario:** Build a notification platform that:
- Sends notifications via push, email, SMS, in-app
- Handles 10M users, 1B notifications/day
- Supports real-time delivery (in-app via WebSocket/SSE)
- Users can configure preferences (channels, quiet hours, frequency caps)
- Must guarantee at-least-once delivery
- Needs priority levels (critical alerts > marketing)

**Design Requirements:**
1. How would you design the ingestion layer for notification requests?
2. How would you route notifications to the correct channel?
3. How would you handle the real-time WebSocket connections at scale?
4. How do you handle delivery failures and retries?
5. How would you implement user preference evaluation?

**Expected Architecture:**
```
┌──────────────────────────────────────────────────────────────┐
│                  NOTIFICATION PLATFORM                         │
│                                                               │
│  ┌─────────────┐     ┌─────────────────────────────────────┐│
│  │ Ingestion   │     │  Processing Pipeline                 ││
│  │ API (WebFlux)│────→│                                     ││
│  │ 50K rps     │     │  ┌──────────┐   ┌───────────────┐  ││
│  └─────────────┘     │  │ Priority │   │ Preference    │  ││
│                       │  │ Queue    │──→│ Evaluator     │  ││
│  Kafka Topics:        │  │ (Kafka)  │   │ (Dedupe, Cap) │  ││
│  - critical (P0)      │  └──────────┘   └───────┬───────┘  ││
│  - high (P1)          │                          │          ││
│  - normal (P2)        │         ┌────────────────┼────────┐ ││
│  - bulk (P3)          │         │                │        │ ││
│                       │         ▼                ▼        ▼ ││
│                       │  ┌──────────┐ ┌──────────┐ ┌─────┐ ││
│                       │  │Push (FCM)│ │Email     │ │SMS  │ ││
│                       │  │WebSocket │ │(SendGrid)│ │     │ ││
│                       │  └──────────┘ └──────────┘ └─────┘ ││
│                       └─────────────────────────────────────┘│
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ WebSocket Gateway (WebFlux + Netty)                      │ │
│  │ - 10M persistent connections                             │ │
│  │ - Redis Pub/Sub for cross-instance delivery              │ │
│  │ - Connection registry in Redis                           │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

**Key Spring Boot/WebFlux Decisions:**
- Why WebFlux for the WebSocket gateway? (Event loop handles 100K+ connections per node)
- How to scale WebSocket nodes? (Redis Pub/Sub for routing messages to correct node)
- How to handle reconnections? (Client-side exponential backoff, server-side connection registry TTL)
- Kafka consumer group configuration for priority processing
- Outbox pattern for guaranteed notification creation

**Follow-up Questions:**
- How would you implement notification batching (digest mode)?
- How do you prevent notification storms (e.g., cascading alerts)?
- How would you support multi-region deployment with regional compliance?

---

## Problem 3: Design an API Gateway from Scratch

**Scenario:** Your organization is unhappy with off-the-shelf API gateways. Design a custom one using Spring Cloud Gateway (WebFlux-based) that:
- Routes traffic to 300+ backend services
- Handles 200K requests/sec
- Supports dynamic route configuration (no redeploy)
- Implements authentication, rate limiting, request transformation
- Provides real-time analytics and logging
- Must have <5ms overhead per request (p99)

**Design Requirements:**
1. How would you structure the filter chain for minimal latency?
2. How do you handle dynamic route updates without restart?
3. How do you manage filter ordering and dependencies?
4. How do you handle large request/response bodies (streaming)?
5. How would you implement canary deployments through the gateway?

**Key Architectural Decisions:**
```
Filter Chain Design (ORDER MATTERS for latency):
  1. RequestId injection (~0.01ms)
  2. Rate Limiting (Redis Lua, ~0.5ms)
  3. Authentication (JWT validation, ~0.1ms cached)
  4. Route Resolution (trie-based, ~0.01ms)
  5. Request Transformation (~0.1ms)
  6. Load Balancing (weighted round-robin)
  7. Circuit Breaking (Resilience4j)
  8. Proxy to backend
  9. Response Transformation
  10. Metrics/Logging (async, ~0ms on hot path)

Dynamic Configuration:
  - Store routes in database/config service
  - Poll or event-driven refresh (Spring Cloud Bus)
  - Atomic swap of route definitions
  - Version routes for rollback capability
```

**Follow-up Questions:**
- How would you implement request coalescing (deduplication of identical concurrent requests)?
- How do you handle WebSocket proxying with connection state?
- How would you implement shadow traffic (duplicate requests to test environment)?

---

## Problem 4: Design a Job Scheduling Platform

**Scenario:** Build a distributed job scheduling platform that:
- Schedules and executes 100K+ jobs/day across 50 services
- Supports cron, one-time, and event-triggered jobs
- Guarantees exactly-once execution (even during failures)
- Provides job dependency graphs (Job B runs after Job A completes)
- Must handle job execution times from 100ms to 6 hours
- Needs retry policies, dead-letter handling, and alerting

**Design Requirements:**
1. How do you ensure exactly-once execution in a distributed environment?
2. How do you handle long-running jobs vs short jobs differently?
3. How do you implement job dependency resolution?
4. What happens when a worker node dies mid-execution?
5. How do you handle backpressure when too many jobs are scheduled?

**Expected Architecture:**
```
Components:
  1. Scheduler Service (Spring Boot)
     - Evaluates cron expressions
     - Manages job state machine (PENDING → RUNNING → SUCCESS/FAILED)
     - Leader election for scheduler (single writer)

  2. Job Queue (Kafka / Redis Streams)
     - Partitioned by job priority
     - Visibility timeout for at-least-once
     - Consumer groups for parallel execution

  3. Worker Service (Spring Boot)
     - Pulls jobs from queue
     - Heartbeat mechanism (I'm still alive)
     - Graceful shutdown (finish current job)

  4. Job Registry (Database)
     - Job definitions, schedules, dependencies
     - Execution history, audit trail
     - Distributed lock for exactly-once

State Machine:
  CREATED → SCHEDULED → QUEUED → RUNNING → SUCCESS
                                       → FAILED → RETRY → QUEUED
                                       → TIMEOUT → RETRY/DEAD_LETTER
```

**Follow-up Questions:**
- How would you implement job priority preemption?
- How do you handle time-zone-aware cron scheduling across regions?
- How would you implement job execution quotas per team/tenant?

---

## Problem 5: Design a Feature Flag Platform

**Scenario:** Build a feature flag service for your organization that:
- Serves 1M flag evaluations/sec with <1ms p99
- Supports targeting rules (user segments, percentages, geo)
- Provides real-time flag updates to all services (no cache staleness)
- Maintains audit trail of all changes
- Supports gradual rollouts with automatic rollback on metrics degradation

**Design Requirements:**
1. How do you achieve <1ms evaluation latency at 1M rps?
2. How do you propagate flag changes in real-time to all services?
3. How do you implement consistent percentage rollouts (same user always gets same variant)?
4. How would you implement automatic rollback based on error rate metrics?
5. How do you handle the SDK vs API trade-off for flag evaluation?

**Key Design Decisions:**
```
Evaluation Approaches:
  A. Server-side API (every evaluation = network call)
     - Pro: Always fresh, central control
     - Con: Added latency, SPOF

  B. SDK with local cache (poll for updates)
     - Pro: <1ms evaluation, resilient
     - Con: Stale during poll interval

  C. SDK with streaming updates (SSE/WebSocket)
     - Pro: Near-real-time updates, fast evaluation
     - Con: Connection management complexity

  Recommended: C (SDK with SSE streaming from Spring WebFlux backend)

Consistent Hashing for Percentage Rollouts:
  hash(flagKey + userId) % 100 < rolloutPercentage
  - Deterministic: same user always gets same result
  - Gradually increasing percentage doesn't re-randomize existing users
```

**Follow-up Questions:**
- How would you handle flags that depend on other flags (flag composition)?
- How do you implement emergency kill switches that bypass all caching?
- How would you design the admin UI for non-technical product managers?

---

## Problem 6: Design a Multi-Region Active-Active System

**Scenario:** You need to make an existing Spring Boot e-commerce platform active-active across 3 regions (US-East, EU-West, AP-Southeast) with:
- Users routed to nearest region
- Writes propagated across regions (eventual consistency acceptable for most data)
- Strong consistency for inventory/payment (cannot oversell)
- Sub-100ms read latency, sub-500ms write latency
- Graceful degradation if one region is down

**Design Requirements:**
1. How do you handle data replication across regions?
2. How do you maintain consistency for inventory without global locks?
3. How do you route users and handle region failover?
4. How do you handle conflicting writes (same item edited in 2 regions)?
5. What Spring Boot configurations change for multi-region?

**Expected Discussion Points:**
```
Data Classification:
  1. REGIONAL (user profiles, sessions, carts)
     - Master in user's home region
     - Async replicate to others (CRDTs or last-write-wins)

  2. GLOBAL-CONSISTENT (inventory, payments, orders)
     - Single global primary OR
     - Reservation-based (reserve locally, confirm globally)

  3. REFERENCE (product catalog, configs)
     - Read replicas everywhere
     - Write from single admin region

Conflict Resolution Strategies:
  - Last-Write-Wins (LWW) with vector clocks
  - CRDTs (Conflict-free Replicated Data Types)
  - Application-level merge (custom resolution logic)
  - Reservation pattern (pre-allocate inventory per region)

Spring Boot Considerations:
  - R2DBC with read replica routing per region
  - Kafka MirrorMaker for cross-region event replication
  - Spring Cloud Gateway per-region with geo-DNS routing
  - Resilience4j circuit breakers for cross-region calls
  - Distributed tracing spanning regions (correlation IDs)
```

**Follow-up Questions:**
- How would you handle a "split-brain" scenario where regions can't communicate?
- How do you test multi-region failover?
- How would you handle GDPR data residency requirements?

---

## Problem 7: Design a Real-Time Analytics Pipeline

**Scenario:** Build a real-time analytics service that:
- Ingests 2M events/sec from 200 microservices
- Computes real-time dashboards (count, sum, avg, percentiles over sliding windows)
- Supports ad-hoc queries on recent data (last 24 hours)
- Must show results within 5 seconds of event occurrence
- Historical data (older than 24h) goes to data lake

**Design Requirements:**
1. How do you design the event ingestion layer to handle 2M events/sec?
2. How do you compute sliding window aggregations in real-time?
3. How do you expose the analytics via API without overwhelming the computation layer?
4. How do you handle late-arriving events?
5. How do you backfill when computation logic changes?

**Expected Architecture:**
```
┌───────────────────────────────────────────────────────────┐
│  Event Producers (200 microservices)                       │
│  - Async event emission via Kafka producer               │
│  - Event schema registry (Avro/Protobuf)                 │
└────────────────────┬──────────────────────────────────────┘
                     │
                     ▼
┌───────────────────────────────────────────────────────────┐
│  Kafka (partitioned by event type + service)              │
│  - 500 partitions across 30 brokers                      │
│  - 24h retention for reprocessing                        │
└────────────────────┬──────────────────────────────────────┘
                     │
        ┌────────────┼────────────────┐
        │            │                │
        ▼            ▼                ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│ Stream Proc  │ │ Archiver │ │ Spring Boot  │
│ (Kafka       │ │ (S3/Lake)│ │ Query API    │
│  Streams /   │ │          │ │ (WebFlux)    │
│  Flink)      │ └──────────┘ └──────────────┘
│              │                      ▲
│ Windowed     │                      │
│ Aggregations │──→ Redis TimeSeries──┘
│ (5s, 1m, 1h) │
└──────────────┘
```

**Spring Boot Specific Considerations:**
- Kafka Streams embedded in Spring Boot for stream processing
- WebFlux SSE endpoint for real-time dashboard push
- R2DBC + Redis for serving pre-computed aggregations
- Custom Micrometer metrics for pipeline health
- Schema evolution handling with Confluent Schema Registry

---

## Problem 8: Design a Configuration Management Platform

**Scenario:** Your 300-service organization needs a centralized configuration platform that:
- Serves 100K config reads/sec
- Supports hierarchical configs (global → team → service → environment → instance)
- Real-time config propagation (<5 seconds to all instances)
- Audit trail for all changes
- Secret management integrated
- Supports config validation before apply
- Canary config deployments (apply to 1% first)

**Design Requirements:**
1. How would you design the hierarchy resolution for O(1) lookup?
2. How do you propagate changes in real-time to 1000+ service instances?
3. How do you implement canary config deployments?
4. How do you handle config rollback?
5. How do you validate configs before they're applied?

**Key Design Decisions:**
```
Hierarchy Resolution (inheritance):
  global.database.pool-size = 10
  team-payments.database.pool-size = 20
  payment-service.database.pool-size = 30    ← WINS (most specific)

  Pre-compute resolved configs per service/env → O(1) lookup
  On any change → recompute affected resolved configs
  Store resolved version in Redis for serving

Real-time Propagation Options:
  A. Polling (Spring Cloud Config refresh)
     - Simple, but up to poll-interval delay
  
  B. Push via Spring Cloud Bus (RabbitMQ/Kafka)
     - Near real-time, all instances get RefreshEvent
  
  C. SSE/WebSocket streaming from config service
     - Immediate, persistent connection needed

  Recommended: B for most services + C for critical services

Spring Boot Integration:
  - @RefreshScope for live config updates
  - EnvironmentChangeEvent listeners
  - Custom PropertySource that connects to config platform
  - Spring Cloud Config Server as the backbone
```

**Follow-up Questions:**
- How do you handle config dependencies (changing DB URL requires connection pool restart)?
- How do you prevent bad configs from causing cascading outages?
- How would you implement config-as-code with GitOps workflow?

---

## Problem 9: Design a Service Mesh Control Plane

**Scenario:** You're building a lightweight service mesh control plane using Spring Boot that:
- Manages service discovery for 500 services (5000 instances)
- Pushes routing rules to sidecar proxies in real-time
- Implements traffic splitting (canary, blue-green, A/B)
- Provides circuit breaking configuration
- Supports mTLS certificate rotation
- Must recover from control plane outages without data plane impact

**Design Requirements:**
1. How do you design the control plane for high availability?
2. How do you push configuration to 5000 sidecar proxies efficiently?
3. How do you handle control plane failure without affecting running services?
4. How do you implement traffic splitting without application code changes?
5. How do you manage certificate rotation for 5000 instances?

---

## Problem 10: Design an Event-Driven Order Processing System

**Scenario:** A large retailer needs a new order processing system:
- 50K orders/minute at peak (Black Friday)
- Each order involves: payment, inventory, shipping, notification
- Must handle partial failures (payment succeeds, inventory fails)
- Requires compensation logic (refund if later steps fail)
- Must support order status tracking in real-time
- 99.99% order completion SLA

**Design Requirements:**
1. Saga pattern: orchestration vs choreography - which and why?
2. How do you handle the "double-spend" problem?
3. How do you implement real-time order status to customers?
4. How do you handle the 10x traffic spike on Black Friday?
5. How do you debug a failed order across 5 services?

**Expected Discussion Points:**
```
Saga Orchestration (recommended for complex flows):
  OrderOrchestrator (Spring Boot):
    1. Create order (PENDING)
    2. Reserve inventory → success/compensate
    3. Process payment → success/compensate
    4. Schedule shipping → success/compensate
    5. Send notification
    6. Complete order (SUCCESS)

  On failure at step 3:
    - Compensate step 2 (release inventory)
    - Mark order FAILED
    - Notify customer

Implementation with Spring:
  - Spring State Machine for order lifecycle
  - Kafka for inter-service communication
  - Outbox pattern for reliable event publishing
  - Idempotency keys on each step
  - Distributed tracing (Sleuth/Micrometer Tracing)

Scaling for Black Friday:
  - Pre-warm: Start extra instances before peak
  - Kafka partitions scaled up
  - Queue-based decoupling absorbs burst
  - Rate limit non-critical paths (notifications can be delayed)
  - Inventory pre-allocated to regions
```

**Follow-up Questions:**
- How do you handle an order stuck in PENDING for 30 minutes?
- How would you implement order amendment after placement?
- How do you replay failed events without duplicating effects?
