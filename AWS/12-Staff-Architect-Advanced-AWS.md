# Staff/Architect Level - Advanced AWS Architecture Patterns

> Deep architectural decisions, trade-offs, and patterns for senior roles.

---

## 1. Well-Architected Framework (Staff-level depth)

### Six Pillars with Architect Decisions

#### Operational Excellence
- **Key question:** "How do you evolve your architecture without impacting users?"
- **Answers:** Feature flags, canary deployments, blue/green, observability-driven development
- **Anti-patterns:** Manual deployments, snowflake servers, undocumented changes
- **Staff responsibility:** Define operational excellence standards, runbook templates, SLO framework

#### Security
- **Key question:** "How do you protect data in a multi-team, multi-account environment?"
- **Answers:** Zero-trust, defense-in-depth, encryption by default, automated compliance
- **Architect patterns:**
  - Encryption: Per-service KMS keys, envelope encryption, field-level encryption for PII
  - Identity: Service mesh mTLS + IRSA for AWS access + short-lived tokens everywhere
  - Detection: GuardDuty + Security Hub + Config Rules + automated remediation
  - Prevention: SCPs + Permission Boundaries + preventive guardrails

#### Reliability
- **Key question:** "How do you design for failure at every layer?"
- **Answers:** Chaos engineering, cell-based architecture, blast radius reduction
- **Cell-based architecture:**
  ```
  Each "cell" is independent and handles a subset of users/traffic
  Cell 1: Users A-M (us-east-1a, 1b)
  Cell 2: Users N-Z (us-east-1c, us-east-1d)
  
  Benefits: Cell failure affects only subset of users
  Implementation: Partition by user/tenant → route to cell → cell is self-contained
  ```

#### Performance Efficiency
- **Key question:** "How do you make optimal technology selections that evolve over time?"
- **Answers:** Benchmark-driven decisions, regular architecture reviews, experiments
- **Architect patterns:**
  - Data-driven: Load test with realistic traffic BEFORE production
  - Mechanical sympathy: Understand underlying hardware (Nitro, Graviton, EFA)
  - Right tool: DynamoDB for KV, OpenSearch for search, Neptune for graph (not everything in RDS)

#### Cost Optimization
- **Key question:** "How do you maximize business value per dollar spent?"
- **At architect level:** Unit economics (cost per transaction), not just total spend
- **Patterns:** Spot for non-critical, Serverless for variable, RI/SP for baseline, tiered storage

#### Sustainability
- **Key question:** "How do you minimize environmental impact of cloud workloads?"
- **Answers:** Right-size (less waste), Graviton (more efficient), serverless (shared resources), Region selection (renewable energy)

---

## 2. Advanced Networking Patterns

### Service-to-Service Communication Decision Tree
```
Need request-response? 
  ├── Yes: Synchronous
  │   ├── Internal: Service Mesh (gRPC/HTTP via Envoy)
  │   └── External: API Gateway
  └── No: Asynchronous
      ├── Need ordering? 
      │   ├── Yes: Kinesis/SQS FIFO
      │   └── No: SQS Standard / SNS fan-out
      ├── Need pub/sub (multiple consumers)?
      │   └── SNS → SQS (fan-out) or EventBridge (rule-based routing)
      └── Need workflow orchestration?
          └── Step Functions
```

### VPC Lattice (Modern Service Networking)
- **What:** L7 service-to-service networking across VPCs and accounts (without VPC peering or TGW)
- **Why it matters:** Replaces complex mesh of VPC peering + internal NLBs + service discovery
- **Components:** Service network, Service, Target group, Listener, Rules
- **Benefits:** 
  - Cross-VPC/account without network-level connectivity
  - Built-in auth (IAM + SigV4), observability, traffic management
  - Simpler than service mesh for AWS-native workloads
- **vs App Mesh:** Lattice = infrastructure-level networking. App Mesh = application-level sidecar proxy
- **vs API Gateway:** API Gateway = external traffic. Lattice = internal service-to-service

