# AI System Design Patterns: Real-World Examples

## How Production Systems Combine Patterns

Individual patterns are building blocks. Real systems combine 3-8 patterns to address multiple concerns simultaneously. This document shows how patterns compose in production architectures.

---

## Case Study 1: E-Commerce Product Search

### Patterns Used: Gateway + Router + Fan-Out/Fan-In + Circuit Breaker + Materialized View

### Problem
Large e-commerce platform needs AI-powered product search that handles 10,000 QPS, supports natural language queries ("red running shoes under $100 with good arch support"), and fails gracefully when AI providers have issues.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AI Gateway (Pattern 1)                        │
│  - Rate limiting per customer tier                                   │
│  - API key management                                                │
│  - Cost tracking per merchant                                        │
│  - Request/response logging                                          │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Router (P16)     │
                    │                   │
                    │ Simple queries:   │
                    │  → Materialized   │
                    │    View (cached)  │
                    │                   │
                    │ Complex queries:  │
                    │  → Fan-Out path   │
                    └──┬──────────┬─────┘
                       │          │
            ┌──────────┘          └──────────────┐
            │ (simple)                           │ (complex)
            ▼                                    ▼
┌───────────────────┐              ┌──────────────────────────────┐
│ Materialized View │              │    Fan-Out/Fan-In (P11)       │
│   (Pattern 19)    │              │                              │
│                   │              │  ┌─────────┐ ┌──────────┐   │
│ Pre-computed for: │              │  │Semantic │ │ Product  │   │
│ - "running shoes" │              │  │Search   │ │ Graph    │   │
│ - "laptop under   │              │  │(Vector) │ │ (Neo4j)  │   │
│    1000"          │              │  └────┬────┘ └────┬─────┘   │
│ - Top 1000 queries│              │       │           │          │
│                   │              │  ┌────▼───┐  ┌───▼──────┐   │
│ Cache hit: <5ms   │              │  │Circuit │  │Circuit   │   │
│ Hit rate: ~40%    │              │  │Breaker │  │Breaker   │   │
└───────────────────┘              │  │(P2)    │  │(P2)      │   │
                                   │  └────┬───┘  └───┬──────┘   │
                                   │       │          │           │
                                   │  ┌────▼──────────▼─────┐    │
                                   │  │   Result Merger      │    │
                                   │  │   - RRF ranking      │    │
                                   │  │   - Price filtering   │    │
                                   │  │   - Availability check│    │
                                   │  └──────────────────────┘    │
                                   └──────────────────────────────┘
