# Staff Engineer & Architect - System Design & Distributed Systems

> Questions and concepts asked at Staff/Principal Engineer and Solution Architect level.
> Focus: Trade-offs, scalability decisions, failure modes, organizational impact.

---

## 1. Distributed Systems Fundamentals

### CAP Theorem
- **Consistency:** Every read receives the most recent write
- **Availability:** Every request receives a response (no guarantee it's the latest)
- **Partition Tolerance:** System continues operating despite network partitions
- **Reality:** Network partitions WILL happen → choose CP or AP
- **AWS Examples:**
  - CP: DynamoDB with strongly consistent reads (sacrifices some availability)
  - AP: DynamoDB with eventually consistent reads (default), S3, ElastiCache
  - CA: Single-node RDS (no partition = no tolerance needed)

### PACELC Theorem (Extension of CAP)
- If Partition → choose Availability or Consistency
- Else (no partition) → choose Latency or Consistency
- **DynamoDB:** PA/EL (partition → available, else → low latency with eventual consistency)
- **Aurora:** PC/EC (partition → consistent, else → consistent but higher latency)

### Consistency Models
| Model | Description | AWS Example |
|-------|-------------|-------------|
| Strong | Read always returns latest write | Aurora writer, DynamoDB consistent read |
| Eventual | Reads may return stale data temporarily | DynamoDB default, S3, ElastiCache replica |
| Causal | Preserves cause-effect order | DynamoDB Streams |
| Read-your-writes | Your writes visible to your reads immediately | Session-based caching |

### Consensus Algorithms
- **Raft:** Used by etcd (Kubernetes), Consul. Leader election + log replication
- **Paxos:** Theoretical foundation. Used by Google Spanner
- **AWS implementation:** Aurora uses quorum-based replication (4/6 writes, 3/6 reads)

---

## 2. Scalability Patterns

### Horizontal vs Vertical Scaling Decision
- **Vertical first when:** Database (up to a point), legacy monolith, early stage
- **Horizontal when:** Stateless services, read-heavy (replicas), need fault tolerance
- **Staff-level insight:** Vertical scaling has diminishing returns AND increases blast radius. Horizontal adds complexity but improves resilience

### Database Scaling Strategies
```
Read Scaling:
  Read Replicas → Cache layer (Redis) → CDN caching → CQRS (separate read model)

Write Scaling:
  Vertical → Write-behind cache → Sharding → Event Sourcing → Multi-region active-active
```

### Sharding Strategies
- **Range-based:** Easy range queries, risk of hot partitions (user A-M on shard 1)
- **Hash-based:** Even distribution, no range queries (DynamoDB approach)
- **Directory-based:** Lookup table maps entity → shard. Flexible but single point of failure
- **Consistent hashing:** Minimize reshuffling when adding/removing nodes (ElastiCache, Cassandra)

**Staff-level question:** "How would you handle cross-shard queries and transactions?"
- **Answer:** Avoid where possible (design for partition-local queries). When needed: saga pattern, two-phase commit (expensive), materialized views across shards, or CQRS with denormalized read model

### Back-Pressure Patterns
- **Problem:** Producer faster than consumer → queue grows unbounded → OOM
- **Solutions:**
  - Bounded queues (SQS MaxReceiveCount → DLQ)
  - Rate limiting at ingress (API Gateway throttling)
  - Load shedding (reject requests above capacity, return 503)
  - Circuit breaker (stop calling overwhelmed downstream)
  - Adaptive concurrency limits (Netflix concurrency-limits library)

---

## 3. Event-Driven Architecture (Advanced)

### Event Sourcing
- **What:** Store state changes as immutable events (not current state)
- **Event Store:** Append-only log (Kinesis, DynamoDB Streams, Kafka)
- **Current state:** Replay events from beginning or from snapshot
- **Benefits:** Complete audit trail, temporal queries, rebuild state from any point
- **Challenges:** Event schema evolution, eventual consistency, complexity
- **AWS:** DynamoDB + Streams + Lambda projections, or Kinesis + DynamoDB

### CQRS (Command Query Responsibility Segregation)
- **Separate:** Write model (command side) from Read model (query side)
- **Write:** Optimized for transactions (normalized, RDS/DynamoDB)
- **Read:** Optimized for queries (denormalized, ElastiCache/OpenSearch/Redshift)
- **Sync:** DynamoDB Streams/Kinesis → Lambda → update read store
- **When to use:** Different read/write patterns, complex queries on write-optimized store, independent scaling

### Saga Pattern (Distributed Transactions)
- **Problem:** Transaction across multiple services (order + payment + inventory)
- **Choreography:** Each service publishes events, next service reacts. Simple but hard to track
- **Orchestration:** Central coordinator (Step Functions) manages flow. Explicit but single point
- **Compensation:** Each step has compensating action (refund payment if inventory fails)
- **AWS:** Step Functions (orchestration), EventBridge + Lambda (choreography)

```
Order Service → Payment Service → Inventory Service
     ↑ (compensate)      ↑ (refund)        ↑ (restock)
     └─────────────────── ← failure detected ←──────┘
```

### Exactly-Once Processing
- **Reality:** Exactly-once is impossible in distributed systems. Use "effectively-once"
- **Approaches:**
  - Idempotent consumers (processing same message twice produces same result)
  - Deduplication (idempotency key in DynamoDB/Redis, check before processing)
  - Transactional outbox (write event + state change in same DB transaction)
- **SQS:** Exactly-once delivery (FIFO), at-least-once (standard). Consumer must be idempotent regardless
- **Kinesis:** At-least-once. Use checkpointing + idempotent handlers

---

## 4. Reliability & Resilience Patterns

### Failure Modes and Mitigations
| Failure | Impact | Mitigation |
|---------|--------|------------|
| Single instance | One user affected | Auto Scaling, health checks |
| AZ failure | 33% capacity loss | Multi-AZ deployment, AZ-independent design |
| Region failure | Full outage | Multi-region active-active, Route 53 failover |
| Service failure | Feature degraded | Circuit breaker, fallback, graceful degradation |
| Database corruption | Data loss | Point-in-time recovery, cross-region backups |
| DNS failure | All traffic lost | Multiple DNS providers, low TTLs |
| Deployment failure | Degraded service | Canary, rollback automation, feature flags |

### Bulkhead Pattern
- **Concept:** Isolate components so failure in one doesn't cascade
- **Implementation:**
  - Separate connection pools per downstream service
  - Separate thread pools (Hystrix-style)
  - Separate ECS services (not all microservices in one service)
  - Separate AWS accounts per blast radius boundary
- **AWS:** Separate VPCs, separate accounts, resource-level isolation

### Thundering Herd Prevention
- **Problem:** Cache expires → all requests hit DB simultaneously
- **Solutions:**
  - Cache stampede lock (only one request refreshes cache, others wait)
  - Staggered TTLs (add jitter to expiry: TTL + random(0, 60s))
  - Background refresh (refresh cache before expiry asynchronously)
  - Request coalescing (deduplicate identical in-flight requests)
- **AWS:** ElastiCache with lazy-loading + jittered TTL, CloudFront Origin Shield (coalesces requests)

### Retry Strategy Design
```
Level 1: Immediate retry (network blip) - 0ms delay
Level 2: Exponential backoff - 100ms, 200ms, 400ms, 800ms...
Level 3: Jitter - backoff * random(0.5, 1.5) to prevent synchronized retries
Level 4: Circuit breaker - stop retrying after threshold (fail fast)
Level 5: Dead letter queue - capture permanently failed for manual handling
```
- **Idempotency key:** Client generates UUID per request. Server checks before processing
- **Staff insight:** Always have a maximum retry limit + exponential backoff + jitter. Without jitter, correlated retries cause cascading failures

### Graceful Degradation
- **Philosophy:** Better to serve partial/stale data than error
- **Techniques:**
  - Return cached data when service down (serve stale)
  - Disable non-critical features under load
  - Reduce functionality (read-only mode when writes failing)
  - Static fallback content
- **Example:** Product page: price service down → show "Price unavailable" instead of 500. Recommendation service down → show generic bestsellers

---

## 5. Multi-Account & Landing Zone Architecture

### AWS Multi-Account Strategy
```
Organization Root
├── Security OU
│   ├── Log Archive Account (centralized logging)
│   ├── Security Tools Account (GuardDuty, SecurityHub, Inspector)
│   └── Audit Account (read-only cross-account access)
├── Infrastructure OU
│   ├── Network Account (Transit Gateway, Direct Connect, VPN)
│   ├── Shared Services Account (AD, DNS, artifact repos)
│   └── CI/CD Account (CodePipeline, GitHub Actions runners)
├── Workload OU
│   ├── Dev OU
│   │   ├── Team-A Dev Account
│   │   └── Team-B Dev Account
│   ├── Staging OU
│   │   └── Staging Account
│   └── Production OU
│       ├── Prod Account (primary)
│       └── Prod DR Account (secondary region)
└── Sandbox OU
    └── Individual sandbox accounts
```

### Why Multi-Account?
- **Blast radius:** Misconfiguration in dev can't affect prod
- **Security boundary:** IAM is account-level isolation (strongest boundary)
- **Billing:** Per-team/project cost allocation
- **Quotas:** Service limits per account (DynamoDB, Lambda concurrency)
- **Compliance:** Separate regulated workloads (PCI, HIPAA)

### Control Tower & Landing Zone
- **Control Tower:** Automated landing zone setup with guardrails
- **Guardrails:** Preventive (SCP-based, block actions) + Detective (Config Rules, detect drift)
- **Account Factory:** Standardized account provisioning (networking, logging, security baseline)
- **Customizations for Control Tower (CfCT):** Custom resources deployed to every new account

### Cross-Account Patterns (Staff-level)
- **Centralized logging:** All accounts → CloudWatch Logs → Kinesis → S3 in Log Archive account
- **Network hub:** Transit Gateway in Network account, shared with all via RAM
- **CI/CD:** Pipelines in CI/CD account, deploy to workload accounts via cross-account roles
- **Security:** GuardDuty delegated admin, Security Hub aggregation, Config aggregator

---

## 6. Cost Architecture (FinOps)

### Cost Optimization Framework
1. **Right-size:** Compute Optimizer, CloudWatch, Trusted Advisor (continuous)
2. **Pricing models:** Savings Plans/RI for steady-state (60%+ savings)
3. **Architecture:** Serverless for variable, spot for fault-tolerant, ARM/Graviton
4. **Waste elimination:** Unused resources, idle environments, over-provisioned storage
5. **Data transfer:** VPC endpoints, same-AZ affinity, compression, CDN offload

### Cost at Scale (Staff/Architect decisions)
- **NAT Gateway:** $0.045/GB. At 100 TB/month = $4,500. Solution: VPC endpoints ($7.20/endpoint/month)
- **Data transfer between AZs:** $0.01/GB each way. Design for AZ-local where possible
- **CloudWatch Logs:** $0.50/GB ingestion. At scale: Fluent Bit → S3 directly ($0.023/GB) + Athena
- **EBS Snapshots:** Incremental but accumulate. Lifecycle policies critical at 1000s of snapshots
- **Load Balancer idle:** $16/month minimum. Consolidate non-prod behind single ALB

### FinOps for Architects
- **Unit economics:** Cost per transaction, cost per user, cost per API call (not just total bill)
- **Showback/Chargeback:** Tag strategy → Cost Allocation Tags → per-team reports
- **Anomaly detection:** AWS Cost Anomaly Detection + custom alerts
- **Budget governance:** AWS Budgets with actions (auto-apply SCP when budget exceeded)
- **Architecture reviews:** Include cost estimation. "What does this cost at 10x scale?"

---

## 7. Security Architecture

### Zero Trust Architecture on AWS
- **Principle:** Never trust, always verify. Regardless of network location
- **Implementation:**
  - Every service-to-service call authenticated (mTLS via service mesh)
  - Fine-grained authorization (RBAC + ABAC, not network-based)
  - Micro-segmentation (network policies, security groups per service)
  - Encrypt everything (in-transit + at-rest)
  - Continuous verification (not just at perimeter)
- **AWS tools:** App Mesh (mTLS), IAM (identity-based), VPC Lattice, Verified Access

### Threat Modeling for Cloud
- **STRIDE model:** Spoofing, Tampering, Repudiation, Information Disclosure, DoS, Elevation of Privilege
- **AWS attack surfaces:**
  - Public endpoints (API Gateway, ALB, CloudFront)
  - IAM misconfiguration (overly permissive roles)
  - Data exposure (public S3, unencrypted EBS)
  - Supply chain (compromised dependencies, container images)
  - Lateral movement (SSRF via IMDSv1, shared VPC)
- **Mitigation layers:** WAF → Shield → SG → NACL → IAM → Encryption → Monitoring

### Data Classification & Encryption Strategy
```
Classification → Encryption → Access Control → Monitoring
Public         → Optional     → Open           → Basic
Internal       → In-transit   → IAM-based      → CloudTrail
Confidential   → At-rest+transit → Least privilege → Enhanced
Restricted     → CMK per dataset → Need-to-know  → Real-time alerts
```

- **KMS strategy:** One CMK per data classification per service per environment
- **Key rotation:** Automatic annual rotation for KMS. Custom rotation for Secrets Manager
- **Envelope encryption:** Data key encrypts data, CMK encrypts data key (performance + security)

---

## 8. Platform Engineering

### Internal Developer Platform (IDP) Design
- **What:** Self-service platform enabling developers to deploy without infrastructure knowledge
- **Components:**
  - Service catalog (golden paths for common workloads)
  - CI/CD templates (standardized pipelines)
  - Infrastructure provisioning (Terraform modules, CDK constructs)
  - Observability (pre-configured dashboards, alerting)
  - Documentation (runbooks, architecture decision records)

### Platform Team Responsibilities
- Provide paved roads (not gates)
- Abstract infrastructure complexity
- Enforce security/compliance transparently
- Measure developer productivity (DORA metrics)
- Build reusable modules/templates

### Golden Path Example (EKS Service)
```
Developer provides:
  - Dockerfile
  - Service name
  - Resource requirements (CPU/memory)
  - Port
  - Health check endpoint

Platform provides (automatically):
  - EKS namespace
  - Deployment, Service, Ingress
  - CI/CD pipeline (build, test, deploy)
  - Monitoring (dashboards, alerts, SLOs)
  - Logging (structured, aggregated)
  - Networking (service mesh, DNS)
  - Security (IRSA, network policies, pod security)
  - Scaling (HPA configured)
```

### Developer Experience Metrics
- **DORA Metrics:**
  - Deployment frequency (how often you deploy to production)
  - Lead time for changes (commit to production)
  - Mean time to recovery (MTTR)
  - Change failure rate (% deployments causing failure)
- **Elite performers:** Multiple deploys/day, <1 hour lead time, <1 hour MTTR, <15% failure rate
- **Platform metrics:** Time to first deploy, onboarding time, self-service success rate

---

## 9. Architectural Decision Making

### Architecture Decision Records (ADR)
```markdown
# ADR-001: Use EKS over ECS for container orchestration

## Status: Accepted

## Context
We need container orchestration for 50+ microservices across 3 teams.
Requirements: multi-cloud portability, advanced scheduling, team isolation.

## Decision
Use Amazon EKS with managed node groups and Karpenter for autoscaling.

## Consequences
- (+) Kubernetes portability, rich ecosystem, industry standard
- (+) Better multi-tenancy (namespaces, RBAC, network policies)
- (-) Higher operational complexity vs ECS
- (-) Steeper learning curve for teams
- (-) Higher cost for small clusters (EKS: $0.10/hr control plane)

## Alternatives Considered
- ECS Fargate: Simpler but less portable, limited scheduling
- Self-managed K8s: Too much operational burden
```

### Technology Selection Framework (Staff-level)
| Criteria | Weight | Questions to Ask |
|----------|--------|-----------------|
| Team capability | 25% | Can the team operate this? Training cost? |
| Operational cost | 20% | TCO over 3 years? Staffing needs? |
| Scalability | 15% | Does it scale to 10x? 100x? |
| Ecosystem | 15% | Community, tooling, hiring market? |
| Vendor lock-in | 10% | Exit cost? Multi-cloud strategy? |
| Time-to-market | 10% | How fast can we deliver with this? |
| Security | 5% | Compliance needs met? Audit trail? |

### Build vs Buy Decision
- **Build when:** Core differentiator, unique requirements, data sensitivity, team capacity
- **Buy when:** Commodity capability, faster time-to-market, limited team, well-solved problem
- **Staff insight:** Always calculate total cost of ownership (build = maintenance forever, buy = ongoing licensing + integration)

---

## 10. Staff/Architect Scenario Questions

### Q1: Design a system that handles 1 million concurrent WebSocket connections
**Answer:**
- **Challenge:** 1M connections × ~10KB memory = 10GB minimum. Single instance can't handle all
- **Architecture:**
  - ALB/NLB → Fleet of WebSocket servers (EC2 c5.4xlarge can handle ~100K connections each → 10+ instances)
  - Connection registry in Redis (connectionId → serverId mapping)
  - To broadcast: Publish to SNS/Redis Pub-Sub → all servers push to their connections
  - Use ElastiCache Redis Cluster for pub/sub (not SQS - too much latency)
- **Scaling:** Auto-scale server fleet. New connections load-balanced. Existing connections sticky
- **API Gateway WebSocket:** Manages connections, but at 1M scale might hit limits → custom solution
- **State:** DynamoDB for connection metadata, Redis for pub/sub + connection mapping

### Q2: Your microservices architecture has cascading failures. Design the resilience strategy
**Answer:**
- **Circuit Breaker:** Implement at service mesh level (App Mesh/Istio). Per-service thresholds:
  - Open circuit after 50% failure rate in 10-second window
  - Half-open: Allow 1 request every 5 seconds to test recovery
  - Close: 5 consecutive successes
- **Bulkhead:** Separate thread/connection pools per downstream dependency
  - If service-A fails, don't exhaust all connections (other services still work)
- **Timeout strategy:** 
  - Each service: 3s timeout for downstream calls
  - Total request budget: 10s (distributed across chain)
  - Timeout at edge (API Gateway) = sum of all expected latencies + buffer
- **Graceful degradation:** Each service defines fallback behavior
  - Recommendation service down → return empty recommendations (not 500)
  - Payment service down → queue order for later processing
- **Retry budget:** Max 3 retries with exponential backoff + jitter
  - Important: Don't retry on 4xx (client errors), only 5xx and timeouts
- **Load shedding:** Return 503 immediately when at capacity (better than slow failure)
- **Testing:** Regular chaos engineering (AWS FIS: terminate instances, block AZ, inject latency)

### Q3: Design data pipeline processing 10TB/day with exactly-once semantics
**Answer:**
- **Ingestion:** Kinesis Data Streams (or MSK/Kafka) for ordered, partitioned streaming
  - Partition by entity ID (all events for same entity on same shard)
- **Processing:** Kinesis → Lambda (or Flink on EMR) 
  - Deduplication: Write processed event IDs to DynamoDB with TTL
  - Idempotent writes: Use conditional writes (DynamoDB) or upserts
- **Exactly-once approach:**
  1. Consume message
  2. Check dedup table (DynamoDB: eventId exists?)
  3. Process + write output + write to dedup table (DynamoDB TransactWriteItems - atomic)
  4. Checkpoint Kinesis position AFTER successful processing
  5. If crash before checkpoint → replay → dedup catches duplicates
- **Storage:** Processed data → S3 (Parquet) for analytics, DynamoDB for serving
- **Scale:** 10TB/day = ~115 MB/s sustained. Kinesis: 12 shards (1MB/s each) with enhanced fan-out
- **Monitoring:** Iterator age (processing delay), error rate, DLQ depth

### Q4: You're asked to reduce overall system latency from p99 500ms to p99 100ms
**Answer:**
- **Measurement first:** Distributed tracing (X-Ray) to find where time is spent
- **Common latency sources and fixes:**
  | Source | Fix |
  |--------|-----|
  | Network hops | Co-locate services (same AZ), reduce service chain depth |
  | DNS resolution | Cache DNS, use IP-based discovery |
  | TLS handshake | Connection pooling, session resumption |
  | Cold starts (Lambda) | Provisioned concurrency, warm pools |
  | Database queries | Read replicas, caching (Redis), query optimization, connection pooling |
  | Serialization | Protocol Buffers/gRPC instead of JSON, compression |
  | Cross-AZ calls | AZ-aware routing (topology-aware hints in K8s) |
  | Large payloads | Pagination, field selection (GraphQL), compression |
- **Architecture changes:**
  - Add cache layer (Redis) for frequent queries → avoid DB round trip
  - Pre-compute expensive operations asynchronously
  - Move computation to edge (Lambda@Edge, CloudFront Functions)
  - Reduce serialization layers (gRPC between internal services)
- **Key insight:** p99 optimization requires eliminating tail latency. Often caused by GC pauses, cold caches, retries hitting slow replicas. Solution: hedged requests (send to 2 replicas, take first response)

### Q5: Design multi-region active-active architecture for a payment system
**Answer:**
- **Requirements:** Low latency globally, strong consistency for payments, survive region failure
- **Architecture:**
  ```
  Region A (us-east-1)          Region B (eu-west-1)
  ├── API Gateway + Lambda      ├── API Gateway + Lambda
  ├── EKS cluster               ├── EKS cluster  
  ├── Aurora Primary (writer)   ├── Aurora Secondary (read-local)
  ├── DynamoDB Global Table     ├── DynamoDB Global Table
  ├── ElastiCache Redis         ├── ElastiCache Redis
  └── SQS + processors         └── SQS + processors
  
  Route 53: Latency-based routing (users → nearest region)
  ```
- **Data strategy:**
  - Payment state: DynamoDB Global Tables (last-writer-wins, conflict resolution via version)
  - Financial records: Aurora Global Database (primary region for writes, <1s replication)
  - Idempotency keys: DynamoDB with conditional write (prevent double-charge across regions)
- **Conflict resolution for payments:**
  - Route ALL writes for same payment to same region (partition by payment_id hash → region)
  - OR: Use distributed lock (DynamoDB conditional write as lock)
  - OR: Event sourcing - accept all writes, resolve conflicts in order-processor
- **Failover:** Route 53 health check → automatic DNS failover in <60s
  - During failover: Queue payments in SQS → process when primary recovers (if Aurora write needed)
  - For DynamoDB: Both regions can write (truly active-active)

### Q6: Design a system that must comply with GDPR right-to-be-forgotten
**Answer:**
- **Data inventory:** Map all personal data across all services (data catalog)
- **Architecture principles:**
  - Data localization: EU data stays in EU (Aurora in eu-west-1)
  - Encryption with per-user key: Each user's data encrypted with their own data key
  - **Crypto-shredding:** Delete user's encryption key → data becomes unreadable without full deletion
- **Deletion strategy:**
  - Synchronous: API call → delete from all data stores (complex, fragile)
  - Event-driven: Publish "user-deletion-requested" event → each service handles independently
  - **Crypto-shredding (recommended):** All user data encrypted with user-specific key in KMS. To "forget" user → delete their KMS key → data unrecoverable
- **Challenges:**
  - Backups: Encrypted → crypto-shredding covers it
  - Logs: Don't log PII. If you must, use tokenization
  - Analytics: Anonymize before ETL (remove PII, keep aggregates)
  - Third parties: Track all data sharing, implement deletion API
- **Implementation:**
  ```
  User deletion request → Step Functions:
    1. Mark user as "pending deletion" (DynamoDB)
    2. Fan-out to all services (parallel Lambda invocations)
    3. Each service confirms deletion (callback)
    4. Delete KMS user key (crypto-shred all encrypted data)
    5. Record deletion certificate (compliance audit)
  ```

### Q7: The engineering team is growing from 10 to 100 engineers. Redesign the platform for scale
**Answer:**
- **Current state (10 eng):** Monorepo, shared infrastructure, everyone deploys
- **Target state (100 eng):** Platform team + product teams + clear boundaries
- **Organizational changes:**
  - Team Topologies: Stream-aligned teams (product features) + Platform team (infrastructure) + Enabling teams (help adoption)
  - Each team owns 2-3 services end-to-end (you build it, you run it)
- **Platform changes:**
  - Self-service infrastructure (Backstage/Port catalog, golden paths)
  - Standardized CI/CD (reusable workflows, consistent deployment)
  - Shared observability (centralized logging, distributed tracing, SLO dashboards)
  - Service mesh (mTLS, traffic management without application changes)
- **AWS account strategy:** 
  - Account per team per environment (Team-A-Dev, Team-A-Prod)
  - Shared services account (CI/CD, observability, base infrastructure)
  - Network account (Transit Gateway, shared VPCs)
- **Architecture evolution:**
  - Decompose monolith along team boundaries (DDD bounded contexts)
  - API contracts between teams (OpenAPI specs, contract testing)
  - Event bus for cross-team communication (reduce coupling)
  - Independent deployability (no coordinated releases)

### Q8: Design cache strategy for an e-commerce platform (product catalog, pricing, sessions)
**Answer:**
- **Multi-layer caching:**
  ```
  Browser Cache (static assets, 1 hour)
    ↓ miss
  CloudFront Edge (product images, CSS/JS, 24 hours)
    ↓ miss
  Application Cache - ElastiCache Redis Cluster
    ├── Product catalog (TTL: 5 min, lazy loading)
    ├── Pricing (TTL: 1 min, event-invalidation on price change)
    ├── User sessions (TTL: 30 min, write-through)
    └── Search results (TTL: 30 sec, cache-aside)
    ↓ miss
  Database (Aurora + DynamoDB)
  ```
- **Caching patterns per use case:**
  | Data | Pattern | TTL | Invalidation |
  |------|---------|-----|-------------|
  | Product info | Cache-aside (lazy) | 5 min | Event-driven (SNS on product update) |
  | Pricing | Write-through | 1 min | Immediate invalidation on change |
  | Sessions | Write-through | 30 min | Explicit delete on logout |
  | Cart | Write-through | 24 hours | User action |
  | Search results | Cache-aside | 30 sec | Short TTL (acceptable staleness) |
  | Inventory count | No cache | - | Always real-time (DynamoDB) |

- **Cache invalidation strategies:**
  - **TTL-based:** Simple, slight staleness acceptable (product descriptions)
  - **Event-driven:** Product service publishes change → Lambda invalidates Redis key (pricing)
  - **Write-through:** Every write updates cache AND database simultaneously (sessions)
  - **Cache-aside with refresh-ahead:** Background job refreshes popular items before TTL expires

- **Hot key mitigation:**
  - Problem: Flash sale → millions of requests for same product → single Redis node overloaded
  - Solution: Add random suffix to key (product:123:shard1, product:123:shard2) → read from random shard
  - Alternative: Local in-memory cache (Caffeine/Guava) with very short TTL (5s) → reduces Redis load by 95%

### Q9: Design a system for 99.999% availability (5-nines)
**Answer:**
- **Budget:** 5.26 minutes downtime per YEAR. No single point of failure allowed
- **Architecture requirements:**
  - Multi-region active-active (survive entire region failure)
  - Multi-AZ within each region
  - No shared-nothing single dependencies
  - Automated failover (no human in the loop)
- **Design:**
  ```
  Global: Route 53 (100% SLA) with health checks
  Per-region:
    - Multiple AZs with independent compute
    - Data: DynamoDB Global Tables (multi-region active-active)
    - Compute: EKS with Karpenter (auto-replace failed nodes in seconds)
    - Cache: Redis with Multi-AZ + cross-region read replicas
    - Queue: SQS (11 nines durability)
  ```
- **Key decisions:**
  - Use DynamoDB over Aurora (DynamoDB = multi-region active-active writes, Aurora = single writer)
  - Stateless compute only (all state in data layer)
  - Health checks at every layer (Route 53, ALB, pod readiness)
  - Retry with different region on failure (client-side)
- **Testing:** Monthly chaos engineering, canary deployments, game days
- **Monitoring:** Sub-second alerting, automated remediation for known failures
- **Reality check:** 5-nines is extremely expensive. Most systems need it only for specific flows (payment processing) not all features

### Q10: You notice DynamoDB costs are $50K/month and growing 20% monthly. Design optimization strategy
**Answer:**
- **Analysis first:**
  1. CloudWatch: ReadCapacityUnits, WriteCapacityUnits consumed vs provisioned
  2. Cost Explorer: Which tables? Which operations? Read vs Write split?
  3. DynamoDB contributor insights: Hot keys, access patterns
- **Optimization strategies:**
  | Strategy | Savings | Effort |
  |----------|---------|--------|
  | Switch to On-Demand (if variable) or Provisioned+Autoscaling (if predictable) | 20-60% | Low |
  | Add DAX cache for read-heavy tables | 40-80% reads | Medium |
  | Reduce item size (compress, separate hot/cold attributes) | 20-30% | Medium |
  | TTL + archive old data to S3 | 30-50% storage | Low |
  | Redesign access patterns (reduce scans, better partition key) | 50%+ | High |
  | Move infrequently accessed data to S3 + Athena | 70%+ for cold data | Medium |
  | Reserved capacity (if commit to 1+ year) | 53-76% | Contract |
- **Architecture change (if needed):**
  - Hot data in DynamoDB + DAX (last 7 days)
  - Warm data in DynamoDB Standard-IA table class (last 90 days, 60% storage savings)
  - Cold data in S3 Parquet + Athena (historical)
  - DynamoDB Streams → Lambda → S3 (continuous archival)
- **Key insight:** At $50K/month, even 30% optimization = $180K/year savings. Justify engineering investment

### Q11: Design the migration strategy from monolithic RDS to microservices databases
**Answer:**
- **Phase 1: Identify bounded contexts (2-4 weeks)**
  - Map domain objects to services (users, orders, products, payments)
  - Identify query patterns crossing boundaries
  - Choose target database per service (RDS, DynamoDB, etc.)

- **Phase 2: Introduce Branch by Abstraction (4-8 weeks)**
  - Create database abstraction layer in monolith
  - New service reads from own DB but writes to both (dual-write via monolith)
  - Or: Monolith writes to old DB + publishes event → new service keeps own DB in sync

- **Phase 3: Strangler Fig per service (ongoing)**
  ```
  API Gateway
  ├── /users/* → New User Service (own PostgreSQL)
  ├── /orders/* → New Order Service (own DynamoDB)
  └── /* → Monolith (shared RDS) ← shrinking
  ```

- **Phase 4: Remove old tables**
  - After all reads/writes migrated to new service
  - Keep old tables read-only for 30 days (safety net)
  - Archive and drop

- **Cross-service queries (the hard part):**
  - API composition: Service A calls Service B for data needed (runtime)
  - CQRS: Materialized view combining data from multiple services (async)
  - Event-driven: Services publish events → denormalized read store
  - **Avoid:** Shared database between services (couples them)

- **Data migration:**
  - DMS for initial full load + CDC (ongoing sync during transition)
  - Validate row counts + checksums
  - Shadow reads: Read from both, compare results, alert on mismatch

### Q12: Design observability strategy for 200+ microservices
**Answer:**
- **Principles:**
  - Standardized (all services emit same format)
  - Correlated (trace ID across all signals)
  - Actionable (alerts tied to SLOs, not just thresholds)
  - Cost-effective (sample, aggregate, tier)

- **Three pillars implementation:**
  ```
  Metrics (Prometheus/CloudWatch):
    RED per service: Rate, Errors, Duration
    USE per resource: Utilization, Saturation, Errors
    Business metrics: Orders/min, revenue, conversion
    → Grafana dashboards + Alertmanager
  
  Logs (Fluent Bit → OpenSearch/S3):
    Structured JSON: timestamp, traceId, service, level, message
    → Hot (OpenSearch, 7d) + Cold (S3, 1yr)
    → Cost: S3 ($23/TB) vs CloudWatch Logs ($500/TB)
  
  Traces (OpenTelemetry → X-Ray/Jaeger):
    Sampling: 10% normal, 100% errors/slow
    → Identify latency source in request chain
  ```

- **SLO-based alerting:**
  - Define SLOs per service: 99.9% availability, p99 < 200ms
  - Calculate error budget: 0.1% = 43 min/month
  - Alert on burn rate: "Burning error budget 10x faster than sustainable"
  - Benefits: Fewer alerts (only when users affected), prioritized by impact

- **Cost management at scale:**
  - 200 services × 100 metrics × per-second = expensive
  - Solution: Aggregate to 1-minute resolution, sample traces (10%), tier log storage
  - Estimated cost: $5-15K/month (vs $50K+ without optimization)