### PrivateLink Architecture at Scale
```
Provider Account (SaaS):
  NLB → Backend Services
  VPC Endpoint Service (connected to NLB)
  
Consumer Accounts (Customers):
  Interface VPC Endpoint → access provider's service via private IP
  
Benefits at scale:
  - No VPC peering needed (CIDR overlap OK)
  - Unidirectional (consumer → provider only)
  - IAM + endpoint policies for access control
  - Cross-account, cross-region
```

### Global Accelerator vs CloudFront
| | Global Accelerator | CloudFront |
|--|---|---|
| Protocol | TCP/UDP (any) | HTTP/HTTPS |
| Caching | No | Yes |
| Static IPs | Yes (2 anycast) | No |
| Use case | Non-HTTP (gaming, IoT, VoIP), TCP failover | Web content, APIs, streaming |
| Routing | Nearest healthy endpoint | Nearest edge cache |

---

## 3. Advanced Data Patterns

### Data Mesh on AWS
- **Principle:** Decentralized data ownership (domain teams own their data products)
- **Architecture:**
  ```
  Domain Team A (User Service):
    Source: DynamoDB → 
    Data Product: S3 (Parquet) in their account
    Catalog: Glue Data Catalog (shared via Lake Formation)
  
  Domain Team B (Order Service):
    Source: Aurora →
    Data Product: S3 (Parquet) in their account
    Catalog: Glue Data Catalog
  
  Platform Team:
    Governance: Lake Formation (permissions, audit)
    Discovery: Glue Data Catalog (central search)
    Infrastructure: Shared Kinesis, S3 templates, Athena
  
  Consumer Team (Analytics):
    Query: Athena / Redshift Spectrum across data products
    Access: Lake Formation grants (no data copying)
  ```

### Event Streaming Architecture Decisions
| Criteria | Kinesis | SQS | MSK (Kafka) | EventBridge |
|----------|---------|-----|-------------|-------------|
| Ordering | Per-shard | FIFO only | Per-partition | No |
| Retention | 24hr-365d | 4d-14d | Unlimited | None (real-time) |
| Consumers | Multiple (fan-out) | Single (polling) | Multiple (consumer groups) | Rule-based routing |
| Replay | Yes | No | Yes | No |
| Scale | Shard-based | Unlimited | Partition-based | Unlimited |
| Managed | Fully | Fully | Semi (you manage topics) | Fully |
| **Best for** | Real-time analytics, IoT | Job queues, decoupling | High-throughput streaming | Event routing, integration |

### Change Data Capture (CDC) Patterns
```
Source → CDC → Processing → Target

Pattern 1: DynamoDB Streams → Lambda → ElastiCache/OpenSearch
Pattern 2: Aurora → DMS with CDC → Kinesis → S3 (data lake)
Pattern 3: MSK Connect (Debezium) → MSK → consumers
Pattern 4: RDS → DMS → Kinesis → Lambda → DynamoDB (CQRS read model)
```

- **Debezium (via MSK Connect):** Most flexible. Log-based CDC from RDS/Aurora. No impact on source
- **DMS CDC:** AWS-managed. Simpler setup but less features than Debezium
- **DynamoDB Streams:** Native CDC for DynamoDB. 24-hour retention

---

## 4. Advanced Compute Patterns

### Serverless vs Containers Decision Matrix
| Factor | Serverless (Lambda) | Containers (ECS/EKS) |
|--------|--------------------|-----------------------|
| Cold start | 100ms-10s (problem for latency-sensitive) | None (always running) |
| Max duration | 15 minutes | Unlimited |
| Cost at low scale | Cheapest (pay per invocation) | Expensive (minimum instances) |
| Cost at high scale | Expensive (per-ms billing adds up) | Cheaper (amortized over time) |
| Max concurrency | 1000 (default, can increase) | Unlimited (add instances) |
| Complexity | Low (no infra) | Medium-High (cluster management) |
| Vendor lock-in | High (Lambda-specific) | Low (K8s portable) |
| **Choose Lambda:** | Event-driven, variable load, simple functions, glue code |
| **Choose Containers:** | Long-running, high-throughput, complex apps, portability needed |

