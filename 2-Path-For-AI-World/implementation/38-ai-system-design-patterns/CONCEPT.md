# AI System Design Patterns

## A Pattern Language for AI Architectures

Just as the Gang of Four defined patterns for object-oriented design, AI systems need their own pattern language. These patterns address the unique challenges of AI architectures: non-deterministic outputs, high latency, token costs, model failures, and the need for observability into black-box reasoning.

This catalog defines 20 patterns organized by their primary concern: **Resilience**, **Data Flow**, **Deployment**, and **Coordination**.

---

## Pattern 1: Gateway Pattern

### Problem It Solves
Applications directly coupled to AI providers (OpenAI, Anthropic, Cohere) face vendor lock-in, inconsistent error handling, no centralized cost control, and duplicated retry logic across services.

### When to Use
- Multiple services call AI providers independently
- You need centralized rate limiting, cost tracking, or API key management
- You want to swap providers without changing downstream code
- You need request/response logging for compliance

### When NOT to Use
- Single service with one AI provider (adds unnecessary indirection)
- Ultra-low latency requirements where gateway adds unacceptable overhead (<10ms budget)
- Prototype or MVP stage where flexibility isn't worth the infrastructure cost

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      AI Gateway                              │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
│  │  Auth &   │  │  Rate    │  │  Cost    │  │  Response  │ │
│  │  API Keys │  │  Limiter │  │  Tracker │  │  Cache     │ │
│  └──────────┘  └──────────┘  └──────────┘  └───────────┘ │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
│  │  Router   │  │  Retry   │  │  Logger  │  │  Transform │ │
│  │  Logic    │  │  Policy  │  │          │  │  Layer     │ │
│  └──────────┘  └──────────┘  └──────────┘  └───────────┘ │
└────────┬────────────────┬────────────────┬────────────────┘
         │                │                │
    ┌────▼────┐     ┌────▼────┐     ┌────▼────┐
    │ OpenAI  │     │Anthropic│     │  Cohere │
    │  API    │     │  API    │     │  API    │
    └─────────┘     └─────────┘     └─────────┘
```

### Key Components
- **Provider Abstraction Layer**: Normalizes request/response formats across providers
- **Routing Engine**: Directs requests to optimal provider based on model, cost, latency
- **Cost Accountant**: Tracks token usage per team/service, enforces budgets
- **Semantic Cache**: Caches responses for semantically similar queries (not just exact matches)
- **Observability Collector**: Captures latency, token usage, error rates per provider

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Provider flexibility | Additional network hop (5-15ms latency) |
| Centralized cost control | Single point of failure (needs HA) |
| Unified logging | Operational complexity of maintaining gateway |
| Semantic caching | Cache invalidation complexity |

### Related Patterns
- Ambassador Pattern (Gateway as ambassador)
- Circuit Breaker (embedded in gateway)
- Router Pattern (routing logic within gateway)

---

## Pattern 2: Circuit Breaker Pattern

### Problem It Solves
AI providers experience outages, rate limiting, and degraded performance. Without circuit breakers, services continue sending requests to failing providers, exhausting timeouts, degrading user experience, and accumulating costs from retries.

### When to Use
- AI provider has documented SLA below 99.99%
- Your system has fallback behavior (cached responses, simpler model, rule-based fallback)
- Multiple downstream services depend on the same AI provider
- Rate limits are shared across your organization

### When NOT to Use
- AI call is best-effort and failure is acceptable (e.g., optional enhancement)
- No meaningful fallback exists and you'd rather fail fast to the user
- Single-request batch jobs where retry at job level is simpler

### Architecture Diagram

```
                    ┌─────────────────────────┐
                    │     Circuit Breaker      │
                    │                         │
  Request ─────────►  State: [CLOSED|OPEN|   │
                    │         HALF-OPEN]      │
                    │                         │
                    │  Failure Count: N       │
                    │  Threshold: 5           │
                    │  Timeout: 30s           │
                    │  Half-Open Max: 3       │
                    └──────┬──────────────────┘
                           │
              ┌────────────┼────────────────┐
              │            │                │
         CLOSED       HALF-OPEN          OPEN
              │            │                │
              ▼            ▼                ▼
     ┌────────────┐ ┌───────────┐  ┌────────────┐
     │  Forward   │ │  Allow N  │  │  Return    │
     │  to AI     │ │  probe    │  │  fallback  │
     │  Provider  │ │  requests │  │  immediately│
     └────────────┘ └───────────┘  └────────────┘