```

### How Patterns Interact

1. **Gateway** receives all requests, handles auth, tracks costs
2. **Router** classifies query: 40% are common queries (cache hit), 60% need full processing
3. **Materialized View** serves cached results in <5ms for common queries
4. **Fan-Out** sends complex queries to vector search + product graph in parallel
5. **Circuit Breaker** protects each search source independently — if vector DB is down, product graph results still returned

### Key Metrics
| Metric | Value |
|--------|-------|
| P50 latency (cache hit) | 4ms |
| P50 latency (full search) | 180ms |
| P99 latency | 450ms |
| Cost per query (cached) | $0.00 |
| Cost per query (full) | $0.003 |
| Availability | 99.95% |

### Failure Modes Handled
- **Vector DB down**: Circuit breaker opens, return product graph results only (degraded but functional)
- **AI embedding service down**: Fall back to keyword search
- **Budget exceeded**: Gateway blocks requests, return cached results where possible
- **Slow query**: Fan-in returns partial results after 300ms deadline

---

## Case Study 2: Financial Compliance System

### Patterns Used: Event Sourcing + CQRS + Saga + Sidecar + Poison Pill

### Problem
Investment bank needs AI to review trade communications for compliance violations. Every AI decision must be auditable, toxic inputs must be quarantined, and multi-step review workflows must be recoverable if interrupted.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Communication Ingestion                           │
│                                                                       │
│  Emails, Chats, Voice Transcripts                                    │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────────────────────────────────┐                        │
│  │        Poison Pill Detector (P13)        │                        │
│  │                                         │                        │
│  │  - Detect encoded/obfuscated content    │                        │
│  │  - Flag adversarial manipulation        │                        │
│  │  - Quarantine corrupted files           │                        │
│  └──────────┬──────────────────────────────┘                        │
│             │ (clean inputs only)                                     │
│             ▼                                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    CQRS (Pattern 6)                          │    │
│  │                                                             │    │
│  │  WRITE PATH                     READ PATH                   │    │
│  │  ┌──────────────────┐          ┌──────────────────────┐    │    │
│  │  │Parse → Classify  │          │ Compliance Dashboard │    │    │
│  │  │→ Embed → Index   │          │ - Search violations  │    │    │
│  │  │                  │          │ - Risk scores        │    │    │
│  │  │Event Sourcing ──►│──events──│ - Audit reports      │    │    │
│  │  │(Pattern 5)       │          │                      │    │    │
│  │  └──────────────────┘          └──────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              Compliance Review Saga (Pattern 4)               │    │
│  │                                                             │    │
│  │  Step 1: AI Classification                                  │    │
│  │    → "Potential insider trading language detected"           │    │
│  │    → Confidence: 0.87                                       │    │
│  │    Compensation: Mark as "review_pending" (no action taken) │    │
│  │                                                             │    │
│  │  Step 2: Contextual Analysis                                │    │
│  │    → Pull related communications from same parties          │    │
│  │    → Assess pattern vs. isolated incident                   │    │
│  │    Compensation: Release gathered context, clear flags      │    │
│  │                                                             │    │
│  │  Step 3: Risk Scoring                                       │    │
│  │    → Aggregate evidence, compute risk score                 │    │
│  │    Compensation: Reset risk score to previous value         │    │
│  │                                                             │    │
│  │  Step 4: Human Escalation (if risk > threshold)             │    │
│  │    → Route to compliance officer with full context          │    │
│  │    Compensation: Close escalation ticket                    │    │
│  │                                                             │    │
│  │  Step 5: Resolution & Record                                │    │
│  │    → Record decision (violation/no-violation/needs-review)  │    │
│  │    → Update audit trail                                     │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌──────────────────────────────────┐                               │
│  │    Guardrail Sidecar (P7)        │  (attached to each AI service) │
│  │    - Log all AI decisions        │                               │
│  │    - Enforce confidence thresholds│                               │
│  │    - PII redaction in logs       │                               │
│  │    - Regulatory rule enforcement │                               │
│  └──────────────────────────────────┘                               │
└─────────────────────────────────────────────────────────────────────┘
```

### Event Sourcing in Action

Every AI decision produces events:

```
Event Stream for Communication #COM-2024-78432:

1. CommunicationReceived
   {type: "email", parties: ["trader_a", "external_b"], timestamp: "..."}

2. PoisonPillCheckPassed
   {checks: ["encoding", "format", "length"], result: "clean"}

3. ClassificationCompleted
   {labels: ["potential_insider_trading"], confidence: 0.87, model: "compliance-v3.2"}

4. ContextRetrieved
   {related_comms: 12, timespan: "30d", same_parties: 5}

5. RiskScoreComputed
   {score: 0.72, factors: ["repeated_pattern", "pre_announcement_timing"]}

6. EscalationCreated
   {officer: "CO-445", priority: "high", deadline: "48h"}

7. HumanDecision
   {officer: "CO-445", decision: "confirmed_violation", action: "report_to_sec"}
```

### Why This Pattern Combination Works
- **Event Sourcing**: Regulators can audit exactly what the AI "saw" and decided
- **CQRS**: Ingestion handles 1M+ communications/day; dashboard serves real-time queries independently
- **Saga**: Multi-step review is recoverable — system crash at step 3 resumes from step 3
- **Sidecar**: Consistent guardrails across all AI services without code duplication
- **Poison Pill**: Malicious communications detected before they corrupt AI analysis

---

## Case Study 3: Multi-Agent Customer Support

### Patterns Used: Orchestrator-Worker + Bulkhead + Canary + Competing Consumers + Claim Check

