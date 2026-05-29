# Microservices Fundamentals

## Definition and Characteristics

Microservices is an architectural style that structures an application as a collection of loosely coupled, independently deployable services, each running in its own process and communicating via lightweight mechanisms (typically HTTP/REST or messaging).

### Key Characteristics

| Characteristic | Description |
|---|---|
| Small & Focused | Each service does one thing well |
| Independently Deployable | Deploy without coordinating with other services |
| Loosely Coupled | Changes in one don't require changes in others |
| Organized around Business Capabilities | Not technical layers |
| Owned by Small Teams | Two-pizza team rule |
| Technology Heterogeneous | Each service can use different tech stack |
| Decentralized Data Management | Each service owns its data |
| Fault Tolerant | Design for failure |
| Observable | Centralized logging, monitoring, tracing |

---

## 12-Factor App Methodology

Originally defined by Heroku engineers for building SaaS apps. Essential for microservices.

### I. Codebase
> One codebase tracked in version control, many deploys

- One repo per service (or mono-repo with clear boundaries)
- Same codebase deployed to dev, staging, production
- Different deploys may run different versions

### II. Dependencies
> Explicitly declare and isolate dependencies

- Never rely on system-wide packages
- Use dependency manifests (package.json, requirements.txt, go.mod)
- Vendor or lock dependencies for reproducible builds

### III. Config
> Store config in the environment

- Config = anything that varies between deploys (DB URLs, credentials, feature flags)
- Never hardcode config in source code
- Use environment variables or external config services (Consul, Spring Cloud Config)

### IV. Backing Services
> Treat backing services as attached resources

- Databases, message queues, caches, SMTP servers are all attached resources
- Swappable without code changes (local MySQL vs Amazon RDS)
- Connection info lives in config

### V. Build, Release, Run
> Strictly separate build and run stages

- **Build**: Convert code into executable bundle
- **Release**: Combine build with config
- **Run**: Launch the process in the execution environment
- Every release has a unique ID; releases are immutable

### VI. Processes
> Execute the app as one or more stateless processes

- Processes are stateless and share-nothing
- Persistent data stored in backing services
- Sticky sessions are a violation — use distributed cache instead

### VII. Port Binding
> Export services via port binding

- The service is self-contained; it doesn't rely on an external web server
- Exposes HTTP (or other protocol) by binding to a port
- One service can become a backing service for another

### VIII. Concurrency
> Scale out via the process model

- Scale by running more instances (horizontal scaling)
- Different process types for different workloads (web, worker, scheduler)
- Never daemonize; use process managers (systemd, Kubernetes)

### IX. Disposability
> Maximize robustness with fast startup and graceful shutdown

- Processes start quickly and shut down gracefully
- Handle SIGTERM; finish current requests, then exit
- Crash-only design: safe to kill at any time
- Use work queues for long-running tasks

### X. Dev/Prod Parity
> Keep development, staging, and production as similar as possible

- Minimize gaps: time (deploy quickly), personnel (devs who write it deploy it), tools (same backing services)
- Use containers (Docker) to achieve parity
- Avoid "works on my machine" problems

### XI. Logs
> Treat logs as event streams

- Never manage log files within the service
- Write to stdout/stderr
- Execution environment captures and routes logs (Fluentd, Logstash, CloudWatch)

### XII. Admin Processes
> Run admin/management tasks as one-off processes

- DB migrations, console sessions, one-time scripts
- Run in identical environment as long-running processes
- Ship with the application code

---

## Single Responsibility Principle (SRP) in Microservices

> A service should have one, and only one, reason to change.

- Each microservice encapsulates a single business capability
- Changes to billing logic shouldn't affect inventory service
- Indicators of SRP violation:
  - Service changes frequently for unrelated reasons
  - Multiple teams need to coordinate for changes
  - Service name contains "and" (e.g., "OrderAndPayment")

**Practical guideline**: If you can't describe what a service does in one sentence without using "and," it may be too broad.

---

## Bounded Context (from DDD)

A **Bounded Context** is a boundary within which a particular domain model is defined and applicable.

- Same term can mean different things in different contexts (e.g., "Account" in Banking vs Authentication)
- Each microservice should align with one bounded context
- Communication between contexts happens through well-defined interfaces
- Ubiquitous Language is consistent within a context but may differ across contexts

```
┌─────────────────┐    ┌─────────────────┐
│  Sales Context  │    │ Shipping Context │
│                 │    │                  │
│ Customer = buyer│    │ Customer = recip.│
│ Product = offer │    │ Product = parcel │
└────────┬────────┘    └────────┬─────────┘
         │    Anti-Corruption    │
         └───────Layer───────────┘
```

---

## Autonomy and Independent Deployability

### Autonomy
- Teams can develop, test, deploy without coordinating
- Each service has its own CI/CD pipeline
- Own database (no shared schemas)
- Own technology choices

### Independent Deployability
- The single most important property of microservices
- Requires:
  - Loose coupling between services
  - Backward-compatible API changes
  - Contract testing (Pact, Spring Cloud Contract)
  - Feature flags for partial rollouts