### Lambda Power Tuning
- **Problem:** What memory/CPU setting minimizes cost AND latency?
- **Tool:** AWS Lambda Power Tuning (Step Functions that tests different memory configs)
- **Insight:** More memory = more CPU = faster execution = less duration cost
- **Sweet spot:** Often 1024-2048MB (faster execution offsets higher per-ms cost)
- **Example:** 128MB × 10s × $0.0000002083 = $0.000002083 vs 1024MB × 1.5s × $0.0000166667 = $0.000025 (more expensive but 6.7x faster)
- **Architect decision:** For user-facing: optimize for latency. For async: optimize for cost

### Step Functions Patterns
- **Standard vs Express:**
  - Standard: Long-running (up to 1 year), exactly-once, $0.025 per 1000 transitions
  - Express: Short (5 min max), at-least-once, $1 per 1M requests + duration
- **Patterns:**
  - Saga: Orchestrate distributed transaction with compensation
  - Map: Fan-out parallel processing (process 10K items concurrently)
  - Wait: Human approval workflow (wait for callback)
  - Choice: Branching logic without code
  - Retry/Catch: Built-in error handling per state

---

## 5. Advanced Container Orchestration

### EKS Multi-Cluster Strategy
```
Cluster per environment:
  eks-dev    → developers, fast iteration, relaxed policies
  eks-staging → integration testing, production-like
  eks-prod-1 → production region 1 (us-east-1)
  eks-prod-2 → production region 2 (eu-west-1)

Management:
  ArgoCD (hub cluster) → manages all clusters
  Karpenter → per-cluster auto-provisioning
  External Secrets Operator → sync from Secrets Manager per cluster
```

### Kubernetes Cost Optimization (Architect-level)
1. **Right-sizing pods:** VPA recommendations → tune requests/limits
2. **Bin-packing:** Karpenter consolidation (move pods to fewer, fuller nodes)
3. **Spot nodes:** 70-90% savings. Karpenter weighted spot + on-demand fallback
4. **Node selection:** Graviton (20% cheaper), right instance family
5. **Scale to zero:** KEDA for non-production, HPA minReplicas=0 with KEDA
6. **Namespace quotas:** Prevent teams from over-requesting
7. **Measurement:** Kubecost or OpenCost for per-team/namespace cost visibility
- **Target:** 60-70% cluster utilization (below = waste, above = no headroom for burst)

### Multi-Tenancy at Scale
- **Namespace-based (soft):** Good for trusted teams within organization
  - ResourceQuota, LimitRange, NetworkPolicy, RBAC per namespace
  - Risk: Noisy neighbor (pod consuming node resources), privilege escalation
- **Cluster-based (hard):** Maximum isolation
  - Separate cluster per tenant/team
  - Expensive (EKS control plane: $0.10/hr × clusters)
- **Virtual cluster (vcluster):** Middle ground
  - Virtual K8s control plane per tenant inside shared cluster
  - Tenant sees own cluster, actually sharing underlying nodes
- **Architect decision:** Start with namespaces + strict policies. Move to vclusters if isolation requirements grow. Dedicated clusters only for compliance/regulation

---

## 6. Advanced Security Architecture

### Supply Chain Security
```
Source → Build → Package → Deploy → Runtime

Each stage needs verification:
Source: Signed commits, branch protection, CODEOWNERS
Build: Hermetic builds, SBOM generation, build provenance (SLSA Level 3)
Package: Image signing (Cosign/Notation), vulnerability scanning (Trivy/Inspector)
Deploy: Admission control (verify signature before deploying)
Runtime: Runtime protection (Falco), continuous scanning
```