### Problem
SaaS company with 50K daily support requests needs AI agents that handle routine issues autonomously, escalate complex issues intelligently, and safely deploy improvements without breaking customer experience.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Customer Support Platform                          │
│                                                                       │
│  Incoming Tickets                                                    │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │            Competing Consumers (Pattern 18)                   │    │
│  │                                                             │    │
│  │  ┌──────────────────────────────────────────────────────┐  │    │
│  │  │              Priority Queue System                    │  │    │
│  │  │                                                      │  │    │
│  │  │  [VIP Queue]     [Standard Queue]   [Batch Queue]   │  │    │
│  │  │  Concurrency: 20  Concurrency: 50   Concurrency: 10 │  │    │
│  │  │  SLA: 30s         SLA: 5min         SLA: 1hr        │  │    │
│  │  └──────────────────────────────────────────────────────┘  │    │
│  │                                                             │    │
│  │  ┌────────────────────────────────────┐  BULKHEAD (P3)    │    │
│  │  │                                    │                    │    │
│  │  │  VIP Pool ───── Standard Pool ─── Batch Pool          │    │
│  │  │  (isolated)     (isolated)        (isolated)           │    │
│  │  │  Budget: $200/h Budget: $500/h    Budget: $50/h       │    │
│  │  └────────────────────────────────────┘                    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │           Orchestrator-Worker (Pattern 17)                    │    │
│  │                                                             │    │
│  │  Orchestrator receives ticket, decomposes:                  │    │
│  │                                                             │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │    │
│  │  │Classifier│  │ Retriever│  │ Resolver │  │ Verifier │ │    │
│  │  │ Worker   │  │  Worker  │  │  Worker  │  │  Worker  │ │    │
│  │  │          │  │          │  │          │  │          │ │    │
│  │  │Categorize│  │Fetch KB  │  │Draft     │  │Check     │ │    │
│  │  │& route   │  │articles, │  │response  │  │quality,  │ │    │
│  │  │          │  │past cases│  │or action │  │safety    │ │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │    │
│  │                                                             │    │
│  │  Claim Check (P20): Past case history (large) stored in    │    │
│  │  blob storage, only case_ids passed between workers         │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                Canary Deployment (Pattern 14)                 │    │
│  │                                                             │    │
│  │  Current: prompt_v12 + model_gpt4o                          │    │
│  │  Canary:  prompt_v13 + model_gpt4o (5% of standard tier)   │    │
│  │                                                             │    │
│  │  Metrics watched:                                           │    │
│  │  - Customer satisfaction (CSAT): v12=4.3, v13=4.4 ✅       │    │
│  │  - Escalation rate: v12=12%, v13=10% ✅                    │    │
│  │  - Resolution time: v12=3.2min, v13=2.8min ✅              │    │
│  │  - Safety incidents: v12=0, v13=0 ✅                       │    │
│  │                                                             │    │
│  │  Decision: PROMOTE v13 → increase to 25% → 50% → 100%    │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### How Patterns Interact
1. **Competing Consumers** pull tickets from priority queues — auto-scale during peak hours
2. **Bulkhead** ensures VIP customers always get capacity even when standard queue is overwhelmed
3. **Orchestrator-Worker** decomposes each ticket into classify → retrieve → resolve → verify
4. **Claim Check** prevents large case histories from bloating messages between workers
5. **Canary** safely rolls out prompt improvements without risking customer experience

---

## Anti-Pattern Examples

### Anti-Pattern 1: Over-Engineering with Event Sourcing

**Scenario**: Startup building an internal chatbot for 50 employees adds Event Sourcing for all AI interactions.

**What goes wrong**:
- Storage costs exceed the AI API costs
- Team spends 3 weeks building event replay infrastructure
- Schema evolution becomes a burden (events are immutable)
- Nobody ever replays events or audits them
- Simple feature changes require event schema migrations

**Root cause**: Event Sourcing solves compliance/audit problems. Internal tool with 50 users has no regulatory requirement and no need to replay AI decisions.

**Right approach**: Simple request/response logging to a database table. Add Event Sourcing only if regulations or scale demand it.

---

### Anti-Pattern 2: Premature Bulkhead Isolation

**Scenario**: Team with a single AI-powered feature (chatbot) creates 4 separate bulkheads for "future isolation."

**What goes wrong**:
- 75% of allocated resources sit idle in unused bulkheads
- Configuration complexity with no benefit
- Difficult to understand actual resource usage
- When the one active feature needs burst capacity, it can't access idle resources

**Root cause**: Bulkhead Pattern solves multi-workload interference. With one workload, there's nothing to isolate.

**Right approach**: Start with a single resource pool. Add bulkheads when you have 2+ workloads with different priorities competing for resources.

---

### Anti-Pattern 3: Circuit Breaker Without Fallback