**Test**: Can you deploy service A without deploying service B? If not, they're not truly independent.

---

## Decentralized Governance

- No single technology mandate across all services
- Teams choose the best tool for their problem
- Shared standards only where necessary (API contracts, security, observability)
- Inner source model for shared libraries
- Avoid the "golden path" becoming a mandate

### What to centralize vs decentralize:

| Centralize | Decentralize |
|---|---|
| Security policies | Programming language |
| API standards (REST/gRPC conventions) | Framework choice |
| Observability (logging format, tracing) | Database technology |
| Deployment platform | Internal architecture |
| Auth mechanism | Testing strategy details |

---

## Design for Failure

In distributed systems, failure is inevitable. Design assumes components will fail.

### Patterns:
- **Circuit Breaker**: Stop calling a failing service; fail fast
- **Bulkhead**: Isolate failures; don't let one failing dependency bring down everything
- **Timeout**: Never wait indefinitely
- **Retry with backoff**: Transient failures may resolve themselves
- **Fallback**: Degrade gracefully (cached data, default response)
- **Health checks**: Liveness and readiness probes
- **Chaos engineering**: Intentionally inject failures (Netflix Simian Army)

### Failure modes to design for:
- Network partitions
- Service crashes
- Slow responses (worse than crashes — they consume resources)
- Cascading failures
- Data inconsistency

---

## Infrastructure Automation

- **CI/CD pipelines**: Automated build, test, deploy per service
- **Infrastructure as Code**: Terraform, Pulumi, CloudFormation
- **Container orchestration**: Kubernetes, ECS
- **Immutable infrastructure**: Replace, don't patch
- **GitOps**: Infrastructure state in Git (ArgoCD, Flux)
- **Service mesh**: Istio, Linkerd for cross-cutting concerns
- **Automated testing**: Unit → Integration → Contract → E2E

Without automation, the operational overhead of microservices makes them impractical.

---

## Evolutionary Design

- Services are replaceable, not precious
- Start with a monolith if domain is unclear (Monolith First approach)
- Extract services when boundaries become clear
- Design for replaceability: could you rewrite this service in 2 weeks?
- Avoid premature decomposition
- Use fitness functions to track architectural goals

---

## Smart Endpoints, Dumb Pipes

- Business logic lives in services (smart endpoints)
- Communication infrastructure is simple (dumb pipes)
- Contrast with ESB (Enterprise Service Bus) where pipes had routing, transformation, orchestration
- Preferred communication:
  - Synchronous: REST, gRPC (point-to-point)
  - Asynchronous: Simple message broker (RabbitMQ, Kafka) — broker just delivers messages, no transformation

---

## Conway's Law and Team Topology

> "Organizations design systems that mirror their communication structures." — Melvin Conway

### Implications:
- If you have 4 teams, you'll get 4 services (roughly)
- Align team boundaries with service boundaries
- **Inverse Conway Maneuver**: Structure teams to get the architecture you want

### Team Topologies (Skelton & Pais):
- **Stream-aligned teams**: Deliver value for a business domain
- **Enabling teams**: Help stream-aligned teams adopt new tech
- **Complicated subsystem teams**: Own complex domains requiring specialists
- **Platform teams**: Provide self-service internal platform

---

## Microservices vs SOA vs Monolith

| Aspect | Monolith | SOA | Microservices |
|---|---|---|---|
| **Size** | Single deployable unit | Large services | Small, focused services |
| **Data** | Shared database | Shared or separate | Each owns its data |
| **Communication** | In-process calls | ESB (smart pipes) | REST/messaging (dumb pipes) |
| **Governance** | Centralized | Centralized | Decentralized |
| **Deployment** | All-or-nothing | Service-level | Independent per service |
| **Technology** | Homogeneous | Mostly homogeneous | Heterogeneous |
| **Team Structure** | Feature teams across layers | Project teams | Product teams per service |
| **Coupling** | Tight | Moderate (through ESB) | Loose |
| **Complexity** | In code | In middleware | In operations |
| **Best For** | Small teams, unclear domains | Enterprise integration | Rapid scaling, large orgs |
| **Scaling** | Vertical | Horizontal (coarse) | Horizontal (fine-grained) |
| **Failure Impact** | Total | Partial | Isolated |

---

## CAP Theorem

> In a distributed system, you can only guarantee 2 of 3: **Consistency**, **Availability**, **Partition Tolerance**.

- **Consistency (C)**: Every read receives the most recent write
- **Availability (A)**: Every request receives a response (not guaranteed to be latest)
- **Partition Tolerance (P)**: System operates despite network partitions

### Reality:
- Network partitions WILL happen → you must choose between C and A during partitions
- **CP systems**: Choose consistency (e.g., HBase, MongoDB, ZooKeeper) — may return errors during partition
- **AP systems**: Choose availability (e.g., Cassandra, DynamoDB, CouchDB) — may return stale data

### Implications for microservices:
- Cross-service consistency is expensive
- Prefer eventual consistency where business allows
- Use sagas for distributed transactions
- PACELC theorem extends CAP: Even without partitions, there's a latency vs consistency tradeoff