### Encryption Architecture at Scale
- **KMS Key hierarchy:**
  ```
  AWS KMS
  ├── Organization-level keys (audit logs, backups)
  ├── Account-level keys (general purpose per account)
  ├── Service-level keys (per-service encryption)
  └── Data-classification keys (PII key, financial key)
  ```
- **Cross-account encryption:**
  - Key policy: Allow specific roles in specific accounts
  - Resource policy: Grant decrypt to consumer account roles
- **Envelope encryption everywhere:**
  - KMS encrypts data keys (envelope)
  - Data keys encrypt actual data (locally, no KMS call per record)
  - Performance: Generate data key, cache plaintext key briefly, encrypt many records
- **Field-level encryption:**
  - Encrypt PII fields before storing in DynamoDB
  - Only services with decrypt permission can read PII
  - Other services see encrypted blob (can still query non-PII fields)

### Network Security Layers
```
Internet
  ↓ Shield Standard (always-on L3/L4 DDoS)
CloudFront Edge
  ↓ WAF (L7 filtering: SQLi, XSS, rate-limit, bot control)
  ↓ CloudFront Functions (custom validation)
API Gateway / ALB
  ↓ VPC (network boundary)
  ↓ NACL (subnet-level stateless rules)
  ↓ Security Group (instance-level stateful rules)
  ↓ Network Policy (K8s pod-level L3/L4)
  ↓ Service Mesh mTLS (service identity verification)
Application
  ↓ IAM (API authorization)
  ↓ Application auth (JWT/RBAC)
Data Layer
  ↓ Encryption at rest (KMS)
  ↓ Row-level security (RDS) / partition isolation (DynamoDB)
```

---

## 7. Migration Architecture

### Migration Strategies (7 Rs)
| Strategy | Description | When to Use | Effort |
|----------|-------------|-------------|--------|
| Rehost (lift-and-shift) | Move as-is to EC2 | Quick migration, no changes | Low |
| Replatform | Minor optimization (RDS instead of self-managed DB) | Quick wins | Low-Med |
| Repurchase | Move to SaaS (Salesforce, Workday) | Replace commodity | Med |
| Refactor | Re-architect for cloud-native | Core differentiator | High |
| Retire | Decommission | No longer needed | Low |
| Retain | Keep on-prem | Not worth migrating yet | None |
| Relocate | VMware Cloud on AWS | Minimal change | Low |

### Large-Scale Migration (1000+ servers)
- **Phase 1: Assess (4-8 weeks)**
  - Application Discovery Service / Migration Hub
  - Dependencies mapping (who talks to who)
  - TCO analysis (on-prem vs AWS)
  - Wave planning (group related apps)
  
- **Phase 2: Mobilize (8-12 weeks)**
  - Landing zone setup (Control Tower, accounts, networking)
  - Direct Connect / VPN for hybrid connectivity
  - CI/CD pipeline for infrastructure
  - Security baseline (GuardDuty, Config Rules)
  
- **Phase 3: Migrate (ongoing, wave-based)**
  - Wave 1: Easy wins (stateless web servers, lift-and-shift)
  - Wave 2: Databases (DMS with CDC for minimal downtime)
  - Wave 3: Complex apps (refactor, dependencies)
  - Each wave: Test → migrate → validate → cutover

- **Phase 4: Optimize (ongoing)**
  - Right-size instances
  - Modernize (containers, serverless)
  - Cost optimization (RI, Savings Plans)

### Application Modernization Path
```
Monolith on EC2 (rehost)
  ↓ (months 1-3)
Containerize monolith on ECS (replatform)
  ↓ (months 3-6)
Extract first microservice (strangler fig)
  ↓ (months 6-12)
Multiple microservices on EKS + remaining monolith
  ↓ (months 12-24)
Fully decomposed microservices + serverless where appropriate
```