**Scenario**: Team implements Circuit Breaker for their AI provider. When it opens, they return HTTP 503 to users.

**What goes wrong**:
- Users see errors for 30+ seconds while circuit is open
- No better than not having the circuit breaker — user experience is equally bad
- Circuit breaker adds complexity without adding resilience

**Root cause**: Circuit Breaker is only valuable with meaningful fallback behavior. Without it, you're just failing slightly faster.

**Right approach**: Either implement fallback (cached response, simpler model, rule-based response, graceful UI message) OR don't use Circuit Breaker at all.

---

### Anti-Pattern 4: Gateway as Bottleneck

**Scenario**: All 30 microservices route through a single AI Gateway instance. Gateway becomes the system's ceiling.

**What goes wrong**:
- Gateway handles 5000 QPS but the system needs 15000
- Single gateway failure takes down all AI features
- Gateway team becomes bottleneck for every team's changes
- Latency increases as gateway logic grows

**Root cause**: Gateway Pattern needs horizontal scaling and high availability. Treating it as a single instance violates the pattern's intent.

**Right approach**: Gateway as a horizontally scaled service (3+ instances), load-balanced, with each instance stateless. Consider per-domain gateways if organizational boundaries require it.

---

### Anti-Pattern 5: Saga for Simple Workflows

**Scenario**: Team implements full Saga with compensation logic for a chatbot that only reads data and returns responses.

**What goes wrong**:
- Compensation logic for read-only operations is meaningless
- Saga orchestrator adds 200ms latency to every response
- Code complexity 5x higher than needed
- New developers spend days understanding the saga framework

**Root cause**: Saga solves the problem of long-running transactions that modify external state. Read-only AI interactions have nothing to compensate.

**Right approach**: Simple request-response with retry. Use Saga only when the AI workflow creates side effects that need rollback.

---

## Pattern Evolution: Growing a System

### Phase 1: MVP (Month 1-3)
**2 Patterns: Gateway + Retry with Backoff**

```
┌──────────────┐        ┌──────────┐
│  AI Gateway  │───────►│  OpenAI  │
│  - API keys  │  retry │  API     │
│  - Logging   │◄───────│          │
│  - Basic rate│        └──────────┘
│    limiting  │
└──────────────┘
```

Traffic: 100 QPS | Budget: $5K/month | Team: 2 engineers

---

### Phase 2: Growth (Month 4-8)
**5 Patterns: + Router + Circuit Breaker + Materialized View**

```
┌──────────────┐     ┌──────────┐    ┌──────────┐
│  AI Gateway  │────►│  Router  │───►│  OpenAI  │
│  + Cache     │     │          │    └──────────┘
│  (Material-  │     │  Simple→ │    ┌──────────┐
│   ized View) │     │  Cache   │───►│ Anthropic│
│              │     │          │    │(fallback)│
│  + Circuit   │     │  Complex→│    └──────────┘
│    Breaker   │     │  Full AI │
└──────────────┘     └──────────┘
```

Traffic: 1,000 QPS | Budget: $30K/month | Team: 5 engineers

**Why these patterns added**:
- Router: 40% of queries are simple (route to cache, save 60% cost)
- Circuit Breaker: OpenAI had 3 outages last month, need Anthropic fallback
- Materialized View: Same questions asked repeatedly, cache saves $12K/month

---

### Phase 3: Scale (Month 9-14)
**8 Patterns: + Fan-Out/Fan-In + Pipeline + Competing Consumers**

```
┌──────────────┐    ┌────────┐    ┌────────────────────┐
│  AI Gateway  │───►│ Router │───►│  Fan-Out           │
│              │    │        │    │  - Vector search   │
│  + Canary    │    │        │    │  - Knowledge graph │
│  deployment  │    │        │    │  - Product DB      │
└──────────────┘    └────────┘    └────────────────────┘
                                          │
                    ┌──────────────────────┘
                    ▼
            ┌───────────────┐     ┌─────────────────┐
            │  Ingestion    │     │  Competing      │
            │  Pipeline     │     │  Consumers      │
            │  (async)      │     │  (inference)    │
            └───────────────┘     └─────────────────┘
```

Traffic: 10,000 QPS | Budget: $150K/month | Team: 12 engineers