```

### State Transitions for AI Systems

```
CLOSED ──[5 failures in 60s]──► OPEN
OPEN ──[after 30s cooldown]──► HALF-OPEN
HALF-OPEN ──[3 successes]──► CLOSED
HALF-OPEN ──[1 failure]──► OPEN
```

### AI-Specific Considerations
- **Rate limit errors (429)**: Trip the breaker immediately — continued requests worsen the situation
- **Timeout errors**: Use longer thresholds — AI responses legitimately take 5-30s
- **Partial failures**: Model returns response but with degraded quality — harder to detect
- **Cost-based tripping**: Open circuit when spend exceeds budget, regardless of errors

### Fallback Strategies (AI-Specific)
1. **Provider fallback**: OpenAI fails → route to Anthropic
2. **Model downgrade**: GPT-4 fails → use GPT-3.5 (faster, cheaper, less capable)
3. **Cached response**: Return semantically similar cached response
4. **Rule-based fallback**: Use traditional logic for common cases
5. **Graceful degradation**: Disable AI-powered features, show simpler UI

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Prevents cascade failures | Stale fallback responses |
| Reduces wasted API costs | Complexity in tuning thresholds |
| Faster failure detection | May trip prematurely on transient errors |
| Protects downstream services | Requires meaningful fallback logic |

### Related Patterns
- Gateway Pattern (circuit breaker lives inside gateway)
- Retry with Backoff (used before circuit trips)
- Bulkhead Pattern (isolates failures to specific workloads)

---

## Pattern 3: Bulkhead Pattern

### Problem It Solves
A single misbehaving AI workload (e.g., a runaway agent loop consuming all tokens) exhausts shared resources, causing all AI-powered features to fail simultaneously.

### When to Use
- Multiple AI features share the same provider/budget/compute pool
- Some AI workloads are more critical than others (revenue-generating vs. nice-to-have)
- You need to guarantee capacity for priority workloads during peak load
- Agent systems where one agent's failure shouldn't affect others

### When NOT to Use
- Single AI workload with dedicated resources
- All AI features have equal priority and shared fate is acceptable
- Cost of isolation exceeds cost of occasional cascade failure

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Resource Pool                                 │
│                                                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Bulkhead A    │  │   Bulkhead B    │  │   Bulkhead C    │ │
│  │   (Critical)    │  │   (Standard)    │  │   (Background)  │ │
│  │                 │  │                 │  │                 │ │
│  │  Budget: $500/h │  │  Budget: $200/h │  │  Budget: $50/h  │ │
│  │  Concurrency: 50│  │  Concurrency: 20│  │  Concurrency: 5 │ │
│  │  Priority: HIGH │  │  Priority: MED  │  │  Priority: LOW  │ │
│  │                 │  │                 │  │                 │ │
│  │  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌───────────┐  │ │
│  │  │ Chat API  │  │  │  │ Search    │  │  │  │ Batch     │  │ │
│  │  │ Real-time │  │  │  │ Ranking   │  │  │  │ Embedding │  │ │
│  │  └───────────┘  │  │  └───────────┘  │  │  └───────────┘  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Isolation Dimensions for AI
- **Token budget isolation**: Each bulkhead has its own token/spend cap
- **Concurrency isolation**: Separate thread pools or connection pools per workload
- **Provider isolation**: Critical workloads get dedicated API keys with higher rate limits
- **Compute isolation**: Separate GPU/inference instances per workload class

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Blast radius containment | Resource underutilization (idle capacity in bulkheads) |
| Priority guarantee | Complexity of managing multiple pools |
| Cost predictability per workload | Harder to burst for legitimate spikes |
| Independent scaling | More infrastructure to monitor |

### Related Patterns
- Circuit Breaker (trips within a single bulkhead)
- Competing Consumers (workers within a bulkhead)
- Gateway Pattern (gateway enforces bulkhead allocation)

---

## Pattern 4: Saga Pattern

### Problem It Solves
AI agent workflows involve multiple steps that can fail mid-execution: researching, planning, executing actions, updating databases. Unlike simple request-response, these long-running transactions need compensation logic to undo partial work when a step fails.

### When to Use
- Multi-step agent workflows that modify external state
- Agent actions that are partially reversible (e.g., created a draft email but hasn't sent it)
- Workflows spanning multiple services where distributed transactions are impractical
- Human-in-the-loop approval gates within agent workflows

### When NOT to Use
- Simple single-step AI calls (inference only, no side effects)
- Idempotent operations where retry is sufficient
- Workflows where all steps can be atomic (use normal transactions instead)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Saga Orchestrator                          │
│                                                             │
│  Step 1          Step 2          Step 3          Step 4     │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐ │
│  │Research │───►│Plan     │───►│Execute  │───►│Verify   │ │
│  │Context  │    │Actions  │    │Actions  │    │Results  │ │
│  └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘ │
│       │              │              │              │       │
│  Compensate:    Compensate:    Compensate:    Compensate: │
│  Release locks  Discard plan   Undo actions   Flag for    │
│                                               review      │
└─────────────────────────────────────────────────────────────┘

HAPPY PATH:
  Research ──► Plan ──► Execute ──► Verify ──► COMPLETE

FAILURE AT STEP 3:
  Research ──► Plan ──► Execute(FAIL) ──► Compensate Execute
                                         ──► Compensate Plan
                                         ──► Compensate Research
                                         ──► SAGA FAILED
```

### Saga Types in AI Systems

**Choreography-based (Event-driven)**:
```
Agent A publishes "research_complete" event
Agent B listens, starts planning
Agent B publishes "plan_ready" event
Agent C listens, starts execution
```

**Orchestration-based (Centralized)**:
```
Orchestrator calls Agent A: "Research this topic"
Orchestrator calls Agent B: "Plan based on research"
Orchestrator calls Agent C: "Execute this plan"
Orchestrator handles failures and compensation
```

### AI-Specific Compensation Examples
| Step | Action | Compensation |
|------|--------|-------------|
| Create draft email | Draft saved | Delete draft |
| Book calendar slot | Slot reserved | Cancel reservation |
| Update CRM record | Field modified | Revert to previous value |
| Send notification | Message sent | Send correction/retraction |
| Generate report | File created | Mark as invalid, notify stakeholders |

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Handles long-running workflows | Compensation logic is complex |
| Supports human-in-the-loop | Eventual consistency (not immediate) |
| Partial failure recovery | Not all actions are reversible |
| Clear audit trail | Saga state management overhead |

### Related Patterns
- Event Sourcing (records saga steps for replay)
- Orchestrator-Worker (orchestrator manages saga)
- Circuit Breaker (trips if saga steps consistently fail)

---

## Pattern 5: Event Sourcing Pattern

### Problem It Solves
AI systems make decisions that affect real outcomes. When something goes wrong, you need to know exactly what the AI "saw," what it "decided," and why. Traditional CRUD databases overwrite state, losing the decision history.

### When to Use
- Regulated industries requiring AI audit trails (finance, healthcare, legal)
- Debugging non-deterministic AI behavior ("why did it do that?")
- A/B testing AI changes by replaying historical events against new models
- Building training datasets from production interactions
- Compliance requirements (EU AI Act, SOC2 for AI systems)

### When NOT to Use
- High-volume, low-value AI interactions (autocomplete suggestions)
- Storage costs outweigh audit value
- Simple stateless inference with no downstream effects

### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                     Event Store                                │
│                                                              │
│  Event 1: UserQueryReceived                                  │
│    {query: "...", user_id: "...", timestamp: "..."}          │
│                                                              │
│  Event 2: ContextRetrieved                                   │
│    {chunks: [...], scores: [...], source_ids: [...]}         │
│                                                              │
│  Event 3: PromptConstructed                                  │
│    {system_prompt: "...", user_msg: "...", context: "..."}   │
│                                                              │
│  Event 4: LLMResponseGenerated                               │
│    {response: "...", model: "gpt-4", tokens: 847,           │
│     latency_ms: 2340, temperature: 0.7}                     │
│                                                              │
│  Event 5: GuardrailEvaluated                                 │
│    {passed: true, checks: ["toxicity", "pii", "relevance"]} │
│                                                              │
│  Event 6: ResponseDelivered                                  │
│    {response_id: "...", user_feedback: null}                 │
└──────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐          ┌─────────────────────┐
│  Replay Engine  │          │  Projection Builder │
│  (Debug/Audit)  │          │  (Read Models)      │
└─────────────────┘          └─────────────────────┘
```

### Event Types for AI Systems
- **Decision Events**: What the AI decided and what inputs led to that decision
- **Context Events**: What retrieval results were available at decision time
- **Guardrail Events**: What safety checks passed/failed
- **Feedback Events**: User thumbs-up/down, corrections, escalations
- **Cost Events**: Token usage, latency, provider used

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Complete audit trail | Storage grows unboundedly |
| Replay and debug any interaction | Complexity of event schema evolution |
| Build training data from production | Query complexity (need projections) |
| Regulatory compliance | Event ordering guarantees needed |

### Related Patterns
- CQRS (separate write events from read projections)
- Saga Pattern (saga steps are events)
- Poison Pill (quarantine events for toxic inputs)

---

## Pattern 6: CQRS Pattern

### Problem It Solves
AI knowledge bases have fundamentally different read and write characteristics. Ingestion (write) is batch, compute-heavy, and tolerant of latency. Retrieval (read) must be fast, concurrent, and optimized for semantic similarity. A single model for both is suboptimal.

### When to Use
- RAG systems where ingestion and retrieval have different scaling needs
- Knowledge bases with complex ingestion pipelines (parsing, chunking, embedding)
- Systems needing different consistency guarantees for reads vs writes
- High read-to-write ratio (common in knowledge bases: 1000:1)

### When NOT to Use
- Simple AI applications with no persistent knowledge
- Write-heavy systems where eventual consistency is unacceptable
- Small datasets where a single store performs adequately

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                   │
│  WRITE PATH (Ingestion)              READ PATH (Retrieval)       │
│                                                                   │
│  ┌──────────┐                        ┌──────────────┐           │
│  │ Document │                        │ User Query   │           │
│  │ Upload   │                        │              │           │
│  └────┬─────┘                        └──────┬───────┘           │
│       │                                     │                    │
│       ▼                                     ▼                    │
│  ┌──────────┐                        ┌──────────────┐           │
│  │ Parse &  │                        │ Query        │           │
│  │ Extract  │                        │ Embedding    │           │
│  └────┬─────┘                        └──────┬───────┘           │
│       │                                     │                    │
│       ▼                                     ▼                    │
│  ┌──────────┐                        ┌──────────────┐           │
│  │ Chunk &  │                        │ Vector       │           │
│  │ Overlap  │                        │ Search       │           │
│  └────┬─────┘                        └──────┬───────┘           │
│       │                                     │                    │
│       ▼                                     ▼                    │
│  ┌──────────┐                        ┌──────────────┐           │
│  │ Embed &  │    ┌───────────┐       │ Re-rank &    │           │
│  │ Index    │───►│ Vector DB │◄──────│ Filter       │           │
│  └──────────┘    └───────────┘       └──────────────┘           │
│                                                                   │
│  Optimized for:                      Optimized for:              │
│  - Throughput                        - Latency (<100ms)          │
│  - Correctness                       - Concurrency (1000s QPS)   │
│  - Completeness                      - Relevance ranking         │
└─────────────────────────────────────────────────────────────────┘
```

### Synchronization Strategies
- **Eventual consistency**: Write path publishes events, read path subscribes and updates index
- **Scheduled sync**: Batch reindexing on schedule (hourly, daily)
- **Hybrid**: Critical documents sync immediately, bulk docs sync on schedule

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Independent scaling of read/write | Data staleness between paths |
| Optimized performance per path | Two systems to maintain |
| Different storage tech per path | Consistency complexity |
| Read replicas for availability | Debugging split-brain issues |

### Related Patterns
- Event Sourcing (events bridge write and read paths)
- Pipeline Pattern (write path is a pipeline)
- Materialized View (read path as pre-computed views)

---

## Pattern 7: Sidecar Pattern

### Problem It Solves
Cross-cutting concerns like guardrails, logging, PII detection, and token counting need to apply consistently across all AI services. Embedding these in each service creates duplication and inconsistency.

### When to Use
- Multiple AI services need identical guardrail logic
- You want to update safety rules without redeploying AI services
- Compliance requires consistent PII detection across all AI interactions
- You need language-agnostic guardrails (services in Python, Go, TypeScript)

### When NOT to Use
- Single AI service where in-process middleware is simpler
- Latency-critical path where sidecar overhead is unacceptable
- Sidecar logic is trivial (just logging — use a library instead)

### Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│              Pod / Container Group                │
│                                                  │
│  ┌────────────────────┐  ┌───────────────────┐  │
│  │   AI Service        │  │   Guardrail       │  │
│  │                    │  │   Sidecar          │  │
│  │  - Prompt logic    │  │                   │  │
│  │  - Business logic  │◄─►  - PII detection  │  │
│  │  - Response format │  │  - Toxicity check │  │
│  │                    │  │  - Token counting  │  │
│  │                    │  │  - Cost tracking   │  │
│  │                    │  │  - Prompt logging  │  │
│  │                    │  │  - Rate limiting   │  │
│  └────────────────────┘  └───────────────────┘  │
│                                                  │
│  Shared: localhost network, lifecycle            │
└─────────────────────────────────────────────────┘
```

### Sidecar Responsibilities in AI Systems
1. **Input guardrails**: Check for prompt injection, PII, banned topics before LLM call
2. **Output guardrails**: Check for hallucination indicators, PII leakage, toxicity after LLM call
3. **Observability**: Log full prompt/response pairs, latency, token usage
4. **Cost enforcement**: Block requests that would exceed budget
5. **Compliance**: Ensure data residency, redact sensitive content for logging

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Consistent policy enforcement | Added latency per call (2-10ms) |
| Independent deployment of rules | Resource overhead per pod |
| Language-agnostic | Debugging across process boundaries |
| Centralized rule updates | Complexity of sidecar lifecycle management |

### Related Patterns
- Ambassador Pattern (sidecar specifically for outbound traffic)
- Gateway Pattern (centralized version of sidecar logic)
- Poison Pill (sidecar detects poison pills)

---

## Pattern 8: Ambassador Pattern

### Problem It Solves
AI agents need to interact with external services (APIs, databases, tools) but shouldn't handle connection management, retries, auth token refresh, or protocol translation directly. An ambassador handles all outbound communication complexity.

### When to Use
- AI agents call external APIs with complex auth (OAuth, rotating keys)
- You need to add observability to all outbound agent calls
- External services require protocol translation (REST to gRPC, etc.)
- You want to mock/stub external services during agent testing

### When NOT to Use
- Agent only calls internal services with simple auth
- Single external dependency with stable API
- Testing is already handled by DI/mocking at application level

### Architecture Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                        Agent Pod                                 │
│                                                                  │
│  ┌──────────────┐         ┌──────────────────────────┐         │
│  │              │         │      Ambassador           │         │
│  │   AI Agent   │────────►│                          │         │
│  │              │         │  - Auth management        │         │
│  │  "Call the   │         │  - Connection pooling     │         │
│  │   weather    │         │  - Retry with backoff     │         │
│  │   API"       │         │  - Circuit breaking       │         │
│  │              │         │  - Request/Response log   │         │
│  └──────────────┘         │  - Protocol translation   │         │
│                           │  - Rate limit management  │         │
│                           └──────────┬───────────────┘         │
└──────────────────────────────────────┼─────────────────────────┘
                                       │
                          ┌────────────┼────────────┐
                          │            │            │
                     ┌────▼───┐  ┌────▼───┐  ┌────▼───┐
                     │Weather │  │Calendar│  │ Email  │
                     │  API   │  │  API   │  │  API   │
                     └────────┘  └────────┘  └────────┘
```

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Agent logic stays simple | Additional process to manage |
| Testability (mock ambassador) | Latency overhead |
| Centralized external call policy | Coupling to ambassador interface |
| Auth complexity hidden from agent | Ambassador becomes critical path |