---

## BASE vs ACID

| Property | ACID | BASE |
|---|---|---|
| **Full name** | Atomicity, Consistency, Isolation, Durability | Basically Available, Soft state, Eventually consistent |
| **Consistency** | Strong (immediate) | Eventual |
| **Availability** | May sacrifice for consistency | Prioritizes availability |
| **Use case** | Single database, financial transactions | Distributed systems, microservices |
| **Scaling** | Vertical (harder to scale) | Horizontal (scales well) |
| **Performance** | Lower (locking, coordination) | Higher (no distributed locks) |
| **Complexity** | Simple programming model | Requires compensation logic |

### In microservices:
- ACID within a single service's database
- BASE across services
- Sagas replace distributed transactions
- Idempotency is critical for eventual consistency

---

## Fallacies of Distributed Computing

Eight assumptions developers incorrectly make when building distributed systems (Peter Deutsch, 1994):

### 1. The network is reliable
- Packets get dropped, connections reset
- **Mitigation**: Retry, circuit breakers, idempotent operations

### 2. Latency is zero
- Remote calls are 1000x+ slower than in-process calls
- **Mitigation**: Batch calls, caching, async communication, avoid chatty interfaces

### 3. Bandwidth is infinite
- Large payloads cause congestion
- **Mitigation**: Pagination, compression, selective field responses (GraphQL)

### 4. The network is secure
- Every network hop is an attack surface
- **Mitigation**: mTLS, zero-trust, encrypt in transit, service mesh

### 5. Topology doesn't change
- Services move, IPs change, instances scale
- **Mitigation**: Service discovery, DNS, load balancers

### 6. There is one administrator
- Multiple teams, multiple cloud providers, multiple regions
- **Mitigation**: Decentralized operations, clear ownership, runbooks

### 7. Transport cost is zero
- Serialization, network hardware, cloud egress costs
- **Mitigation**: Efficient serialization (protobuf > JSON), minimize cross-region calls

### 8. The network is homogeneous
- Different protocols, OS, hardware, cloud providers
- **Mitigation**: Standard protocols (HTTP, gRPC), API contracts, abstraction layers

---

## Microservices Maturity Model

### Level 0: Monolith
- Single deployable unit
- Shared database
- Single team

### Level 1: Basic Decomposition
- Services extracted but share database
- Manual deployments
- Synchronous communication only

### Level 2: Decoupled Services
- Each service owns its data
- CI/CD per service
- API gateway in place
- Basic monitoring

### Level 3: Observable & Resilient
- Distributed tracing (Jaeger, Zipkin)
- Circuit breakers, retries, timeouts
- Centralized logging
- Health checks and auto-recovery
- Contract testing

### Level 4: Autonomous & Evolutionary
- Event-driven architecture
- Self-service platform
- Chaos engineering
- Automated canary deployments
- Full organizational alignment (Inverse Conway)
- Services are replaceable

---

## Anti-Patterns in Microservices

### 1. Distributed Monolith
- **Symptom**: Must deploy multiple services together
- **Cause**: Tight coupling through shared databases, synchronous chains, shared libraries with domain logic
- **Fix**: Enforce independent deployability, use async communication, eliminate shared state

### 2. Nano-services (Too Fine-Grained)
- **Symptom**: Services too small to justify operational overhead
- **Cause**: Over-applying SRP; one service per entity
- **Fix**: Merge related services; consider aggregate boundaries

### 3. Shared Database
- **Symptom**: Multiple services read/write the same tables
- **Cause**: Easier than data duplication
- **Fix**: Database per service; replicate data via events

### 4. Chatty Communication
- **Symptom**: Service A makes 20 calls to Service B for one operation
- **Cause**: Fine-grained APIs mimicking in-process calls
- **Fix**: Coarse-grained APIs, BFF pattern, data aggregation

### 5. Knot (Circular Dependencies)
- **Symptom**: Service A → B → C → A
- **Cause**: Poor boundary design
- **Fix**: Introduce event bus, extract shared concern into new service

### 6. ESB Resurgence (Smart Pipes)
- **Symptom**: API gateway or service mesh has business logic
- **Cause**: Convenience of centralized transformation
- **Fix**: Keep routing/infrastructure concerns only in middleware

### 7. No Versioning Strategy
- **Symptom**: Breaking changes cascade across consumers
- **Cause**: Lack of contract management
- **Fix**: Semantic versioning, backward-compatible changes, consumer-driven contracts

### 8. Golden Hammer
- **Symptom**: Every problem solved with microservices
- **Cause**: Hype-driven architecture
- **Fix**: Start with monolith if team is small or domain unclear; use microservices where they provide clear value

### 9. Mega Service (God Service)
- **Symptom**: One service handles too many responsibilities
- **Cause**: Incomplete decomposition
- **Fix**: Apply DDD; identify bounded contexts within the mega service

### 10. Lack of Observability
- **Symptom**: "It works on my machine" / can't trace failures
- **Cause**: Treating distributed system like a monolith operationally
- **Fix**: Structured logging, distributed tracing, metrics (RED/USE), alerting