**Why these patterns added**:
- Fan-Out: Need multiple data sources for comprehensive answers
- Pipeline: Knowledge base ingestion is a multi-stage async process
- Competing Consumers: Bursty traffic needs elastic scaling
- Canary: Can't risk breaking experience for 10K QPS users

---

### Phase 4: Enterprise (Month 15+)
**12+ Patterns: + Event Sourcing + CQRS + Saga + Bulkhead + Sidecar**

Added for enterprise requirements:
- Event Sourcing: SOC2 audit requirement
- CQRS: Ingestion at 100K docs/day, retrieval at 50K QPS — different scaling
- Saga: AI now takes actions (send emails, update CRM) — needs compensation
- Bulkhead: Enterprise vs. free tier isolation required
- Sidecar: PII detection mandatory across all 15 AI services

Traffic: 50,000 QPS | Budget: $500K/month | Team: 30 engineers

---

## Pattern Selection Framework

### Decision Tree

```
START: What is your primary concern?
│
├── RELIABILITY
│   ├── Provider outages? → Circuit Breaker + Gateway (provider fallback)
│   ├── Cascade failures? → Bulkhead (workload isolation)
│   ├── Transient errors? → Retry with Backoff
│   └── Long workflow failures? → Saga (compensation logic)
│
├── PERFORMANCE
│   ├── High latency? → Materialized View (caching) + Router (route simple queries away)
│   ├── Multiple data sources? → Fan-Out/Fan-In (parallel retrieval)
│   ├── Throughput ceiling? → Competing Consumers (horizontal scaling)
│   └── Large payloads? → Claim Check (reference passing)
│
├── COST
│   ├── Over-spending on AI? → Router (right-size model per query) + Materialized View (cache)
│   ├── No visibility into spend? → Gateway (centralized cost tracking)
│   └── Budget isolation per team? → Bulkhead (per-team budgets)
│
├── SAFETY & COMPLIANCE
│   ├── Regulatory audit? → Event Sourcing (full decision trail)
│   ├── Malicious inputs? → Poison Pill (input quarantine)
│   ├── Consistent guardrails? → Sidecar (policy enforcement)
│   └── Data classification? → CQRS (separate ingestion security from retrieval)
│
├── DEPLOYMENT
│   ├── Risky model changes? → Canary (% rollout) or Shadow (zero-risk comparison)
│   ├── Legacy migration? → Strangler Fig (incremental replacement)
│   └── Multi-model evaluation? → Shadow (parallel comparison)
│
└── COORDINATION
    ├── Multi-agent workflows? → Orchestrator-Worker
    ├── Agent-to-service calls? → Ambassador (connection management)
    ├── Provider abstraction? → Gateway
    └── Query classification? → Router
```

### Minimum Viable Patterns by System Type

| System Type | Essential Patterns | Add When Scaling |
|-------------|-------------------|------------------|
| Chatbot | Gateway, Retry | + Circuit Breaker, Materialized View |
| RAG System | Pipeline, CQRS | + Fan-Out, Competing Consumers |
| Agent System | Orchestrator-Worker, Saga | + Bulkhead, Claim Check, Event Sourcing |
| AI Platform | Gateway, Router, Bulkhead | + Canary, Competing Consumers |
| Compliance AI | Event Sourcing, Sidecar, Poison Pill | + CQRS, Saga |

---

## Interview Pattern: Presenting AI System Design Patterns

### Structured Approach for System Design Interviews

When asked to design an AI system in an interview, use this framework:

#### Step 1: Identify Requirements → Map to Patterns (2 minutes)

```
Interviewer: "Design a customer support AI system"

Your thought process:
- Reliability needed? YES → Circuit Breaker, Bulkhead
- Multi-step workflows? YES → Orchestrator-Worker
- Audit trail? PROBABLY → Event Sourcing
- Cost control? YES → Gateway, Router
- Safe deployment? YES → Canary

Declare: "I'll use 5 patterns: Gateway, Orchestrator-Worker, 
Circuit Breaker, Router, and Canary deployment."
```

#### Step 2: Draw the Architecture (5 minutes)

Draw the high-level architecture showing how patterns compose. Name each pattern explicitly:

```
"Requests enter through the AI Gateway [Pattern 1], which handles
auth and cost tracking. The Router [Pattern 16] classifies queries
into simple (FAQ), standard (knowledge lookup), and complex 
(multi-step action). Complex queries go to the Orchestrator 
[Pattern 17], which coordinates specialized workers..."
```

