# 01 — Software Architecture Styles

> A comprehensive reference of all major architecture styles, their trade-offs, and when to apply them.

---

## Table of Contents

1. [Monolithic Architecture](#1-monolithic-architecture)
2. [Layered / N-Tier Architecture](#2-layered--n-tier-architecture)
3. [Client-Server Architecture](#3-client-server-architecture)
4. [Microservices Architecture](#4-microservices-architecture)
5. [Service-Oriented Architecture (SOA)](#5-service-oriented-architecture-soa)
6. [Event-Driven Architecture (EDA)](#6-event-driven-architecture-eda)
7. [Serverless Architecture](#7-serverless-architecture)
8. [Peer-to-Peer Architecture](#8-peer-to-peer-architecture)
9. [Space-Based Architecture](#9-space-based-architecture)
10. [Pipe-and-Filter Architecture](#10-pipe-and-filter-architecture)
11. [Hexagonal Architecture (Ports & Adapters)](#11-hexagonal-architecture-ports--adapters)
12. [Clean Architecture](#12-clean-architecture)
13. [Onion Architecture](#13-onion-architecture)
14. [Domain-Driven Design (DDD)](#14-domain-driven-design-ddd)
15. [CQRS Architecture](#15-cqrs-architecture)
16. [Actor Model Architecture](#16-actor-model-architecture)
17. [Micro-frontend Architecture](#17-micro-frontend-architecture)
18. [Cell-Based Architecture](#18-cell-based-architecture)
19. [Modular Monolith](#19-modular-monolith)
20. [Service Mesh Architecture](#20-service-mesh-architecture)
21. [Choreography vs Orchestration](#21-choreography-vs-orchestration)
22. [Broker Architecture](#22-broker-architecture)
23. [Blackboard Architecture](#23-blackboard-architecture)
24. [Component-Based Architecture](#24-component-based-architecture)
25. [Plugin Architecture](#25-plugin-architecture)

---

## 1. Monolithic Architecture

### Description
A single deployment unit where all application components (UI, business logic, data access) are packaged and deployed together as one artifact.

### Key Principles
- Single codebase, single deployment
- Shared memory space and database
- All modules tightly coupled at runtime
- Simple operational model

### ASCII Diagram
```
┌─────────────────────────────────────┐
│           MONOLITH                   │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐  │
│  │ UI  │ │Order│ │User │ │Pay  │  │
│  │Layer│ │Mgmt │ │Mgmt │ │ment │  │
│  └─────┘ └─────┘ └─────┘ └─────┘  │
│  ┌─────────────────────────────────┐│
│  │        Shared Database          ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

### When to Use
- Early-stage startups / MVPs
- Small teams (< 10 developers)
- Well-understood, stable domain
- Tight deadlines with simple requirements

### When NOT to Use
- Large teams working on independent features
- Need for independent scaling of components
- Need for technology diversity
- Frequent deployments of individual components

### Pros
- Simple to develop, test, deploy
- Easy debugging (single process)
- No network latency between components
- Simple transactions (ACID)
- Lower operational overhead

### Cons
- Scaling requires scaling everything
- Long build/deploy cycles as it grows
- Technology lock-in
- One bug can bring down entire system
- Team coupling and merge conflicts

### Real-world Examples
- **Early Shopify** — started as a Rails monolith
- **Stack Overflow** — famously runs on a monolith
- **Basecamp** — advocates for the majestic monolith

---

## 2. Layered / N-Tier Architecture

### Description
Organizes code into horizontal layers, each with a specific responsibility. Each layer only communicates with the layer directly below it.

### Key Principles
- Separation of concerns by technical function
- Each layer depends only on the layer below
- Layers are replaceable independently
- Typically 3-4 layers: Presentation → Business → Persistence → Database

### ASCII Diagram
```
┌─────────────────────────────┐
│     Presentation Layer      │  ← UI, Controllers, Views
├─────────────────────────────┤
│      Business Layer         │  ← Services, Rules, Validation
├─────────────────────────────┤
│     Persistence Layer       │  ← Repositories, DAOs, ORM
├─────────────────────────────┤
│      Database Layer         │  ← SQL, NoSQL, Files
└─────────────────────────────┘
```

### When to Use
- Standard line-of-business applications
- Teams familiar with traditional enterprise patterns
- Applications with clear separation of UI, logic, and data
- CRUD-heavy applications

### When NOT to Use
- High-performance systems requiring cross-layer optimization
- Domains where business logic doesn't align with layers
- Systems requiring complex domain models (use DDD instead)

### Pros
- Easy to understand and organize
- Clear separation of concerns
- Teams can work on layers independently
- Well-known pattern with abundant tooling

### Cons
- Can lead to "layered lasagna" — too many pass-through layers
- Changes often cascade through all layers
- Tendency toward anemic domain models
- Doesn't scale well organizationally

### Real-world Examples
- **Spring Boot apps** (Controller → Service → Repository)
- **ASP.NET MVC** applications
- **Most enterprise Java/EE** applications

---

## 3. Client-Server Architecture

### Description
Separates the system into two components: clients that request services and servers that provide them. Communication happens over a network via request-response.

### Key Principles
- Clear separation between requester (client) and provider (server)
- Server manages resources and business logic
- Clients present data and handle user interaction
- Stateless or stateful communication

### ASCII Diagram
```
┌────────┐         ┌────────┐
│Client 1│───┐     │        │
└────────┘   │     │        │
┌────────┐   ├────▶│ Server │
│Client 2│───┤     │        │
└────────┘   │     │        │
┌────────┐   │     │        │
│Client 3│───┘     └────────┘
└────────┘
```

### When to Use
- Web applications
- Email systems
- Database applications
- File sharing systems

### When NOT to Use
- Real-time peer-to-peer communication (gaming, video calls)
- Decentralized systems without a central authority
- Systems where server is a single point of failure and uptime is critical

### Pros
- Centralized data management and security
- Easy to maintain and update server independently
- Supports multiple client types (web, mobile, desktop)

### Cons
- Server is a single point of failure
- Network dependency
- Server can become a bottleneck
- Higher latency than local processing

### Real-world Examples
- **Web browsers ↔ Web servers**
- **Email clients ↔ SMTP/IMAP servers**
- **Mobile apps ↔ REST APIs**

---

## 4. Microservices Architecture

### Description
Structures an application as a collection of small, independent services, each running in its own process, owning its own data, and communicating via lightweight protocols.

### Key Principles
- Single Responsibility — each service does one thing well
- Independent deployability
- Decentralized data management (database per service)
- Design for failure
- Organized around business capabilities
- Smart endpoints, dumb pipes

### ASCII Diagram
```
┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐
│Order │  │User  │  │Pay   │  │Notif │
│Svc   │  │Svc   │  │Svc   │  │Svc   │
│      │  │      │  │      │  │      │
│┌────┐│  │┌────┐│  │┌────┐│  │┌────┐│
││ DB ││  ││ DB ││  ││ DB ││  ││ DB ││
│└────┘│  │└────┘│  │└────┘│  │└────┘│
└──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘
   │         │         │         │
───┴─────────┴─────────┴─────────┴───
          Message Bus / API Gateway
```

### When to Use
- Large teams (multiple squads)
- Need for independent deployment and scaling
- Complex domains with clear bounded contexts
- Polyglot technology requirements
- High availability requirements

### When NOT to Use
- Small teams / early-stage startups
- Simple CRUD applications
- Tight deadlines without operational maturity
- Teams lacking DevOps/infrastructure expertise

### Pros
- Independent deployment and scaling
- Technology freedom per service
- Fault isolation
- Team autonomy
- Easier to understand individual services

### Cons
- Distributed system complexity (network, consistency)
- Operational overhead (monitoring, tracing, deployment)
- Data consistency is hard (eventual consistency)
- Integration testing complexity
- Service discovery, versioning challenges

### Real-world Examples
- **Netflix** — 1000+ microservices
- **Amazon** — pioneered the approach (two-pizza teams)
- **Uber** — migrated from monolith to microservices
- **Spotify** — squad-based microservices

---

## 5. Service-Oriented Architecture (SOA)

### Description
An architectural pattern where application components provide services to other components via a communications protocol over a network. Uses an Enterprise Service Bus (ESB) for integration.

### Key Principles
- Services are reusable business functions
- Loose coupling via standardized contracts (WSDL, SOAP)
- Service abstraction hides implementation details
- Enterprise Service Bus for routing and transformation
- Service registry for discovery

### ASCII Diagram
```
┌────────┐  ┌────────┐  ┌────────┐
│Service │  │Service │  │Service │
│   A    │  │   B    │  │   C    │
└───┬────┘  └───┬────┘  └───┬────┘
    │            │            │
════╪════════════╪════════════╪════
         Enterprise Service Bus
════╪════════════╪════════════╪════
    │            │            │
┌───┴────┐  ┌───┴────┐  ┌───┴────┐
│Legacy  │  │  ERP   │  │  CRM   │
│System  │  │        │  │        │
└────────┘  └────────┘  └────────┘
```

### When to Use
- Large enterprises integrating heterogeneous systems
- Need to expose legacy systems as services
- Cross-organizational service sharing
- When governance and standardization are priorities

### When NOT to Use
- Small applications / startups
- When ESB becomes a bottleneck
- Teams wanting autonomy (use microservices instead)
- Greenfield projects without legacy baggage

### Pros
- Reusability of services across organization
- Platform and language independence
- Centralized governance and security
- Good for enterprise integration

### Cons
- ESB can become a single point of failure / bottleneck
- Complex and expensive (middleware, governance)
- Slower to change than microservices
- Over-engineering for simple needs
- SOAP/XML verbosity

### Real-world Examples
- **Banks and insurance companies** — integrating core banking with CRM
- **Government systems** — cross-department integration
- **Large enterprises** using IBM, Oracle, or MuleSoft ESBs

### SOA vs Microservices

| Aspect | SOA | Microservices |
|--------|-----|---------------|
| Scope | Enterprise-wide | Application-level |
| Communication | ESB (smart pipes) | Dumb pipes (HTTP, messaging) |
| Data | Shared databases | Database per service |
| Governance | Centralized | Decentralized |
| Size | Larger services | Smaller, focused services |

---

## 6. Event-Driven Architecture (EDA)

### Description
A pattern where the flow of the program is determined by events — significant changes in state. Components produce and consume events asynchronously.

### Key Principles
- Events are immutable facts about something that happened
- Producers don't know about consumers (decoupling)
- Asynchronous communication by default
- Event broker mediates delivery
- Eventually consistent

### ASCII Diagram
```
┌──────────┐    Event    ┌───────────┐    Event    ┌──────────┐
│ Producer │───────────▶│   Event   │───────────▶│ Consumer │
│  (Order  │            │   Broker  │            │(Shipping)│
│  Service)│            │(Kafka/SQS)│            │          │
└──────────┘            └───────────┘            └──────────┘
                              │
                              │  Event
                              ▼
                        ┌──────────┐
                        │ Consumer │
                        │(Billing) │
                        └──────────┘
```

### When to Use
- Real-time data processing
- Systems requiring high decoupling
- Event sourcing / audit trail requirements
- Fan-out scenarios (one event, many consumers)
- IoT and streaming data

### When NOT to Use
- Simple request-response CRUD
- When strong consistency is required
- When debugging simplicity is critical
- Small systems where overhead isn't justified

### Pros
- Extreme decoupling between producers and consumers
- High scalability and throughput
- Natural fit for real-time processing
- Easy to add new consumers without changing producers
- Built-in audit trail

### Cons
- Eventual consistency — hard to reason about
- Debugging is difficult (no clear call chain)
- Event ordering and deduplication challenges
- Requires robust event broker infrastructure
- Error handling complexity (dead letter queues)

### Real-world Examples
- **LinkedIn** — Kafka for activity streams
- **Uber** — real-time trip events
- **Netflix** — event-driven data pipeline
- **Trading platforms** — market event processing

---

## 7. Serverless Architecture

### Description
An execution model where the cloud provider dynamically manages the allocation of machine resources. Code is deployed as functions (FaaS) triggered by events, with no server management.

### Key Principles
- No server management (provider handles infrastructure)
- Pay-per-execution (no idle cost)
- Auto-scaling to zero and to peak
- Event-triggered functions
- Stateless compute (state stored externally)
- Composed of FaaS (Functions) + BaaS (Backend services)

### ASCII Diagram
```
                    ┌──────────────────────────┐
  HTTP Request ────▶│   API Gateway            │
                    └────────────┬─────────────┘
                                 │ trigger
                    ┌────────────▼─────────────┐
                    │    Lambda / Function      │
                    └────┬──────────┬───────────┘
                         │          │
              ┌──────────▼┐   ┌────▼──────────┐
              │ DynamoDB   │   │ S3 / Storage  │
              └────────────┘   └───────────────┘
```

### When to Use
- Sporadic / unpredictable workloads
- Event-driven processing (file uploads, webhooks)
- APIs with variable traffic
- Quick prototyping / MVPs
- Batch processing and scheduled tasks

### When NOT to Use
- Low-latency requirements (cold start problem)
- Long-running processes (> 15 min typically)
- Stateful applications
- High-throughput steady-state workloads (cost)
- Vendor lock-in concerns

### Pros
- Zero infrastructure management
- Auto-scales to zero (cost-efficient for low traffic)
- Fast time to market
- Built-in high availability
- Pay only for actual usage

### Cons
- Cold start latency
- Vendor lock-in
- Limited execution duration
- Debugging and local testing challenges
- Complex orchestration for multi-step workflows
- Observability gaps

### Real-world Examples
- **Coca-Cola** — vending machine backends on Lambda
- **iRobot** — IoT event processing
- **Nordstrom** — event-driven retail
- **Figma** — serverless for specific workloads

---

## 8. Peer-to-Peer Architecture

### Description
A distributed architecture where each node (peer) acts as both client and server, sharing resources directly without a central coordinating server.

### Key Principles
- No central server — all nodes are equal
- Each peer contributes and consumes resources
- Self-organizing network topology
- Decentralized control
- Resilient to individual node failures

### ASCII Diagram
```
    ┌──────┐         ┌──────┐
    │Peer A│◄───────▶│Peer B│
    └──┬───┘         └───┬──┘
       │    ╲         ╱   │
       │     ╲       ╱    │
       │      ╲     ╱     │
       │       ╲   ╱      │
    ┌──▼───┐    ╲ ╱    ┌──▼───┐
    │Peer D│◄────X────▶│Peer C│
    └──────┘    ╱ ╲    └──────┘
```

### When to Use
- File sharing (BitTorrent)
- Blockchain / cryptocurrency networks
- Video conferencing (WebRTC)
- Content distribution
- Decentralized applications

### When NOT to Use
- When central authority / control is needed
- Regulated environments requiring audit trails
- When peers are untrusted and security is paramount
- Applications requiring strong consistency

### Pros
- No single point of failure
- Scales naturally as peers join
- No server cost — resources are distributed
- Resilient to censorship

### Cons
- Security and trust challenges
- Inconsistent availability (peers go offline)
- Complex discovery and routing
- Freeloading problem (peers consuming without contributing)
- Difficult to manage and monitor

### Real-world Examples
- **BitTorrent** — file sharing
- **Bitcoin / Ethereum** — blockchain consensus
- **Skype** (original architecture)
- **IPFS** — decentralized file system
- **WebRTC** — browser-to-browser communication

---

## 9. Space-Based Architecture

### Description
Designed to address scalability and concurrency issues by removing the central database as a bottleneck. Data is replicated across in-memory grids, and processing units are self-contained.

### Key Principles
- In-memory data grids replace central database
- Processing units contain both logic and data
- Data replication across nodes for high availability
- No single database bottleneck
- Tuples/spaces for coordination (hence "space-based")

### ASCII Diagram
```
┌─────────────────────────────────────────────┐
│              Virtualized Middleware           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐    │
│  │Messaging│  │Data Grid│  │Processing│    │
│  │  Grid   │  │  Mgr    │  │  Grid    │    │
│  └─────────┘  └─────────┘  └─────────┘    │
└───────┬──────────────┬──────────────┬───────┘
        │              │              │
┌───────▼──────┐ ┌─────▼──────┐ ┌────▼───────┐
│Processing    │ │Processing  │ │Processing  │
│Unit 1        │ │Unit 2      │ │Unit 3      │
│┌────┐┌─────┐│ │┌────┐┌────┐│ │┌────┐┌────┐│
││Data││Logic ││ ││Data││Logic││ ││Data││Logic││
│└────┘└─────┘│ │└────┘└────┘│ │└────┘└────┘│
└──────────────┘ └────────────┘ └────────────┘
```

### When to Use
- High-volume, high-concurrency systems
- Trading platforms
- Online gaming backends
- Concert/event ticketing
- Systems with unpredictable spikes

### When NOT to Use
- Systems requiring strong data consistency
- Simple low-traffic applications
- Budget-constrained projects (infrastructure cost)
- Data-heavy analytical workloads

### Pros
- Extreme scalability (linear)
- Very low latency (in-memory)
- No database bottleneck
- Handles traffic spikes gracefully

### Cons
- Complex to implement and test
- Data consistency challenges (replication lag)
- High memory cost
- Not suitable for large datasets
- Difficult debugging

### Real-world Examples
- **GigaSpaces** — trading platforms
- **Hazelcast** — in-memory data grid
- **Concert ticketing systems** (Ticketmaster-style)
- **Online gaming** — real-time state management

---

## 10. Pipe-and-Filter Architecture

### Description
Decomposes processing into a series of independent steps (filters) connected by channels (pipes). Each filter transforms data and passes it to the next.

### Key Principles
- Each filter performs one transformation
- Filters are independent and reusable
- Pipes connect filters (data flows through)
- Filters don't know about adjacent filters
- Can be recombined in different orderings

### ASCII Diagram
```
┌─────┐    ┌────────┐    ┌────────┐    ┌────────┐    ┌──────┐
│Input│───▶│Filter 1│───▶│Filter 2│───▶│Filter 3│───▶│Output│
│     │pipe│Validate│pipe│Transform pipe│Enrich  │pipe│      │
└─────┘    └────────┘    └────────┘    └────────┘    └──────┘
```

### When to Use
- Data processing pipelines (ETL)
- Compiler design (lexer → parser → optimizer → code gen)
- Image/video processing
- Stream processing
- Unix command pipelines

### When NOT to Use
- Interactive applications requiring user feedback
- When filters need to share state
- When ordering is highly dynamic
- Low-latency request-response patterns

### Pros
- Simple to understand and compose
- Filters are reusable and testable in isolation
- Easy to add/remove/reorder steps
- Natural parallelism (pipeline parallel)

### Cons
- Overhead of data transformation between stages
- Not suitable for interactive systems
- Error handling across pipeline is complex
- Data format coupling between adjacent filters

### Real-world Examples
- **Unix pipes** (`cat file | grep "error" | sort | uniq`)
- **Apache Kafka Streams** — stream processing topology
- **ETL pipelines** (Spark, Airflow)
- **Compilers** (GCC, LLVM)

---

## 11. Hexagonal Architecture (Ports & Adapters)

### Description
Isolates the core application logic from external concerns (UI, database, messaging) using ports (interfaces) and adapters (implementations). The domain is at the center, with all dependencies pointing inward.

### Key Principles
- Domain logic at the center, free of external dependencies
- Ports define interfaces for communication (inbound and outbound)
- Adapters implement ports for specific technologies
- Dependencies always point inward
- Easily swap infrastructure without changing domain

### ASCII Diagram
```
         ┌─── Driving Adapters ───┐
         │  (REST, CLI, gRPC)     │
         └──────────┬─────────────┘
                    │ Inbound Port
         ┌──────────▼─────────────┐
         │                        │
         │    APPLICATION CORE    │
         │    (Domain Logic)      │
         │                        │
         └──────────┬─────────────┘
                    │ Outbound Port
         ┌──────────▼─────────────┐
         │  Driven Adapters       │
         │  (DB, Queue, HTTP)     │
         └────────────────────────┘
```

### When to Use
- Complex domain logic that must be testable
- Systems expected to change infrastructure over time
- When you want to defer technology decisions
- Applications requiring high testability

### When NOT to Use
- Simple CRUD applications
- Prototypes / throwaway code
- When the overhead of abstraction isn't justified

### Pros
- Domain logic is completely isolated and testable
- Easy to swap databases, frameworks, UIs
- Clear dependency direction
- Excellent testability (mock adapters)

### Cons
- More code (interfaces, adapters)
- Over-engineering for simple apps
- Learning curve for teams
- Can lead to excessive abstraction

### Real-world Examples
- **Netflix** — internal services architecture
- **Alistair Cockburn** — original author
- Common in **DDD-based Java/Kotlin** applications

---

## 12. Clean Architecture

### Description
Proposed by Robert C. Martin (Uncle Bob). Organizes code into concentric circles where inner circles know nothing about outer circles. Dependencies point inward.

### Key Principles
- Independence from frameworks
- Testable without UI, database, or external agency
- Independence from UI (UI can change without changing business rules)
- Independence from database
- Independence from any external agency
- Dependency Rule: source code dependencies point inward only

### ASCII Diagram
```
┌─────────────────────────────────────────┐
│  Frameworks & Drivers (outermost)       │
│  ┌───────────────────────────────────┐  │
│  │  Interface Adapters               │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │  Application Business Rules │  │  │
│  │  │  ┌───────────────────────┐  │  │  │
│  │  │  │  Enterprise Business  │  │  │  │
│  │  │  │  Rules (Entities)     │  │  │  │
│  │  │  └───────────────────────┘  │  │  │
│  │  └─────────────────────────────┘  │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘

Dependencies → → → (always point INWARD)
```

### Layers (inside out)
1. **Entities** — Enterprise-wide business rules
2. **Use Cases** — Application-specific business rules
3. **Interface Adapters** — Controllers, Presenters, Gateways
4. **Frameworks & Drivers** — Web, DB, UI, External interfaces

### When to Use
- Complex applications with rich business logic
- Long-lived systems expecting framework changes
- Applications requiring high testability
- When business rules must be independent of delivery mechanism

### When NOT to Use
- Simple CRUD apps or microservices with minimal logic
- Rapid prototyping
- Small scripts or utilities

### Pros
- Business rules are framework-independent
- Extremely testable
- Flexible — swap any outer layer
- Clear boundaries between concerns

### Cons
- Significant boilerplate
- Over-engineering for simple applications
- Steep learning curve
- Mapping between layers can be tedious

### Real-world Examples
- Widely adopted in **Android development** (Google recommended)
- **Enterprise Java** applications
- **Kotlin/Spring** backend services

---

## 13. Onion Architecture

### Description
Similar to Clean Architecture — organizes application into layers with the domain model at the core. All coupling is toward the center. Infrastructure is at the outermost ring.

### Key Principles
- Domain Model at the center
- Domain Services wrap the model
- Application Services orchestrate use cases
- Infrastructure is outermost (easily replaceable)
- All dependencies point inward

### ASCII Diagram
```
┌───────────────────────────────────┐
│  Infrastructure (DB, UI, APIs)    │
│  ┌─────────────────────────────┐  │
│  │  Application Services       │  │
│  │  ┌───────────────────────┐  │  │
│  │  │  Domain Services      │  │  │
│  │  │  ┌─────────────────┐  │  │  │
│  │  │  │  Domain Model   │  │  │  │
│  │  │  └─────────────────┘  │  │  │
│  │  └───────────────────────┘  │  │
│  └─────────────────────────────┘  │
└───────────────────────────────────┘
```

### When to Use
- Domain-rich applications
- When infrastructure may change
- .NET / enterprise applications
- Long-lived applications requiring maintainability

### When NOT to Use
- Simple data-driven applications
- Prototypes
- Applications with minimal business logic

### Pros / Cons
Similar to Clean Architecture. Primary difference is terminology and .NET ecosystem prevalence.

### Real-world Examples
- **Jeffrey Palermo** — original author
- Common in **.NET enterprise** applications
- **ASP.NET Core** projects following DDD

---

## 14. Domain-Driven Design (DDD)

### Description
Not just an architecture but a design approach that places the domain model at the center of software design. Strategic and tactical patterns for complex business domains.

### Key Principles

**Strategic Patterns:**
- Bounded Context — explicit boundary around a domain model
- Ubiquitous Language — shared language between devs and domain experts
- Context Mapping — relationships between bounded contexts
- Subdomains — Core, Supporting, Generic

**Tactical Patterns:**
- Entities — objects with identity
- Value Objects — objects defined by attributes
- Aggregates — cluster of entities with a root
- Domain Events — something significant that happened
- Repositories — persistence abstraction
- Domain Services — logic that doesn't belong to an entity
- Factories — complex object creation

### ASCII Diagram
```
┌─── Bounded Context: Orders ───┐   ┌─── Bounded Context: Shipping ──┐
│                                │   │                                 │
│  ┌──────────┐  ┌───────────┐  │   │  ┌──────────┐  ┌───────────┐  │
│  │  Order   │  │ LineItem  │  │   │  │ Shipment │  │  Package  │  │
│  │(Aggregate│  │(Entity)   │  │   │  │(Aggregate│  │(Entity)   │  │
│  │  Root)   │  │           │  │   │  │  Root)   │  │           │  │
│  └──────────┘  └───────────┘  │   │  └──────────┘  └───────────┘  │
│                                │   │                                 │
└────────────────────────────────┘   └─────────────────────────────────┘
              │                                    ▲
              │         Context Map                 │
              └──── (Anti-corruption Layer) ───────┘
```

### When to Use
- Complex domains with rich business rules
- When close collaboration with domain experts is possible
- Large systems with multiple teams
- When the domain IS the competitive advantage

### When NOT to Use
- Simple CRUD applications
- Technical/infrastructure projects
- When domain experts aren't available
- Small, well-understood domains

### Pros
- Software reflects the business accurately
- Shared language reduces miscommunication
- Clear boundaries enable team autonomy
- Handles complexity gracefully

### Cons
- High learning curve
- Requires domain expert involvement
- Over-engineering for simple domains
- Upfront investment in modeling

### Real-world Examples
- **Amazon** — order, payment, shipping as bounded contexts
- **Uber** — ride, driver, payment domains
- **DDD community** — Eric Evans, Vaughn Vernon

---

## 15. CQRS Architecture

### Description
Command Query Responsibility Segregation — separates the read model from the write model. Commands (writes) and Queries (reads) use different models, potentially different databases.

### Key Principles
- Commands change state (write side)
- Queries read state (read side)
- Separate models optimized for their purpose
- Often paired with Event Sourcing
- Eventual consistency between write and read models

### ASCII Diagram
```
              ┌──────────────────────┐
              │      Client          │
              └───┬──────────────┬───┘
                  │              │
         Command  │              │  Query
                  ▼              ▼
         ┌────────────┐  ┌────────────┐
         │   Write    │  │   Read     │
         │   Model    │  │   Model    │
         └─────┬──────┘  └──────▲─────┘
               │                 │
               │    Events       │  Projection
               └────────────────▶┘
               │
         ┌─────▼──────┐  ┌────────────┐
         │ Write DB   │  │  Read DB   │
         │(Normalized)│  │(Denormalized│
         └────────────┘  └────────────┘
```

### When to Use
- Read/write ratio is heavily skewed (many more reads)
- Complex domain requiring different read vs write models
- When read and write performance must be optimized independently
- Event-sourced systems

### When NOT to Use
- Simple domains with balanced read/write
- When eventual consistency is unacceptable
- Small applications (overhead not justified)
- CRUD-heavy apps with simple queries

### Pros
- Independent scaling of reads and writes
- Optimized read models (materialized views)
- Simpler commands and queries (single responsibility)
- Natural fit with event sourcing

### Cons
- Increased complexity
- Eventual consistency
- Data synchronization between models
- More infrastructure to manage

### Real-world Examples
- **Axon Framework** (Java CQRS/ES framework)
- **Event Store** — Greg Young's event sourcing database
- **Banking systems** — write ledger vs read balance views
- **E-commerce** — order writes vs product catalog reads

---

## 16. Actor Model Architecture

### Description
A concurrency model where "actors" are the fundamental unit of computation. Each actor has private state, communicates only through asynchronous messages, and can create new actors.

### Key Principles
- Everything is an actor
- Actors communicate only via asynchronous messages
- Each actor processes one message at a time (no concurrency within actor)
- Actors have private, encapsulated state
- Actors can create child actors (supervision hierarchy)
- Location transparency — actors can be local or remote

### ASCII Diagram
```
┌─────────┐  message  ┌─────────┐  message  ┌─────────┐
│ Actor A │──────────▶│ Actor B │──────────▶│ Actor C │
│(private │           │(private │           │(private │
│ state)  │◀──────────│ state)  │           │ state)  │
└─────────┘  response └────┬────┘           └─────────┘
                           │ creates
                      ┌────▼────┐
                      │ Actor D │
                      │ (child) │
                      └─────────┘
```

### When to Use
- Highly concurrent / distributed systems
- Real-time systems (IoT, gaming, telecom)
- Systems requiring fault tolerance (let-it-crash)
- When shared mutable state is a problem

### When NOT to Use
- Simple sequential applications
- When synchronous request-response is sufficient
- Small-scale applications
- Teams unfamiliar with actor model concepts

### Pros
- No shared state — eliminates race conditions
- Natural distribution (location transparency)
- Fault tolerance through supervision trees
- Scales to millions of concurrent actors

### Cons
- Different programming paradigm (learning curve)
- Debugging message flows is complex
- Mailbox overflow potential
- Ordering guarantees only per actor pair

### Real-world Examples
- **WhatsApp** — Erlang/BEAM (2M connections per server)
- **Discord** — Elixir for real-time messaging
- **Microsoft Orleans** — virtual actor framework (.NET)
- **Akka** (Scala/Java) — used by LinkedIn, PayPal

---

## 17. Micro-frontend Architecture

### Description
Extends microservices to the frontend. Each team owns a vertical slice of the application including its UI, composed into a single user-facing application.

### Key Principles
- Independent teams own end-to-end features (including UI)
- Each micro-frontend is independently deployable
- Technology agnostic (React, Vue, Angular can coexist)
- Isolated — no shared runtime state
- Composed at build time or runtime

### ASCII Diagram
```
┌─────────────────────────────────────────────┐
│              App Shell / Container           │
├────────────┬────────────┬───────────────────┤
│  MFE:      │  MFE:      │  MFE:            │
│  Product   │  Cart      │  Account         │
│  (React)   │  (Vue)     │  (Angular)       │
│            │            │                   │
│  Team A    │  Team B    │  Team C          │
└────────────┴────────────┴───────────────────┘
```

### Composition Strategies
- **Build-time**: npm packages composed at build
- **Runtime via iframes**: simple isolation
- **Runtime via JavaScript**: Module Federation (Webpack 5)
- **Server-side**: SSI, Edge-side Includes
- **Web Components**: framework-agnostic

### When to Use
- Large organizations with many frontend teams
- When different teams need technology freedom
- Independent deployment of UI features
- Legacy migration (strangle fig pattern for frontend)

### When NOT to Use
- Small teams / single frontend team
- When consistent UX is critical and hard to enforce
- Simple applications
- When bundle size is critical

### Pros
- Team autonomy and independent deployments
- Technology diversity
- Incremental upgrades / migration
- Smaller, focused codebases

### Cons
- Increased page load / bundle size
- UX consistency challenges
- Shared dependency management
- Complex routing and communication between MFEs
- Testing integration points

### Real-world Examples
- **IKEA** — Module Federation
- **Spotify** — iframes (desktop app)
- **Zalando** — Project Mosaic
- **DAZN** — micro-frontend platform

---

## 18. Cell-Based Architecture

### Description
An evolution of microservices where services are grouped into self-contained "cells." Each cell is independently deployable, has its own data store, API gateway, and can function autonomously.

### Key Principles
- Cell = a group of related microservices + data + gateway
- Cells communicate via well-defined APIs
- Each cell is independently scalable and deployable
- Cell boundary acts as a blast radius limiter
- Cells can be replicated across regions

### ASCII Diagram
```
┌──── Cell: Orders ─────────────┐  ┌──── Cell: Payments ───────────┐
│  ┌─────────┐                  │  │  ┌─────────┐                  │
│  │  Cell   │                  │  │  │  Cell   │                  │
│  │ Gateway │                  │  │  │ Gateway │                  │
│  └────┬────┘                  │  │  └────┬────┘                  │
│       │                       │  │       │                       │
│  ┌────▼───┐  ┌───────────┐   │  │  ┌────▼───┐  ┌───────────┐   │
│  │Order   │  │ Inventory │   │  │  │Payment │  │  Ledger   │   │
│  │Service │  │  Service  │   │  │  │Service │  │  Service  │   │
│  └────────┘  └───────────┘   │  │  └────────┘  └───────────┘   │
│  ┌────────────────────────┐  │  │  ┌────────────────────────┐   │
│  │      Cell Database     │  │  │  │      Cell Database     │   │
│  └────────────────────────┘  │  │  └────────────────────────┘   │
└───────────────────────────────┘  └───────────────────────────────┘
```

### When to Use
- Very large systems (hundreds of services)
- Multi-region deployments
- When blast radius containment is critical
- Organizations with many autonomous teams

### When NOT to Use
- Small to medium applications
- When inter-cell communication is very frequent
- Early-stage products

### Pros
- Clear blast radius and failure isolation
- Independent scaling per cell
- Regional deployment flexibility
- Team ownership clarity

### Cons
- Overhead of cell-level infrastructure (gateways, DBs)
- Cross-cell transactions are complex
- Can lead to code duplication across cells
- Operational complexity

### Real-world Examples
- **AWS** — internal architecture (cells for availability zones)
- **WSO2** — cell-based architecture reference
- **Large banks** — regional cell deployments

---

## 19. Modular Monolith

### Description
A monolithic application that is well-structured into independent modules with clear boundaries. Combines the simplicity of monolithic deployment with the organizational benefits of modularity.

### Key Principles
- Single deployment unit (like a monolith)
- Strict module boundaries (like microservices)
- Modules communicate through well-defined interfaces
- Each module owns its data (separate schema/tables)
- No circular dependencies between modules
- Easier to extract into microservices later

### ASCII Diagram
```
┌─────────────────────────────────────────┐
│            Single Deployment            │
│  ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │  Orders  │ │  Users   │ │Payments│  │
│  │  Module  │ │  Module  │ │ Module │  │
│  │          │ │          │ │        │  │
│  │ ┌──────┐ │ │ ┌──────┐ │ │┌──────┐│  │
│  │ │ DB   │ │ │ │ DB   │ │ ││ DB   ││  │
│  │ │Schema│ │ │ │Schema│ │ ││Schema││  │
│  │ └──────┘ │ │ └──────┘ │ │└──────┘│  │
│  └──────────┘ └──────────┘ └────────┘  │
│         Public APIs only between        │
│              modules                    │
└─────────────────────────────────────────┘
```

### When to Use
- When microservices overhead isn't justified yet
- Medium-sized teams wanting structure
- As a stepping stone toward microservices
- When you want module isolation without distributed system pain

### When NOT to Use
- When independent scaling/deployment is critical now
- When teams need technology diversity
- Very simple applications (over-engineering)

### Pros
- Simplicity of monolithic deployment
- Clear boundaries and ownership
- Easy to refactor to microservices later
- No network calls between modules
- ACID transactions across modules (same DB)

### Cons
- Still a single deployment (all-or-nothing)
- Requires discipline to maintain boundaries
- Can degrade back into a big ball of mud
- Single technology stack

### Real-world Examples
- **Shopify** — modular monolith with clear component boundaries
- **Gusto** — moved from microservices back to modular monolith
- **Basecamp/Hey** — Rails modular monolith

---

## 20. Service Mesh Architecture

### Description
A dedicated infrastructure layer that handles service-to-service communication. Implemented as sidecar proxies alongside each service instance, managing traffic, security, and observability transparently.

### Key Principles
- Sidecar proxy deployed alongside each service
- Handles cross-cutting concerns (mTLS, retries, circuit breaking)
- Control plane manages configuration
- Data plane handles actual traffic
- Application code is unaware of the mesh

### ASCII Diagram
```
┌─── Control Plane (Istiod) ────────────────┐
│  Config │ Discovery │ Certificate Mgmt    │
└────────────────────┬──────────────────────┘
                     │ pushes config
         ┌───────────┼───────────┐
         ▼           ▼           ▼
┌────────────┐ ┌────────────┐ ┌────────────┐
│┌──────────┐│ │┌──────────┐│ │┌──────────┐│
││  Sidecar ││ ││  Sidecar ││ ││  Sidecar ││
││  (Envoy) ││ ││  (Envoy) ││ ││  (Envoy) ││
│└─────┬────┘│ │└─────┬────┘│ │└─────┬────┘│
│      │     │ │      │     │ │      │     │
│┌─────▼────┐│ │┌─────▼────┐│ │┌─────▼────┐│
││ Service A││ ││ Service B││ ││ Service C││
│└──────────┘│ │└──────────┘│ │└──────────┘│
└────────────┘ └────────────┘ └────────────┘
     Data Plane (sidecar proxies)
```

### When to Use
- Large microservices deployments (50+ services)
- When mTLS between all services is required
- Complex traffic management (canary, A/B, mirroring)
- When you want observability without code changes
- Multi-language/polyglot environments

### When NOT to Use
- Small number of services (< 10)
- When latency overhead of proxy hop is unacceptable
- Simple architectures that don't need mesh features
- Teams without Kubernetes expertise

### Pros
- Cross-cutting concerns handled without code changes
- Consistent security (mTLS everywhere)
- Rich observability (distributed tracing, metrics)
- Advanced traffic management
- Language-agnostic

### Cons
- Significant operational complexity
- Added latency (proxy hop)
- Resource overhead (sidecar per pod)
- Steep learning curve
- Debugging through proxies is harder

### Real-world Examples
- **Istio** — most popular, backed by Google
- **Linkerd** — lightweight alternative (CNCF)
- **Consul Connect** — HashiCorp
- **AWS App Mesh**
- **Airbnb, eBay, Lyft** — early adopters

---

## 21. Choreography vs Orchestration

### Description
Two approaches to coordinating distributed workflows across services.

### Choreography
Each service reacts to events independently. No central coordinator — services know what to do when they receive an event.

### Orchestration
A central orchestrator directs the workflow, telling each service what to do and when.

### ASCII Diagrams

**Choreography:**
```
┌─────────┐  OrderCreated  ┌──────────┐  PaymentDone  ┌──────────┐
│  Order  │───────────────▶│ Payment  │──────────────▶│ Shipping │
│ Service │                │ Service  │               │ Service  │
└─────────┘                └──────────┘               └──────────┘
     │                                                      │
     │              ShipmentSent                             │
     └◀─────────────────────────────────────────────────────┘
```

**Orchestration:**
```
                    ┌──────────────┐
                    │ Orchestrator │
                    │  (Saga Mgr)  │
                    └──┬───┬───┬──┘
          1. Create    │   │   │    3. Ship
          Payment      │   │   │
         ┌─────────────┘   │   └─────────────┐
         ▼                 │                  ▼
┌──────────────┐     2. Reserve      ┌──────────────┐
│   Payment    │       Stock         │   Shipping   │
│   Service    │           │         │   Service    │
└──────────────┘     ┌─────▼──────┐  └──────────────┘
                     │ Inventory  │
                     │  Service   │
                     └────────────┘
```

### Comparison

| Aspect | Choreography | Orchestration |
|--------|-------------|---------------|
| Coupling | Low (event-driven) | Higher (orchestrator knows all) |
| Visibility | Hard to track flow | Central view of workflow |
| Single point of failure | No | Orchestrator is one |
| Complexity | Distributed (harder to debug) | Centralized (easier to follow) |
| Adding steps | Just subscribe to events | Modify orchestrator |
| Error handling | Each service handles own | Centralized compensation |

### When to Use Choreography
- Simple workflows with few steps
- When extreme decoupling is needed
- Event-driven systems

### When to Use Orchestration
- Complex workflows with many steps
- When visibility and control are important
- Saga pattern implementations (compensating transactions)

### Real-world Examples
- **Choreography**: Event-driven e-commerce (Kafka-based)
- **Orchestration**: Netflix Conductor, Uber Cadence, Temporal.io, AWS Step Functions

---

## 22. Broker Architecture

### Description
A middleware pattern where a broker component mediates communication between distributed components. The broker handles location, routing, and protocol translation.

### Key Principles
- Broker mediates all communication
- Clients and servers register with broker
- Location transparency — clients don't know server locations
- Protocol bridging between heterogeneous systems
- Can include load balancing and failover

### ASCII Diagram
```
┌────────┐           ┌────────────┐           ┌────────┐
│Client 1│──────────▶│            │──────────▶│Server A│
└────────┘           │            │           └────────┘
┌────────┐           │   BROKER   │           ┌────────┐
│Client 2│──────────▶│            │──────────▶│Server B│
└────────┘           │ (routing,  │           └────────┘
┌────────┐           │  discovery,│           ┌────────┐
│Client 3│──────────▶│  balancing)│──────────▶│Server C│
└────────┘           └────────────┘           └────────┘
```

### When to Use
- Distributed systems needing location transparency
- Message-oriented middleware
- When clients shouldn't know about server topology
- Heterogeneous system integration

### When NOT to Use
- When direct communication is simpler
- Latency-sensitive systems (broker adds hop)
- When broker becomes a bottleneck

### Pros
- Location transparency
- Dynamic server registration/deregistration
- Load balancing and failover built-in
- Decouples clients from servers

### Cons
- Broker is a single point of failure
- Added latency
- Complexity of broker implementation
- Can become a bottleneck

### Real-world Examples
- **RabbitMQ, ActiveMQ** — message brokers
- **CORBA** — Object Request Broker
- **Apache Kafka** — distributed streaming broker
- **Kubernetes Service** — acts as a broker (kube-proxy)

---

## 23. Blackboard Architecture

### Description
A pattern where multiple specialized subsystems (knowledge sources) collaboratively build a solution on a shared data structure (blackboard). A controller decides which knowledge source to activate next.

### Key Principles
- Shared workspace (blackboard) holds the current state of the solution
- Knowledge sources are independent experts that read/write to the blackboard
- Controller selects which knowledge source to activate
- Iterative refinement until solution is found
- Non-deterministic — solution emerges from collaboration

### ASCII Diagram
```
┌──────────────────────────────────────┐
│           BLACKBOARD                 │
│    (shared problem-solving state)    │
└───┬──────────┬──────────┬───────────┘
    │          │          │
    ▼          ▼          ▼
┌───────┐ ┌───────┐ ┌───────┐
│ KS 1  │ │ KS 2  │ │ KS 3  │  ← Knowledge Sources
│(Speech│ │(NLP   │ │(Intent│
│ Recog)│ │Parser)│ │ Match)│
└───────┘ └───────┘ └───────┘
         ┌───────┐
         │Control│ ← Decides which KS to activate
         └───────┘
```

### When to Use
- Problems with no deterministic solution strategy
- AI/ML pipelines combining multiple models
- Speech recognition, image understanding
- Complex decision-making systems

### When NOT to Use
- Well-defined algorithmic problems
- Simple sequential processing
- When deterministic behavior is required

### Pros
- Supports complex problem-solving with multiple strategies
- Knowledge sources are independent and reusable
- Flexible — add new knowledge sources without changing others
- Good for AI/ML ensemble approaches

### Cons
- Difficult to test and debug
- Non-deterministic behavior
- Control strategy is complex
- Performance overhead of shared state

### Real-world Examples
- **Speech recognition systems** (Hearsay-II)
- **AI planning systems**
- **Multi-model ML inference pipelines**
- **Autonomous vehicle perception** (fusing sensor data)

---

## 24. Component-Based Architecture

### Description
Builds software from pre-built, reusable, self-contained components with well-defined interfaces. Components can be assembled, replaced, and composed to form applications.

### Key Principles
- Components are self-contained units with defined interfaces
- Reusability across applications
- Substitutability — components can be swapped
- Encapsulation — internal implementation is hidden
- Composability — components can be combined

### ASCII Diagram
```
┌─────────────────────────────────────┐
│           Application               │
│                                     │
│  ┌──────────┐  ┌──────────┐        │
│  │  Auth    │  │  Logger  │        │
│  │Component │  │Component │        │
│  └──────────┘  └──────────┘        │
│  ┌──────────┐  ┌──────────┐        │
│  │  Payment │  │  Email   │        │
│  │Component │  │Component │        │
│  └──────────┘  └──────────┘        │
│                                     │
│  Components interact via interfaces │
└─────────────────────────────────────┘
```

### When to Use
- Building applications from reusable parts
- UI frameworks (React components, Web Components)
- Enterprise applications with shared business components
- When standardization and reuse are priorities

### When NOT to Use
- Highly custom one-off systems
- When component boundaries are unclear
- Simple scripts or utilities

### Pros
- Reusability reduces development time
- Independent development and testing
- Easy to replace/upgrade individual components
- Promotes consistency

### Cons
- Designing good component interfaces is hard
- Over-abstraction risk
- Version management across consumers
- May not fit every problem perfectly

### Real-world Examples
- **React / Vue / Angular** — UI component architectures
- **Java EE / Spring** — enterprise components (EJBs, Beans)
- **OSGi** — Java module system
- **npm packages** — reusable Node.js components

---

## 25. Plugin Architecture

### Description
A core system provides basic functionality, with extension points where plugins can add features. The core defines contracts; plugins implement them to extend behavior without modifying the core.

### Key Principles
- Core system provides minimal functionality + extension points
- Plugins conform to a defined interface/contract
- Plugins are independently developed and deployed
- Core doesn't depend on any specific plugin
- Hot-swappable — add/remove plugins at runtime

### ASCII Diagram
```
┌─────────────────────────────────────────┐
│              Core System                 │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │    Plugin Registry / Loader       │  │
│  └────┬──────────┬──────────┬───────┘  │
│       │          │          │           │
└───────┼──────────┼──────────┼───────────┘
        ▼          ▼          ▼
  ┌──────────┐ ┌──────────┐ ┌──────────┐
  │ Plugin A │ │ Plugin B │ │ Plugin C │
  │(PDF      │ │(CSV      │ │(Charts)  │
  │ Export)  │ │ Import)  │ │          │
  └──────────┘ └──────────┘ └──────────┘
```

### When to Use
- Products that need extensibility by third parties
- When core must remain stable but features evolve
- IDE/editor architecture
- When different customers need different features

### When NOT to Use
- Simple applications without extensibility needs
- When plugin API stability is hard to guarantee
- Systems where all features are mandatory

### Pros
- Highly extensible without modifying core
- Third-party ecosystem possible
- Features can be toggled per customer
- Core remains simple and stable

### Cons
- Plugin API design is critical and hard to change
- Security risks from third-party plugins
- Version compatibility challenges
- Testing plugin interactions is complex

### Real-world Examples
- **VS Code** — extension marketplace
- **WordPress** — plugin ecosystem
- **Eclipse IDE** — everything is a plugin
- **Webpack** — loader/plugin system
- **Grafana** — datasource and panel plugins
- **Chrome extensions**

---

## Architecture Decision Matrix

| Architecture | Complexity | Scalability | Team Size | Best For |
|-------------|-----------|-------------|-----------|----------|
| Monolith | Low | Low | Small | MVPs, startups |
| Layered | Low | Medium | Small-Med | Enterprise CRUD |
| Microservices | High | High | Large | Complex domains |
| SOA | High | Medium | Large | Enterprise integration |
| Event-Driven | High | High | Medium-Large | Real-time, streaming |
| Serverless | Medium | High | Small-Med | Sporadic workloads |
| Modular Monolith | Medium | Medium | Medium | Structured monolith |
| CQRS | High | High | Medium | Read-heavy systems |
| Hexagonal/Clean | Medium | - | Any | Testable domain logic |
| Service Mesh | Very High | High | Large | 50+ microservices |
| Cell-Based | Very High | Very High | Very Large | Global-scale systems |

---

## Evolution Path

Most systems evolve through these stages:

```
Monolith → Modular Monolith → Microservices → Cell-Based
                                     ↓
                              + Service Mesh
                              + Event-Driven
                              + CQRS where needed
```

---

*Next: [02-microservices-fundamentals.md](./02-microservices-fundamentals.md)*