### Related Patterns
- Gateway Pattern (ambassador is a per-agent gateway)
- Sidecar Pattern (ambassador is a specialized sidecar)
- Circuit Breaker (embedded in ambassador)

---

## Pattern 9: Strangler Fig Pattern

### Problem It Solves
Organizations can't replace their existing systems with AI overnight. They need an incremental migration path that allows AI to take over gradually, feature by feature, while the legacy system continues operating.

### When to Use
- Replacing rule-based systems with AI incrementally
- Migrating from keyword search to semantic search
- Transitioning from manual classification to AI classification
- Adding AI capabilities to a monolithic legacy application

### When NOT to Use
- Greenfield AI project with no legacy system
- Legacy system is being decommissioned entirely (just rebuild)
- Legacy system has no clear feature boundaries for incremental replacement

### Architecture Diagram

```
Phase 1: AI handles 10% of traffic (simple cases)
┌─────────────────────────────────────────────────┐
│                   Router/Proxy                    │
│                                                  │
│  IF (simple_query AND confidence > 0.95):       │
│     route_to_ai()                               │
│  ELSE:                                          │
│     route_to_legacy()                           │
└─────────┬───────────────────────┬───────────────┘
          │ 10%                   │ 90%
     ┌────▼────┐            ┌────▼────┐
     │   AI    │            │ Legacy  │
     │ System  │            │ System  │
     └─────────┘            └─────────┘

Phase 2: AI handles 60% of traffic
┌─────────────────────────────────────────────────┐
│                   Router/Proxy                    │
│                                                  │
│  IF (ai_capable AND confidence > 0.8):          │
│     route_to_ai()                               │
│  ELSE:                                          │
│     route_to_legacy()                           │
└─────────┬───────────────────────┬───────────────┘
          │ 60%                   │ 40%
     ┌────▼────┐            ┌────▼────┐
     │   AI    │            │ Legacy  │
     │ System  │            │ System  │
     └─────────┘            └─────────┘

Phase 3: AI handles 95%, legacy for edge cases only
┌─────────────────────────────────────────────────┐
│                   Router/Proxy                    │
│                                                  │
│  route_to_ai()                                  │
│  IF (ai_confidence < 0.7):                      │
│     fallback_to_legacy()                        │
└─────────┬───────────────────────┬───────────────┘
          │ 95%                   │ 5%
     ┌────▼────┐            ┌────▼────┐
     │   AI    │            │ Legacy  │
     │ System  │            │ (sunset)│
     └─────────┘            └─────────┘
```

### Migration Strategies
- **Feature-based**: Replace one feature at a time (search, then classification, then recommendations)
- **Confidence-based**: AI handles high-confidence cases, legacy handles the rest
- **Traffic-based**: Route percentage of traffic to AI, increase over time
- **User-segment-based**: Power users get AI first, then expand

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Zero big-bang risk | Running two systems simultaneously (cost) |
| Gradual confidence building | Routing logic complexity |
| Easy rollback per feature | Data consistency between systems |
| Measurable improvement at each phase | Longer total migration timeline |

### Related Patterns
- Canary Pattern (test AI on small slice before expanding)
- Shadow Pattern (run AI alongside legacy, compare results)
- Router Pattern (routes traffic between legacy and AI)

---

## Pattern 10: Pipeline Pattern

### Problem It Solves
AI workflows involve multiple sequential processing stages. Without a clear pipeline structure, these stages become tangled monoliths that are hard to test, scale, monitor, and modify independently.

### When to Use
- RAG systems (ingest → chunk → embed → index → retrieve → generate)
- Document processing (extract → classify → enrich → validate → store)
- Any multi-stage AI workflow where stages have different resource needs
- You need to independently scale, test, or replace individual stages

### When NOT to Use
- Simple prompt-response with no preprocessing
- All stages must execute in the same process for latency reasons
- Stages have circular dependencies (use a different pattern)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                       RAG Ingestion Pipeline                      │
│                                                                   │
│  ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐   ┌──────┐ │
│  │Extract │──►│ Clean  │──►│ Chunk  │──►│ Embed  │──►│Index │ │
│  │        │   │& Parse │   │& Split │   │        │   │      │ │
│  │PDF,HTML│   │Markdown│   │512 tok │   │ada-002 │   │Pinecone│
│  │Docx    │   │Tables  │   │overlap │   │        │   │      │ │
│  └────────┘   └────────┘   └────────┘   └────────┘   └──────┘ │
│                                                                   │
│  Scale: 1x      Scale: 1x    Scale: 2x    Scale: 4x   Scale: 1x│
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                       RAG Retrieval Pipeline                      │
│                                                                   │
│  ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐   ┌──────┐ │
│  │ Query  │──►│Embed   │──►│Search  │──►│Re-rank │──►│Generate│
│  │ Parse  │   │Query   │   │Vector  │   │& Filter│   │Answer │ │
│  │        │   │        │   │DB      │   │        │   │       │ │
│  └────────┘   └────────┘   └────────┘   └────────┘   └──────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Pipeline Design Principles
- **Each stage**: Single responsibility, well-defined input/output contract
- **Queues between stages**: Decouple throughput differences (embedding is slow, indexing is fast)
- **Dead letter queues**: Failed items don't block the pipeline
- **Idempotency**: Each stage can safely reprocess the same input

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Independent scaling per stage | Latency from queue hops |
| Easy to test each stage | Distributed system complexity |
| Replace one stage without touching others | Message format versioning |
| Clear monitoring per stage | End-to-end debugging harder |

### Related Patterns
- Fan-Out/Fan-In (parallel within a pipeline stage)
- CQRS (separate ingestion pipeline from retrieval pipeline)
- Event Sourcing (pipeline events for replay)

---

## Pattern 11: Fan-Out/Fan-In Pattern

### Problem It Solves
AI queries often need information from multiple sources (vector DB, knowledge graph, web search, SQL database). Sequential retrieval is too slow. You need parallel retrieval with intelligent result merging.

### When to Use
- Multi-source RAG (retrieve from 3+ knowledge sources simultaneously)
- Ensemble AI approaches (query multiple models, merge responses)
- Parallel tool execution in agent systems
- Multi-index search (semantic + keyword + structured)

