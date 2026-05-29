# Service Decomposition Patterns

## Decompose by Business Capability

### Problem
How to decompose a monolith into services when you don't know where to draw boundaries.

### Solution
Identify business capabilities (what the business does) and create one service per capability. Business capabilities are stable — they change less frequently than organizational structure or technology.

Examples: Order Management, Inventory, Billing, Shipping, Customer Management, Product Catalog.

### Implementation Steps
1. Map the organization's business capabilities (value stream mapping)
2. Identify top-level capabilities and sub-capabilities
3. Each capability becomes a candidate service
4. Validate: does each capability have its own data? Its own team?
5. Iterate — merge or split as understanding improves

### Trade-offs
| Pros | Cons |
|---|---|
| Stable boundaries (business rarely restructures capabilities) | Requires deep domain understanding |
| Aligns with organizational structure | May produce services that are too coarse initially |
| Clear ownership | Cross-cutting concerns span multiple capabilities |

### Real-world Example
An e-commerce platform decomposes into: Product Catalog Service, Order Service, Payment Service, Shipping Service, Customer Service, Notification Service.

### When to Use
- Domain is well understood
- Organization has clear business units
- Teams can be aligned to capabilities

### When NOT to Use
- Greenfield project with unclear domain
- Very small team (< 5 engineers)
- Domain is still being discovered

---

## Decompose by Subdomain (DDD Approach)

### Problem
Business capabilities are too coarse or the domain has complex interactions that need careful modeling.

### Solution
Apply Domain-Driven Design. Identify core, supporting, and generic subdomains. Each subdomain maps to a bounded context, which maps to a service.

- **Core subdomains**: Competitive advantage; build in-house with best engineers
- **Supporting subdomains**: Necessary but not differentiating; build or outsource
- **Generic subdomains**: Solved problems; buy off-the-shelf (auth, email, payments)

### Implementation Steps
1. Run Event Storming or Domain Storytelling workshops with domain experts
2. Identify domain events, commands, aggregates
3. Cluster related concepts into bounded contexts
4. Classify each as core/supporting/generic
5. Define context map (relationships between contexts)
6. Implement each bounded context as a service

### Trade-offs
| Pros | Cons |
|---|---|
| Precise boundaries based on domain model | Requires DDD expertise |
| Handles complex domains well | Time-intensive discovery process |
| Reduces coupling through explicit relationships | May over-engineer simple domains |

### Real-world Example
Insurance company: Policy Issuance (core), Claims Processing (core), Document Generation (supporting), Identity Verification (generic — use third-party).

### When to Use
- Complex domains with many business rules
- Domain experts are available for workshops
- Long-lived product (investment in modeling pays off)

### When NOT to Use
- Simple CRUD applications
- Domains with very little business logic
- Team lacks DDD knowledge and can't invest in learning

---

## Decompose by Transactions

### Problem
Some operations span multiple business capabilities but require transactional guarantees.

### Solution
Group operations that must be strongly consistent into the same service. Accept eventual consistency across service boundaries.

### Implementation Steps
1. Identify operations that require ACID guarantees
2. Group tightly coupled transactional operations into one service
3. Use sagas for operations that can tolerate eventual consistency
4. Distinguish between "must be consistent" vs "should be consistent eventually"

### Trade-offs
| Pros | Cons |
|---|---|
| Avoids distributed transactions | May create larger services |
| Simplifies consistency model | Transaction boundaries may not align with business boundaries |
| Better performance (no 2PC) | Can lead to coupled domains within a service |

### Real-world Example
Banking: Transfer between accounts in the same bank → single service. Transfer between banks → saga with compensation.

### When to Use
- Strong consistency requirements for specific operations
- Regulatory requirements demand transactional integrity
- Performance-critical paths that can't afford saga overhead

### When NOT to Use
- When eventual consistency is acceptable (most cases)
- When it forces unrelated concepts into one service

---

## Strangler Fig Pattern

### Problem
How to migrate from monolith to microservices incrementally without a risky big-bang rewrite.

### Solution
Named after the strangler fig tree that grows around a host tree and eventually replaces it. Gradually replace specific pieces of functionality with new services, routing traffic from the old to the new system incrementally.

```
         ┌──────────────┐
         │   Proxy/     │
         │   Router     │
         └──┬───────┬───┘
            │       │
   ┌────────▼──┐  ┌─▼────────┐
   │ New       │  │ Monolith  │
   │ Service   │  │ (shrinks) │
   └───────────┘  └───────────┘
```