---

## 8. Capacity Planning & Performance

### Capacity Planning Framework
1. **Baseline:** Current traffic patterns (CloudWatch: requests/sec, CPU, memory, DB connections)
2. **Growth:** Project growth (historical trend + business input). Typically 2-5x for planning
3. **Peaks:** Identify traffic spikes (Black Friday = 10x, launch day = 20x)
4. **Limits:** Service quotas (Lambda: 1000 concurrent, DynamoDB: 40K RCU, ALB: 100 rules)
5. **Buffer:** Add 40-50% headroom above expected peak
6. **Test:** Load test to verify capacity meets projected needs

### Performance Budgets
```
Total request budget: 500ms (user-perceived latency)
Breakdown:
  DNS:           5ms (Route 53, cached after first)
  TCP/TLS:      30ms (connection reuse helps)
  CloudFront:   10ms (edge processing)
  API Gateway:  15ms (auth + routing)
  Load Balancer: 5ms
  Application:  200ms (your code)
  Database:     50ms (query + network)
  Cache:         5ms (Redis)
  Serialization: 20ms (JSON encoding)
  Buffer:       160ms (unexpected)
```
- **Architect responsibility:** Allocate latency budget per component. Alert when any component exceeds its budget

### Load Testing Strategy
- **Tools:** k6 (modern, scriptable), Locust (Python), JMeter (legacy), Artillery
- **Types:**
  - Smoke test: Minimal load, verify system works (CI pipeline)
  - Load test: Expected production traffic (capacity verification)
  - Stress test: Beyond capacity (find breaking point)
  - Soak test: Normal load for extended time (find memory leaks, connection exhaustion)
  - Spike test: Sudden traffic surge (verify auto-scaling)
- **Environment:** Test against production-like (same sizes, same data volume, same network)
- **Metrics to capture:** p50, p95, p99 latency, error rate, throughput, resource utilization
- **Frequency:** Before major releases, quarterly for capacity planning, after architecture changes

---

## 9. Organizational Architecture Decisions

### Team Topologies for Cloud
- **Stream-aligned team:** Delivers end-to-end feature (owns services + data + deployment)
- **Platform team:** Provides self-service capabilities (K8s cluster, CI/CD, observability)
- **Enabling team:** Helps stream-aligned teams adopt new practices (security, SRE coaching)
- **Complicated subsystem team:** Specialized domain needing deep expertise (ML models, data pipeline)

### Service Ownership Model
```
Per service:
  Owner: Team name
  SLO: 99.9% availability, p99 < 200ms
  On-call: Team rotation (PagerDuty)
  Runbooks: Documented in wiki/Backstage
  Dependencies: Listed + monitored
  Cost: Tracked and reviewed monthly
  
  "You build it, you run it" - each team owns full lifecycle
```

### Architecture Review Process
1. **Design doc:** RFC-style document (problem, requirements, options, recommendation)
2. **Review:** Architecture review board OR async review (comments on doc)
3. **ADR:** Record decision with context, alternatives, consequences
4. **Implementation:** Team implements with checkpoints
5. **Retrospective:** Review decision after 3-6 months (was it right?)

### Technical Debt Governance
- **Categorize:**
  - Critical (security/reliability): Fix this sprint
  - High (performance/scalability): Fix this quarter
  - Medium (maintainability): Schedule when relevant
  - Low (cleanup): Boy scout rule
- **Budget:** 20% of engineering capacity reserved for tech debt reduction
- **Tracking:** SonarQube debt + manual backlog items + dependency updates
- **Architecture review:** Quarterly fitness function assessment (is architecture still fit for purpose?)

---

## 10. Staff/Architect Behavioral Scenarios