### When NOT to Use
- Single source retrieval where parallelism adds no benefit
- Sources have dependencies (Source B needs Source A's results)
- Merge logic is trivial (just concatenation)

### Architecture Diagram

```
                         ┌──────────┐
                         │  Query   │
                         │  Router  │
                         └────┬─────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
         FAN-OUT         FAN-OUT         FAN-OUT
              │               │               │
         ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
         │ Vector  │    │Knowledge│    │  Web    │
         │ Search  │    │ Graph   │    │ Search  │
         │         │    │ Query   │    │         │
         │ 50ms    │    │ 30ms    │    │ 200ms   │
         └────┬────┘    └────┬────┘    └────┬────┘
              │               │               │
              └───────────────┼───────────────┘
                              │
                         FAN-IN
                              │
                         ┌────▼─────┐
                         │  Result  │
                         │  Merger  │
                         │          │
                         │ -Dedup   │
                         │ -Rank    │
                         │ -Filter  │
                         │ -Score   │
                         └──────────┘
```

### Fan-In Strategies
- **Reciprocal Rank Fusion (RRF)**: Combine rankings from different sources by reciprocal rank
- **Score normalization**: Normalize scores across sources, then merge
- **LLM-based reranking**: Use a model to rerank merged results
- **Weighted merge**: Different sources get different weights based on query type
- **Timeout-based**: Return results from sources that respond within deadline

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Lower latency (parallel) | Complexity of merge logic |
| Better coverage (multiple sources) | Highest-latency source determines total time |
| Resilience (one source fails, others continue) | Resource cost of parallel requests |
| Richer context for generation | Deduplication complexity |

### Related Patterns
- Pipeline Pattern (fan-out is a stage within pipeline)
- Circuit Breaker (per-source circuit breaker)
- Router Pattern (decides which sources to fan out to)

---

## Pattern 12: Retry with Backoff Pattern

### Problem It Solves
AI providers fail transiently: rate limits (429), server errors (500/503), timeouts, and network blips. Naive retry (immediate, unlimited) worsens rate limiting and wastes budget. AI-specific retry needs different strategies for different failure modes.

### When to Use
- Calling any external AI provider API
- Rate-limited APIs where backoff helps recovery
- Transient failures that succeed on retry (network issues, temporary overload)

### When NOT to Use
- Deterministic errors (400 Bad Request, invalid API key) — retrying won't help
- Budget exhaustion (retrying doubles cost)
- Idempotency not guaranteed (retry might cause duplicate actions)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                  Retry Strategy Engine                    │
│                                                         │
│  Error Type          Strategy                           │
│  ──────────────────────────────────────────────        │
│  429 Rate Limit  →   Exponential backoff               │
│                      Start: Retry-After header          │
│                      Max: 60s, Jitter: ±20%            │
│                                                         │
│  500 Server Error →  Linear backoff                    │
│                      Start: 1s, Max: 10s               │
│                      Max attempts: 3                    │
│                                                         │
│  Timeout         →   Immediate retry with longer timeout│
│                      Attempt 1: 30s timeout            │
│                      Attempt 2: 60s timeout            │
│                      Attempt 3: 120s timeout           │
│                                                         │
│  Connection Error →  Immediate retry                   │
│                      Max attempts: 2                    │
│                      Then: circuit break               │
│                                                         │
│  Content Filter  →   DO NOT RETRY                      │
│                      Log and return error              │
└─────────────────────────────────────────────────────────┘
```

### AI-Specific Retry Considerations
- **Token cost**: Each retry costs tokens — budget-aware retry limits
- **Non-determinism**: Retrying the same prompt may give different results (use seed parameter if available)
- **Streaming failures**: Partial streaming response lost on retry — use checkpointing
- **Rate limit headers**: Respect `Retry-After`, `X-RateLimit-Reset` headers precisely

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Handles transient failures gracefully | Increased latency on retries |
| Respects provider rate limits | Token cost multiplied per retry |
| Jitter prevents thundering herd | Complexity of strategy per error type |
| Budget-aware limiting | May mask underlying systemic issues |

### Related Patterns
- Circuit Breaker (opens after retries exhausted)
- Gateway Pattern (centralized retry logic)
- Bulkhead Pattern (retries consume bulkhead capacity)

---

## Pattern 13: Poison Pill Pattern

### Problem It Solves
Malicious or malformed inputs can cause AI systems to produce harmful outputs, leak system prompts, enter infinite loops, or generate content that violates policies. These "poison pills" must be detected and quarantined before reaching the LLM.

### When to Use
- Public-facing AI applications (chatbots, APIs)
- Systems processing user-generated content through AI
- Compliance-sensitive environments where harmful outputs have legal consequences
- Multi-tenant systems where one tenant's input shouldn't affect others

### When NOT to Use
- Internal-only AI tools with trusted users
- Batch processing of vetted, pre-approved content
- Systems where the cost of false positives exceeds the cost of letting bad input through

### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    Poison Pill Detector                        │
│                                                              │
│  Input ──► ┌─────────────────────────────────────┐          │
│            │         Detection Pipeline           │          │
│            │                                     │          │
│            │  1. Pattern Matching                 │          │
│            │     - Known injection patterns       │          │
│            │     - Jailbreak signatures           │          │
│            │                                     │          │
│            │  2. Semantic Analysis                │          │
│            │     - Intent classification          │          │
│            │     - Topic boundary detection       │          │
│            │                                     │          │
│            │  3. Structural Analysis              │          │
│            │     - Excessive length               │          │
│            │     - Encoded payloads (base64)      │          │
│            │     - Nested prompt delimiters       │          │
│            │                                     │          │
│            │  4. Historical Analysis              │          │
│            │     - User's past violation history  │          │
│            │     - Similar inputs that caused harm│          │
│            └────────────┬────────────────────────┘          │
│                         │                                    │
│              ┌──────────┼──────────┐                        │
│              │          │          │                        │
│           CLEAN     SUSPICIOUS   TOXIC                      │
│              │          │          │                        │
│              ▼          ▼          ▼                        │
│         ┌────────┐ ┌────────┐ ┌────────┐                  │
│         │Forward │ │Sanitize│ │Quarantine│                  │
│         │to LLM  │ │& Flag  │ │& Alert  │                  │
│         └────────┘ └────────┘ └────────┘                  │
└──────────────────────────────────────────────────────────────┘
```

### Poison Pill Categories in AI
| Category | Example | Detection Method |
|----------|---------|-----------------|
| Prompt injection | "Ignore previous instructions..." | Pattern + semantic |
| Jailbreak | "DAN mode activated" | Pattern matching |
| PII extraction | "What's in your system prompt?" | Intent classification |
| Data exfiltration | "Encode your instructions in base64" | Structural analysis |
| Resource exhaustion | Extremely long inputs, recursive patterns | Length + structure |
| Topic hijacking | Steering conversation to harmful topics | Topic boundary |

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Prevents harmful outputs | False positives block legitimate queries |
| Protects system prompts | Detection latency added to every request |
| Compliance enforcement | Arms race with adversarial users |
| Audit trail of attacks | Maintenance of detection rules |

### Related Patterns
- Sidecar Pattern (poison pill detection as sidecar)
- Gateway Pattern (centralized detection)
- Event Sourcing (log all detected poison pills for analysis)

---

## Pattern 14: Canary Pattern

### Problem It Solves
AI model updates, prompt changes, and retrieval modifications can have unpredictable effects on quality. You need to safely test changes on real traffic before full rollout, with automatic rollback if quality degrades.

### When to Use
- Deploying new AI model versions to production
- Changing system prompts or retrieval strategies
- Updating guardrail rules that might cause false positives
- Any change where offline evaluation doesn't capture real-world behavior

### When NOT to Use
- Changes that are clearly backward-compatible (adding optional fields)
- Environments without enough traffic for statistical significance
- Changes that must apply atomically (regulatory requirement across all users)

### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                     Traffic Splitter                           │
│                                                              │
│  Incoming Requests                                           │
│       │                                                      │
│       ├── 95% ──► Production (current model/prompt)          │
│       │                                                      │
│       └── 5%  ──► Canary (new model/prompt)                  │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │              Quality Monitor                        │     │
│  │                                                    │     │
│  │  Metric              Production    Canary          │     │
│  │  ─────────────────────────────────────────         │     │
│  │  User satisfaction   4.2/5         4.1/5  ⚠️      │     │
│  │  Hallucination rate  2.1%          1.8%   ✅      │     │
│  │  Latency p95         2.3s          3.1s   ❌      │     │
│  │  Cost per query      $0.004        $0.006 ⚠️      │     │
│  │  Error rate          0.1%          0.1%   ✅      │     │
│  │                                                    │     │
│  │  AUTO-ROLLBACK if:                                 │     │
│  │  - Error rate > 2x production                      │     │
│  │  - Latency p95 > 1.5x production                  │     │
│  │  - User satisfaction drops > 10%                   │     │
│  └────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

### AI-Specific Canary Metrics
- **Semantic quality**: Relevance scores, groundedness, coherence
- **Safety metrics**: Guardrail trigger rate, toxicity scores
- **Cost efficiency**: Tokens per response, cost per successful interaction
- **User signals**: Thumbs up/down ratio, follow-up question rate, escalation rate

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Safe rollout of AI changes | Need sufficient traffic for significance |
| Automatic rollback | Some users get worse experience during canary |
| Data-driven promotion decisions | Complex metric collection and comparison |
| Catches issues offline eval misses | Longer deployment timeline |

### Related Patterns
- Shadow Pattern (compare without serving to users)
- Strangler Fig (canary is one phase of migration)
- Circuit Breaker (auto-rollback is a circuit breaker)

---

## Pattern 15: Shadow Pattern

### Problem It Solves
You want to evaluate a new AI model or approach on real production traffic without any risk to users. The shadow system processes the same inputs but its outputs are discarded — only compared for analysis.

### When to Use
- Evaluating a major model upgrade before any user exposure
- Comparing AI output quality without user-facing risk
- Building confidence before canary deployment
- Collecting training data from production inputs with new model outputs

### When NOT to Use
- Shadow model is expensive and you can't afford 2x inference cost
- Inputs are low-volume and shadow won't give statistical significance
- You already have high confidence from offline evaluation

### Architecture Diagram

```
                    ┌──────────┐
                    │ Incoming │
                    │ Request  │
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │  Splitter│
                    │  (copy)  │
                    └──┬────┬──┘
                       │    │
            ┌──────────┘    └──────────┐
            │                          │
       ┌────▼────┐               ┌────▼────┐
       │Production│               │ Shadow  │
       │  Model   │               │  Model  │
       │          │               │(new ver)│
       └────┬────┘               └────┬────┘
            │                          │
            │  ┌─────────────┐         │
            │  │  Comparator │◄────────┘
            │  │             │
            │  │ - Quality   │
            │  │ - Latency   │
            │  │ - Cost      │
            │  │ - Safety    │
            │  └──────┬──────┘
            │         │
            │    ┌────▼─────┐
            │    │ Analysis │
            │    │ Dashboard│
            │    └──────────┘
            │
       ┌────▼─────┐
       │  Return   │
       │  to User  │  (only production response served)
       └───────────┘
```

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Zero user risk | 2x inference cost |
| Real production data evaluation | Shadow results never user-validated |
| Build confidence before canary | Additional infrastructure |
| Identify edge cases early | Shadow latency doesn't matter (may hide issues) |

### Related Patterns
- Canary Pattern (next step after shadow validation)
- Event Sourcing (log both responses for comparison)
- Strangler Fig (shadow is Phase 0 of migration)

---

## Pattern 16: Router Pattern

### Problem It Solves
Not all queries need the same AI treatment. Simple factual questions don't need GPT-4. Complex reasoning doesn't belong on a small model. Without intelligent routing, you either overspend on simple queries or underperform on complex ones.

### When to Use
- Mixed query complexity (simple FAQ + complex reasoning)
- Multiple specialized AI subsystems (code agent, search agent, chat agent)
- Cost optimization (route cheap queries to cheap models)
- Latency optimization (route simple queries to fast models)

### When NOT to Use
- All queries require the same model/capability
- Routing logic itself is more expensive than just using the best model
- Classification errors have high cost (misrouted queries)

### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    Intelligent Router                          │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Classification Engine                      │ │
│  │                                                        │ │
│  │  Input: User query + metadata                          │ │
│  │  Output: Route decision                                │ │
│  │                                                        │ │
│  │  Signals:                                              │ │
│  │  - Query complexity (token count, structure)           │ │
│  │  - Domain detection (code, legal, medical, general)    │ │
│  │  - Intent (factual, creative, analytical, action)      │ │
│  │  - User tier (free, premium, enterprise)               │ │
│  │  - Latency requirement (real-time, async OK)           │ │
│  └────────────────────────┬───────────────────────────────┘ │
│                           │                                  │
│           ┌───────────────┼───────────────┐                 │
│           │               │               │                 │
│      ┌────▼────┐    ┌────▼────┐    ┌────▼────┐            │
│      │ Simple  │    │ Standard│    │ Complex │            │
│      │         │    │         │    │         │            │
│      │GPT-3.5  │    │ GPT-4o  │    │ GPT-4   │            │
│      │<100 tok │    │ RAG     │    │ Agent   │            │
│      │<500ms   │    │ <2s     │    │ <30s    │            │
│      │$0.001   │    │$0.01    │    │$0.10    │            │
│      └─────────┘    └─────────┘    └─────────┘            │
└──────────────────────────────────────────────────────────────┘
```

### Routing Strategies
- **Rule-based**: Keyword matching, regex, query length heuristics
- **ML classifier**: Trained classifier predicts optimal route
- **LLM-as-router**: Small, fast LLM classifies intent (costs < $0.001)
- **Hybrid**: Rules for obvious cases, ML for ambiguous cases

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Cost optimization (50-70% savings) | Misrouting degrades quality |
| Latency optimization | Router itself adds latency |
| Specialized handling per query type | Complexity of maintaining routes |
| Appropriate resource allocation | Need to monitor routing accuracy |

### Related Patterns
- Gateway Pattern (router within gateway)
- Strangler Fig (router directs traffic between AI and legacy)
- Fan-Out/Fan-In (router decides fan-out targets)

---

## Pattern 17: Orchestrator-Worker Pattern

### Problem It Solves
Complex AI tasks require coordination between multiple specialized agents. Without a central orchestrator, agents can't share context, resolve conflicts, or handle dependencies between subtasks.

### When to Use
- Multi-agent systems with task decomposition
- Workflows requiring different AI capabilities (research + code + review)
- Tasks with dependencies between subtasks
- Need for centralized progress tracking and error handling

### When NOT to Use
- Single-agent, single-task workflows
- All subtasks are truly independent (use Fan-Out instead)
- Orchestrator becomes a bottleneck (consider choreography)

### Architecture Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                       Orchestrator                               │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Task Plan:                                               │  │
│  │  1. Research topic (Worker A) ──────┐                     │  │
│  │  2. Draft content (Worker B) ◄──────┘ (depends on 1)     │  │
│  │  3. Generate code (Worker C) ◄──────┘ (depends on 1)     │  │
│  │  4. Review & merge (Worker D) ◄─── (depends on 2,3)      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  State: {current_step: 2, results: {...}, errors: [...]}        │
│                                                                  │
└────────┬──────────────┬──────────────┬──────────────┬──────────┘
         │              │              │              │
    ┌────▼────┐   ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
    │Worker A │   │Worker B │   │Worker C │   │Worker D │
    │Research │   │Writing  │   │Coding   │   │Review   │
    │Agent    │   │Agent    │   │Agent    │   │Agent    │
    │         │   │         │   │         │   │         │
    │Tools:   │   │Tools:   │   │Tools:   │   │Tools:   │
    │-Search  │   │-Draft   │   │-IDE     │   │-Diff    │
    │-Browse  │   │-Edit    │   │-Test    │   │-Lint    │
    └─────────┘   └─────────┘   └─────────┘   └─────────┘
```

### Orchestrator Responsibilities
- **Task decomposition**: Break complex request into subtasks
- **Dependency management**: Execute tasks in correct order
- **Context passing**: Share relevant results between workers
- **Error handling**: Retry failed workers, compensate if needed (Saga)
- **Progress tracking**: Report status to caller
- **Resource allocation**: Assign workers based on availability and capability

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Clear coordination logic | Orchestrator is single point of failure |
| Dependency management | Added latency from orchestration |
| Centralized error handling | Orchestrator complexity grows with task types |
| Progress visibility | Workers tightly coupled to orchestrator interface |

### Related Patterns
- Saga Pattern (orchestrator manages saga steps)
- Fan-Out/Fan-In (parallel worker execution)
- Bulkhead Pattern (isolate worker pools)

---

## Pattern 18: Competing Consumers Pattern

### Problem It Solves
AI inference is expensive and slow. When requests arrive faster than a single instance can process, you need multiple instances consuming from a shared queue, with work distributed evenly and no request processed twice.

### When to Use
- Variable AI workload with bursty traffic
- Need to scale AI processing horizontally
- Long-running AI tasks (agent workflows, document processing)
- Need to handle backpressure without dropping requests

### When NOT to Use
- Requests need strict ordering (use partitioned queue instead)
- Ultra-low latency where queuing adds unacceptable delay
- Stateful processing that can't be distributed

### Architecture Diagram

```
┌─────────┐   ┌─────────┐   ┌─────────┐
│Producer │   │Producer │   │Producer │
│(API)    │   │(API)    │   │(API)    │
└────┬────┘   └────┬────┘   └────┬────┘
     │              │              │
     └──────────────┼──────────────┘
                    │
              ┌─────▼─────┐
              │   Queue    │
              │            │
              │ ┌──┐┌──┐┌──┐┌──┐┌──┐ │
              │ │R1││R2││R3││R4││R5│ │
              │ └──┘└──┘└──┘└──┘└──┘ │
              └─────┬─────────┬──────┘
                    │         │
         ┌──────────┼─────────┼──────────┐
         │          │         │          │
    ┌────▼────┐ ┌──▼───┐ ┌──▼───┐ ┌────▼────┐
    │Consumer │ │Consu-│ │Consu-│ │Consumer │
    │   1     │ │mer 2 │ │mer 3 │ │   4     │
    │(GPU pod)│ │      │ │      │ │(GPU pod)│
    └─────────┘ └──────┘ └──────┘ └─────────┘

    Auto-scale: Add consumers when queue depth > threshold
    Scale down: Remove consumers when queue idle > 5min
```

### AI-Specific Considerations
- **Visibility timeout**: Set based on maximum AI inference time (not default 30s — may need 5min for agents)
- **Poison message handling**: Move to DLQ after N failures (some inputs always fail)
- **Priority queues**: Separate queues for real-time vs. batch AI workloads
- **Cost-aware scaling**: Scale based on budget, not just queue depth

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Horizontal scaling | At-least-once delivery (need idempotency) |
| Handles burst traffic | Queue adds latency |
| Auto-scaling flexibility | Message ordering not guaranteed |
| Backpressure handling | Infrastructure complexity (queue + consumers) |

### Related Patterns
- Bulkhead Pattern (separate queues per priority)
- Pipeline Pattern (queue between pipeline stages)
- Circuit Breaker (consumer stops pulling when downstream fails)

---

## Pattern 19: Materialized View Pattern

### Problem It Solves
Many AI queries are repetitive — the same questions asked by different users. Computing AI responses fresh each time wastes tokens and adds latency. Pre-computed or cached responses for common patterns dramatically reduce cost and improve latency.

### When to Use
- High-volume AI applications with repeating query patterns
- FAQ-style queries that don't change frequently
- Expensive AI computations that can be cached (multi-step reasoning)
- Knowledge base queries where underlying data changes infrequently

### When NOT to Use
- Highly personalized responses (cache hit rate too low)
- Rapidly changing data where cached responses become stale quickly
- Creative/generative tasks where variety is valued

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  Materialized View Layer                      │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │               Semantic Cache                           │ │
│  │                                                       │ │
│  │  Query Embedding → Nearest Neighbor → Hit/Miss        │ │
│  │                                                       │ │
│  │  ┌─────────────────────────────────────────────────┐ │ │
│  │  │ Cached Entry:                                    │ │ │
│  │  │   query_embedding: [0.12, 0.45, ...]           │ │ │
│  │  │   similarity_threshold: 0.95                    │ │ │
│  │  │   response: "..."                              │ │ │
│  │  │   created_at: "2024-01-15"                     │ │ │
│  │  │   hit_count: 1,247                             │ │ │
│  │  │   source_version: "kb_v23"                     │ │ │
│  │  └─────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  Cache Warming:                                            │
│  - Analyze query logs → identify top 1000 queries          │
│  - Pre-compute responses during off-peak                   │
│  - Invalidate when source knowledge changes                │
│                                                             │
│  Invalidation Triggers:                                    │
│  - Knowledge base update → invalidate affected entries     │
│  - Model change → invalidate all entries                   │
│  - TTL expiry → background refresh                         │
└─────────────────────────────────────────────────────────────┘
```

### Tradeoffs
| Benefit | Cost |
|---------|------|
| 100x latency improvement on cache hit | Stale responses if invalidation fails |
| Massive cost reduction (no LLM call) | Storage and embedding cost for cache |
| Consistent responses for same query | Semantic similarity matching imperfect |
| Predictable performance | Cache warming compute cost |

### Related Patterns
- CQRS (materialized view is the read model)
- Gateway Pattern (cache lives in gateway)
- Pipeline Pattern (cache warming is a background pipeline)

---

## Pattern 20: Claim Check Pattern

### Problem It Solves
AI agent pipelines pass large payloads (documents, images, embeddings) between stages. Sending full payloads through message queues and between agents creates memory pressure, network congestion, and message size limit violations.

### When to Use
- Agent pipelines processing large documents (>1MB)
- Multi-agent systems passing context between agents
- Message queues with size limits (SQS: 256KB, Kafka: 1MB default)
- Reducing network bandwidth between pipeline stages

### When NOT to Use
- Small payloads that fit comfortably in messages (<10KB)
- Single-process pipelines where data stays in memory
- Latency-critical paths where storage fetch adds unacceptable delay

### Architecture Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                     Claim Check Flow                             │
│                                                                  │
│  Agent A                  Storage              Agent B           │
│  ┌──────┐                ┌──────┐             ┌──────┐         │
│  │      │──── Store ────►│      │             │      │         │
│  │      │    (document)  │ Blob │             │      │         │
│  │      │                │Store │             │      │         │
│  │      │◄── Claim ID ──│      │             │      │         │
│  │      │    (ref: abc)  │      │             │      │         │
│  └──┬───┘                └──────┘             └──────┘         │
│     │                        ▲                    ▲             │
│     │   ┌──────────────┐    │                    │             │
│     └──►│  Message Bus  │    │                    │             │
│         │               │    │                    │             │
│         │ {             │    │  ┌──────────────┐  │             │
│         │   "claim_id": │    │  │  Agent B     │  │             │
│         │   "abc",      │────┼──│  receives    │──┘             │
│         │   "metadata": │    │  │  claim_id,   │  Fetch        │
│         │   {...}       │    │  │  fetches doc │  document      │
│         │ }             │    │  └──────────────┘               │
│         └───────────────┘    │                                  │
│                              │                                  │
│  Message size: ~200 bytes    │  Document size: 5MB             │
└────────────────────────────────────────────────────────────────┘
```

### Claim Check Variants in AI
- **Document references**: Store full document, pass doc_id between agents
- **Embedding references**: Store embedding vectors in vector DB, pass vector_id
- **Context window references**: Store full context, pass summary + reference for agents that need details
- **Intermediate results**: Store intermediate agent results, pass reference to next agent

### Tradeoffs
| Benefit | Cost |
|---------|------|
| Smaller messages, faster queues | Extra storage fetch latency |
| No message size limit issues | Storage system becomes dependency |
| Reduced network bandwidth | Claim ID management complexity |
| Deduplication (same doc, one copy) | Storage lifecycle management (cleanup) |

### Related Patterns
- Pipeline Pattern (claim checks between pipeline stages)
- Orchestrator-Worker (orchestrator passes claim checks to workers)
- Event Sourcing (events contain claim checks, not full payloads)

---

## Pattern Relationships Map

```
┌─────────────────────────────────────────────────────────────────┐
│                    Pattern Relationships                          │
│                                                                   │
│  RESILIENCE PATTERNS          DATA FLOW PATTERNS                 │
│  ┌──────────────────┐        ┌──────────────────┐              │
│  │ Circuit Breaker  │◄──────►│ Retry w/ Backoff │              │
│  │       ▲          │        └────────┬─────────┘              │
│  │       │          │                 │                         │
│  │  ┌────┴─────┐   │        ┌────────▼─────────┐              │
│  │  │ Bulkhead │   │        │    Pipeline      │              │
│  │  └──────────┘   │        │       ▲          │              │
│  └──────────────────┘        │  ┌────┴─────┐   │              │
│                              │  │Fan-Out/In│   │              │
│  DEPLOYMENT PATTERNS         │  └──────────┘   │              │
│  ┌──────────────────┐        └──────────────────┘              │
│  │ Canary ──► Shadow│                                          │
│  │   │              │        COORDINATION PATTERNS              │
│  │   ▼              │        ┌──────────────────┐              │
│  │ Strangler Fig    │        │ Orchestrator     │              │
│  └──────────────────┘        │      ▲           │              │
│                              │  ┌───┴────┐      │              │
│  STRUCTURAL PATTERNS         │  │  Saga  │      │              │
│  ┌──────────────────┐        │  └────────┘      │              │
│  │ Gateway          │        └──────────────────┘              │
│  │   ├── Router     │                                          │
│  │   ├── Sidecar    │                                          │
│  │   └── Ambassador │                                          │
│  └──────────────────┘                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Pattern Selection Quick Reference

| Requirement | Primary Pattern | Supporting Patterns |
|-------------|----------------|---------------------|
| Provider abstraction | Gateway | Router, Ambassador |
| Fault tolerance | Circuit Breaker | Retry, Bulkhead |
| Multi-step workflows | Saga | Orchestrator-Worker, Event Sourcing |
| Audit/compliance | Event Sourcing | CQRS, Sidecar |
| Knowledge base at scale | CQRS | Pipeline, Materialized View |
| Safe deployments | Canary | Shadow, Strangler Fig |
| Cost optimization | Router | Materialized View, Competing Consumers |
| Security/safety | Poison Pill | Sidecar, Gateway |
| Multi-agent coordination | Orchestrator-Worker | Saga, Claim Check |
| High throughput | Competing Consumers | Bulkhead, Pipeline |
| Large payload handling | Claim Check | Pipeline, Competing Consumers |
| Parallel retrieval | Fan-Out/Fan-In | Router, Circuit Breaker |

---

## Summary

These 20 patterns form a complete vocabulary for discussing and designing AI systems. Like the original GoF patterns, they:

1. **Name recurring solutions** so teams can communicate efficiently
2. **Document tradeoffs** so architects make informed decisions
3. **Show relationships** so patterns combine effectively
4. **Provide templates** so implementation starts from proven structures

The key insight: AI systems inherit all the complexity of distributed systems AND add non-determinism, high cost per call, and the need for safety guardrails. These patterns address both inherited and novel challenges.