### Implementation Steps
1. Identify a module to extract (start with something low-risk)
2. Place a proxy/facade in front of the monolith
3. Build the new service implementing the same functionality
4. Route traffic to new service (canary → percentage → full)
5. Remove the old code from the monolith
6. Repeat for next module

### Trade-offs
| Pros | Cons |
|---|---|
| Zero big-bang risk | Longer overall migration time |
| Can stop/pause at any point | Running two systems increases complexity temporarily |
| Proves value incrementally | Need to maintain proxy/routing layer |
| Learn from each extraction | Data synchronization between old and new |

### Real-world Example
Amazon migrated from a monolithic bookstore to microservices over years using this pattern. Each team extracted their domain into a service while the monolith continued serving traffic.

### When to Use
- Existing monolith that must remain operational during migration
- Team wants to prove microservices value before committing fully
- Risk-averse organization

### When NOT to Use
- Greenfield project (no monolith to strangle)
- Monolith is so poorly structured that extraction is impossible without refactoring first
- Timeline pressure requires faster approaches

---

## Anti-Corruption Layer (ACL)

### Problem
When integrating with a legacy system or external service whose model would corrupt your clean domain model.

### Solution
Create a translation layer that converts between the external model and your internal model. Prevents leaking of legacy/external concepts into your domain.

```
┌─────────────┐    ┌─────────────────────┐    ┌──────────────┐
│ Your Domain │◄──►│ Anti-Corruption Layer│◄──►│ Legacy/External│
│   Model     │    │  (Translator)        │    │   System      │
└─────────────┘    └─────────────────────┘    └──────────────┘
```

### Implementation Steps
1. Define your clean domain model independently
2. Create adapter/translator classes that map between models
3. Use facades to simplify the external system's interface
4. All communication with the external system goes through the ACL
5. Write tests that verify translation correctness

### Trade-offs
| Pros | Cons |
|---|---|
| Isolates your domain from external pollution | Extra layer to maintain |
| Can evolve independently from legacy | Translation has performance cost |
| Clear separation of concerns | Can become complex if models differ significantly |

### Real-world Example
New order service integrating with legacy ERP. The ERP uses "Sales Document" with 200 fields; your domain uses "Order" with 15 fields. ACL translates between them.

### When to Use
- Integrating with legacy systems you can't change
- External API model conflicts with your domain model
- During migration (temporary ACL between old and new)

### When NOT to Use
- Models are already aligned
- Simple pass-through with no translation needed
- Tight deadline and the integration is temporary/throwaway

---

## Branch by Abstraction

### Problem
Need to replace a component within a monolith without stopping feature development or creating a long-lived branch.

### Solution
Introduce an abstraction (interface) over the component to be replaced. Build the new implementation behind the abstraction. Switch traffic gradually. Remove the old implementation.

### Implementation Steps
1. Create an abstraction (interface/trait) over the existing implementation
2. Modify all callers to use the abstraction (no behavior change yet)
3. Build new implementation behind the same abstraction
4. Use feature flags to route traffic to new vs old
5. When confident, remove old implementation and the abstraction (if unnecessary)

### Trade-offs
| Pros | Cons |
|---|---|
| No long-lived feature branches | Temporary increase in code complexity |
| Safe, incremental replacement | Requires discipline to clean up |
| Can run both implementations simultaneously | Abstraction may be imperfect |
| Works within a monolith | Not all components can be easily abstracted |

### Real-world Example
Replacing an in-house ORM with Hibernate: create a `Repository` interface, implement it with both ORMs, feature-flag the switch, remove old ORM.

### When to Use
- Replacing internal components within a codebase
- Team wants trunk-based development (no long branches)
- Component has many callers

### When NOT to Use
- Replacing an external system (use Strangler Fig instead)
- Component is already well-abstracted
- One-shot replacement is low risk

---

## Parallel Run Pattern

### Problem
Need confidence that a new service produces correct results before switching traffic.

### Solution
Run both old and new implementations simultaneously. Send requests to both, compare results, but only return the old system's response to users. Once the new system's results consistently match, switch over.

### Implementation Steps
1. Deploy new service alongside old
2. Route all requests to both (or replay production traffic to new)
3. Compare outputs (use a comparator service or log diffs)
4. Investigate and fix discrepancies in the new system
5. Once parity is achieved, switch traffic to new system
6. Decommission old system