#### Step 3: Deep Dive One Pattern (5 minutes)

When the interviewer asks to go deeper, pick the most interesting pattern and explain:
- The specific failure mode it handles
- The state machine or algorithm it uses
- How it interacts with adjacent patterns
- What happens when THIS component fails

#### Step 4: Discuss Tradeoffs (3 minutes)

```
"The tradeoff of using the Orchestrator-Worker pattern is that 
the orchestrator becomes a single point of failure. To mitigate 
this, we'd make the orchestrator stateless with saga state stored 
in a durable store, allowing any instance to resume a failed workflow."
```

#### Step 5: Evolution Story (2 minutes)

```
"For an MVP, I'd start with just Gateway + Retry. As we scale past 
1000 QPS, I'd add Router and Materialized View for cost optimization.
At enterprise scale, I'd add Event Sourcing for audit and Bulkhead 
for tenant isolation."
```

### Common Interview Patterns by Problem Type

| Interview Question | Lead With | Support With |
|-------------------|-----------|--------------|
| "Design a RAG system" | Pipeline + CQRS | Fan-Out, Materialized View |
| "Design an AI chatbot" | Gateway + Router | Circuit Breaker, Materialized View |
| "Design a multi-agent system" | Orchestrator-Worker + Saga | Bulkhead, Claim Check |
| "Design an AI platform" | Gateway + Bulkhead + Router | Canary, Competing Consumers |
| "Make this AI system reliable" | Circuit Breaker + Retry | Bulkhead, Saga |
| "Migrate legacy to AI" | Strangler Fig | Shadow, Canary, Router |
| "Design for compliance" | Event Sourcing + Sidecar | CQRS, Poison Pill |

### Red Flags to Avoid in Interviews

1. **Using all 20 patterns** — Shows lack of judgment. Use 3-5 max, justify each.
2. **Pattern without problem** — Always state the PROBLEM before introducing the pattern.
3. **Ignoring tradeoffs** — Every pattern has a cost. Acknowledge it.
4. **No evolution story** — Show you wouldn't over-engineer day 1.
5. **Pattern name-dropping without understanding** — Interviewer will dig deeper. Know the internals.

---

## Pattern Combination Compatibility Matrix

Some patterns naturally compose; others create tension:

### Strong Combinations (Synergy)
| Pattern A | Pattern B | Why They Work Together |
|-----------|-----------|----------------------|
| Gateway | Router | Router is a natural gateway component |
| Gateway | Circuit Breaker | Gateway is the ideal place for circuit breakers |
| Event Sourcing | CQRS | Events bridge write and read models |
| Orchestrator-Worker | Saga | Orchestrator manages saga lifecycle |
| Pipeline | Competing Consumers | Consumers scale each pipeline stage |
| Fan-Out | Circuit Breaker | Per-source circuit breakers prevent slow sources from blocking |
| Canary | Shadow | Shadow before canary for zero-risk evaluation |
| Sidecar | Poison Pill | Sidecar enforces poison pill detection |

### Tension Combinations (Use Carefully)
| Pattern A | Pattern B | Tension |
|-----------|-----------|---------|
| Materialized View | Event Sourcing | Cache invalidation vs. event replay — which is source of truth? |
| Saga | Competing Consumers | Saga assumes ordered steps; competing consumers have no order guarantee |
| Bulkhead | Materialized View | Isolated caches per bulkhead reduce hit rates |
| Circuit Breaker | Retry | Must coordinate: retry WITHIN circuit, break AFTER retries exhausted |

---

## Summary: The Pattern Architect's Checklist

Before finalizing your AI system architecture, verify:

- [ ] Every pattern addresses a specific, stated problem
- [ ] No pattern is added "just in case" without current need
- [ ] Patterns compose cleanly (no tension combinations unaddressed)
- [ ] Evolution path defined (start simple, add patterns as scale demands)
- [ ] Each pattern has a clear owner/team responsible
- [ ] Failure modes documented (what happens when each pattern's component fails?)
- [ ] Cost justified (pattern's operational cost < cost of the problem it solves)
- [ ] Monitoring defined (how do you know each pattern is working?)

These patterns are tools, not goals. The best architecture uses the minimum patterns needed to meet current requirements, with a clear path to add more as needs evolve.