### Q1: "Two teams disagree on technology choice (Kafka vs SQS). How do you resolve?"
**Answer:**
1. **Clarify requirements:** What problem exactly? Ordering needed? Replay? Throughput? Consumer model?
2. **Define evaluation criteria:** Cost, complexity, team expertise, scalability, maintenance burden
3. **Data-driven POC:** Both teams build small proof-of-concept, measure against criteria
4. **Architecture Decision Record:** Document choice with reasoning, alternatives, trade-offs
5. **Disagree and commit:** After decision, both teams fully commit regardless of preference
6. **Review:** Revisit in 6 months with production data

### Q2: "Leadership wants to adopt Kubernetes but you think it's overkill for the team size (5 engineers). How do you push back?"
**Answer:**
- **Acknowledge the appeal:** K8s is powerful and industry-standard
- **Present data:**
  - ECS Fargate: 0 operational overhead, same containerization benefits, team productive in 1 week
  - EKS: 1-2 engineers just for cluster operations, 2-3 month learning curve, add-ons management
  - For 5 engineers: K8s operational overhead = 20-40% of team capacity
- **Propose alternative:** Start with ECS Fargate. Migrate to EKS when team grows to 15+ AND K8s-specific features needed (custom controllers, advanced scheduling)
- **Decision framework:** What does K8s give us that ECS doesn't? If answer is "portability we'll need someday" → ECS now, K8s later
- **Key principle:** Match technology complexity to organizational capacity

### Q3: "System is experiencing performance degradation but monitoring shows everything 'green'. What's your approach?"
**Answer:**
1. **Define "degradation":** User-reported? Latency increase? Error increase? Where in the funnel?
2. **Check what monitoring DOESN'T cover:**
   - Garbage collection pauses (JVM metrics?)
   - Connection pool exhaustion (pool metrics missing?)
   - DNS resolution time (not typically monitored)
   - TLS certificate overhead (not monitored)
   - Downstream services (are THEIR metrics green?)
3. **Correlation analysis:**
   - When did it start? Correlate with deployments, config changes, traffic patterns
   - Specific users/endpoints/regions affected?
   - Time-of-day pattern? (could be related to batch jobs, cron)
4. **Deep instrumentation:**
   - Add distributed tracing (X-Ray) if not present
   - Profile application (flame graph reveals where time is spent)
   - Packet capture (tcpdump) for network-level analysis
5. **Root cause:** Often: monitoring gaps hiding the real issue (e.g., monitoring checks health endpoint which is lightweight, but real endpoints are slow)

### Q4: "How would you design the architecture for a startup that might need to scale from 100 to 10 million users?"
**Answer:**
- **Phase 1 (100-10K users): Simple, cheap, fast to iterate**
  - Monolith on ECS Fargate (single service, fast deployment)
  - Aurora Serverless v2 (scales with demand, zero management)
  - CloudFront + S3 for static assets
  - Cost: ~$200-500/month
  
- **Phase 2 (10K-100K users): Optimize bottlenecks**
  - Add ElastiCache Redis for hot data (sessions, frequent queries)
  - Add read replicas for Aurora
  - Split monolith into 2-3 services (user-facing, background processing, admin)
  - Add SQS for async processing (emails, notifications)
  - Cost: ~$2,000-5,000/month
  
- **Phase 3 (100K-1M users): Distributed**
  - Full microservices on EKS (team growing, need independent deployments)
  - DynamoDB for high-traffic, simple-access patterns
  - Aurora for complex queries
  - Event-driven architecture (EventBridge + SQS)
  - Multi-AZ everything, auto-scaling everywhere
  - Cost: ~$20,000-50,000/month
  
- **Phase 4 (1M-10M users): Global**
  - Multi-region active-active
  - DynamoDB Global Tables
  - Aurora Global Database
  - CDN edge logic (personalization at edge)
  - Dedicated platform team
  - Cost: ~$100,000-500,000/month

- **Key architect principle:** Don't over-engineer Phase 1 for Phase 4. Each phase should unlock next 10x growth. Refactor when you're at 50-70% of current architecture's capacity limit, not before.