### Trade-offs
| Pros | Cons |
|---|---|
| High confidence in correctness | Doubles resource usage during parallel run |
| Catches edge cases before go-live | Side effects must be carefully handled (don't charge twice!) |
| Data-driven decision to switch | Comparison logic can be complex |

### Real-world Example
GitHub used this when migrating from MySQL to a new backend — "Scientist" library ran both code paths and reported differences without affecting users.

### When to Use
- Critical systems where correctness is paramount (payments, billing)
- Complex logic that's hard to verify with tests alone
- Regulatory environments requiring proof of equivalence

### When NOT to Use
- Side-effectful operations that can't be safely duplicated
- Simple services where unit/integration tests suffice
- Cost constraints prevent running duplicate infrastructure

---

## Decorating Collaborator Pattern

### Problem
Need to add behavior to an existing service without modifying it (e.g., triggering notifications after an order is placed).

### Solution
Place a decorator/proxy in front of or after the existing service that adds the new behavior. The original service remains unchanged.

### Implementation Steps
1. Identify the new behavior to add (e.g., send email after order creation)
2. Create a decorator service that intercepts requests/responses
3. Decorator calls the original service, then performs additional actions
4. Route traffic through the decorator instead of directly to the service
5. Original service is unaware of the decoration

### Trade-offs
| Pros | Cons |
|---|---|
| Open/Closed Principle — extend without modifying | Adds network hop and latency |
| Original service stays simple | Can create confusing service chains |
| Easy to add/remove decorations | Debugging becomes harder |

### Real-world Example
Order service creates orders. A decorator service intercepts the response, and if successful, publishes an event to trigger loyalty points calculation and email notification — without modifying the order service.

### When to Use
- Adding cross-cutting concerns (audit, notifications)
- You can't or don't want to modify the original service
- Behavior is optional or experimental

### When NOT to Use
- Core business logic that belongs inside the service
- When it creates unclear ownership of behavior
- Performance-critical paths where extra hop matters

---

## Domain-Driven Design Strategic Patterns

### Bounded Context

**Problem**: Same terms mean different things to different parts of the organization.

**Solution**: Define explicit boundaries where a model applies. Within a boundary, language is consistent.

**Example**: "Product" in Catalog context (title, description, images) vs "Product" in Warehouse context (SKU, weight, shelf location).

---

### Context Map

**Problem**: Need to understand and manage relationships between bounded contexts.

**Solution**: Draw a map showing all bounded contexts and the relationships between them (upstream/downstream, partnership, shared kernel, etc.).

**Implementation**: Document as a diagram. Review regularly. Types of relationships:

```
┌────────┐  Partnership  ┌────────┐
│Context A├──────────────►│Context B│
└────────┘               └────────┘

┌────────┐  Customer     ┌────────┐
│Upstream ├──Supplier────►│Downstream│
└────────┘               └────────┘
```

---

### Shared Kernel

**Problem**: Two contexts need to share a small subset of the model.

**Solution**: Agree on a shared subset (code/schema) that both teams co-own. Changes require agreement from both.

**Trade-offs**:
- Pro: Reduces duplication for tightly related concepts
- Con: Coupling — changes require coordination
- Con: Can grow uncontrollably

**When to use**: Closely collaborating teams with genuinely shared concepts (e.g., Money value object).

**When NOT to use**: Teams that deploy independently; when the "shared" part keeps growing.

---

### Customer-Supplier

**Problem**: Downstream service depends on upstream service's data/API.

**Solution**: Upstream (supplier) and downstream (customer) have an explicit relationship. Downstream's needs influence upstream's priorities.

**Implementation**: Consumer-driven contract testing. Upstream team prioritizes downstream needs in their backlog.

**When to use**: Clear dependency direction; downstream team has leverage.

**When NOT to use**: Upstream team won't accommodate (use Conformist or ACL instead).

---

### Conformist

**Problem**: Downstream depends on upstream, but upstream has no incentive to accommodate downstream's needs.

**Solution**: Downstream conforms to upstream's model as-is. No translation, no influence.

**Trade-offs**:
- Pro: Simple — no translation layer
- Con: Upstream's model leaks into your domain
- Con: You're at the mercy of upstream changes

**When to use**: Integrating with a dominant platform (e.g., using Salesforce's model as-is).

**When NOT to use**: When upstream's model would significantly corrupt your domain.

---

### Anti-Corruption Layer

(See dedicated section above)

---

### Open Host Service

**Problem**: Multiple consumers need to integrate with your service; can't create custom APIs for each.

**Solution**: Define a well-documented, versioned protocol/API that any consumer can use. Publish it as a standard interface.

**Implementation**: RESTful API with OpenAPI spec, gRPC with proto files, or GraphQL schema.

**When to use**: Multiple consumers, public APIs, platform services.

**When NOT to use**: Single consumer (direct integration is simpler).

---

### Published Language

**Problem**: Need a shared language for communication between contexts that isn't tied to either's internal model.

**Solution**: Define a well-documented interchange format (events schema, canonical data model for integration).

**Example**: Industry standards like SWIFT for banking, HL7 for healthcare, or your own published event schemas (AsyncAPI, Avro schemas).

**When to use**: Multiple contexts communicate; need a lingua franca.

**When NOT to use**: Two services with a simple, direct relationship.

---

## Entity vs Aggregate Boundaries

### Problem
Where to draw the boundary of a service — at the entity level or the aggregate level?

### Solution
Use DDD Aggregates (not entities) as the minimum unit of service design. An aggregate is a cluster of entities and value objects with a single root entity that enforces invariants.

### Key Principles
- **Aggregate = consistency boundary** — all invariants within an aggregate are enforced in a single transaction
- **References between aggregates are by ID only** (not direct object references)
- **One service may own multiple aggregates** but not partial aggregates

### Example
```
Order Aggregate:
├── Order (root entity)
├── OrderLine (entity)
└── ShippingAddress (value object)

Invariant: Order total = sum of line items (enforced within aggregate)
```

Don't split Order and OrderLine into separate services — they share invariants.

### When to Use
- Deciding the minimum size of a service
- Entities have shared invariants

### When NOT to Use
- Aggregates are too small to justify a service (group multiple aggregates)

---

## Service Granularity (Finding the Right Size)

### Problem
How big or small should a microservice be? Too big → monolith benefits lost. Too small → operational overhead.

### Solution
Use multiple factors to determine granularity:

### Sizing Factors

| Factor | Favors Smaller | Favors Larger |
|---|---|---|
| Team cognitive load | Smaller = easier to understand | — |
| Deployment frequency | Different change rates → split | Same change rate → keep together |
| Data coupling | Independent data → split | Shared transactions → keep together |
| Operational overhead | — | Each service adds ops cost |
| Latency | — | Network calls add latency |
| Team structure | One team per service | Small team → fewer services |

### Rules of Thumb
- Can one team own and operate it? (If it takes multiple teams → too big)
- Can one person understand it? (If no one can → too big)
- Does it justify its operational cost? (If not → too small, merge it)
- Can you rewrite it in 2 weeks? (If not → possibly too big)
- Does it have its own data? (If not → might not be a real service)

---

## Database Decomposition Strategies

### Problem
Monolith services share a single database. How to give each service its own data store?

### Solution Approaches

### 1. Database per Service
- Each service has a private database
- No direct database sharing
- Communication via APIs or events

### 2. Shared Database (Transitional)
- Multiple services access the same database but own different schemas/tables
- Stepping stone to full separation
- Use database views or schemas for logical separation

### 3. Database Wrapping Service
- Put a thin service in front of the shared database
- Other services call this service instead of accessing DB directly
- Gradually migrate data out

### 4. Change Data Capture (CDC)
- Use CDC tools (Debezium) to stream changes from monolith DB
- New services consume the stream and maintain their own projections
- Non-invasive — monolith doesn't need modification

### 5. Event-Sourced Decomposition
- Replace shared state with event log
- Each service builds its own read model from events
- Source of truth is the event stream

### Implementation Steps
1. Identify which tables belong to which service
2. Handle shared tables: split, duplicate via events, or create a dedicated service
3. Replace joins with API calls or denormalized data
4. Handle referential integrity through eventual consistency
5. Migrate data (dual-write → CDC → cutover)

### Trade-offs
| Approach | Pros | Cons |
|---|---|---|
| DB per service | Full autonomy, independent scaling | No cross-service joins, data duplication |
| CDC | Non-invasive, works with legacy | Additional infrastructure, eventual consistency |
| Event sourcing | Full audit trail, flexible projections | Complex, steep learning curve |

---

## Feature-Based Decomposition

### Problem
Domain boundaries are unclear, but features have clear scope and ownership.

### Solution
Decompose by user-facing feature. Each feature (or feature set) becomes a service with its own UI component, business logic, and data.

### Implementation Steps
1. List all user-facing features
2. Group related features (e.g., all search-related features)
3. Each group becomes a candidate service
4. Verify: does the group have its own data? Its own lifecycle?
5. Use micro-frontends for UI decomposition alongside backend services

### Trade-offs
| Pros | Cons |
|---|---|
| Intuitive — maps to what users see | Features may cut across domains |
| Easy to explain to stakeholders | Can lead to duplication of domain logic |
| Aligns with product teams | Feature boundaries shift with product evolution |

### Real-world Example
Spotify: Squads own features (Discover Weekly, Your Library, Search) — each backed by dedicated services.

### When to Use
- Product-led organizations
- Clear feature ownership by teams
- User experience is the primary decomposition driver

### When NOT to Use
- Backend-heavy systems with little UI
- Features heavily share domain logic
- Domain-driven boundaries are clearer

---

## Volatility-Based Decomposition

### Problem
Some parts of the system change frequently while others are stable. Deploying everything together wastes time and adds risk.

### Solution
Separate components by rate of change. Stable components become one service; volatile components become another. Deploy volatile parts frequently without touching stable ones.

### Implementation Steps
1. Analyze git history: which modules change most frequently?
2. Identify change drivers: regulatory, market, experimentation
3. Group modules with similar change rates
4. Extract high-volatility modules into separate services
5. Keep stable modules together (fewer, larger services)

### Trade-offs
| Pros | Cons |
|---|---|
| Optimizes for deployment speed | Change rates may shift over time |
| Reduces blast radius of frequent changes | Doesn't align with domain boundaries necessarily |
| Practical, data-driven approach | Requires historical analysis |

### Real-world Example
Pricing engine changes weekly (A/B tests, promotions). Product catalog changes monthly. Separate them so pricing can deploy independently without risking catalog stability.

### When to Use
- Parts of system change at very different rates
- Deployment speed is a priority
- You have historical data on change frequency

### When NOT to Use
- All parts change at similar rates
- System is too small to benefit from separation
- Volatility is temporary (e.g., initial development phase)

---

## Team-Based Decomposition (Inverse Conway Maneuver)

### Problem
Architecture doesn't match desired team structure, leading to coordination overhead and slow delivery.

### Solution
Intentionally structure teams to match the desired architecture. If you want 5 microservices, create 5 teams. Team boundaries = service boundaries.

### Implementation Steps
1. Define the desired target architecture
2. Identify the services/components in that architecture
3. Form teams aligned to those services (stream-aligned teams)
4. Give each team full ownership: code, data, deployments, on-call
5. Minimize cross-team dependencies in the architecture
6. Create platform/enabling teams to support stream-aligned teams

### Trade-offs
| Pros | Cons |
|---|---|
| Architecture and org align — less friction | Requires organizational change (hard politically) |
| Clear ownership and accountability | Teams may be too small for complex services |
| Reduces coordination overhead | Not always possible to restructure teams |
| Enables independent velocity | May fragment domain expertise initially |

### Real-world Example
A fintech company wants to move from a monolith to 4 microservices (Accounts, Payments, Lending, Compliance). They restructure from 3 feature teams into 4 domain teams, each owning one service end-to-end.

### When to Use
- Organization is willing to restructure teams
- Current team structure causes bottlenecks
- Building for long-term ownership model

### When NOT to Use
- Can't change team structure (political/organizational constraints)
- Temporary project teams (no long-term ownership)
- Team size is fixed and doesn't map to desired services

---

## Summary: Choosing a Decomposition Strategy

| Strategy | Best Signal | Start Here If... |
|---|---|---|
| Business Capability | Stable org structure | Domain is well-known |
| Subdomain (DDD) | Complex domain rules | Domain experts available |
| Transactions | Consistency requirements | Strong ACID needs |
| Strangler Fig | Existing monolith | Migrating incrementally |
| Feature-based | Product-led org | Clear feature teams |
| Volatility-based | Different change rates | Deployment speed matters |
| Team-based | Org willing to restructure | Conway's Law is hurting you |

**Key principle**: There is no single correct decomposition. Most systems use a combination of strategies. Start coarse, refine over time. The cost of getting boundaries wrong is high but not permanent — services can be merged or split as understanding grows.
