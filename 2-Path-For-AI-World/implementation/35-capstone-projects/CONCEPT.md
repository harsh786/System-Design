# Module 35: Capstone Projects — Portfolio for Staff AI Architect

## Why Portfolio Projects Matter

A Staff AI Architect doesn't just talk about systems—they build them, evaluate them, and make decisions that survive production. These 9 capstone projects form a portfolio that demonstrates:

1. **End-to-end system thinking** — Not just components, but full systems with observability, failure modes, and operational runbooks
2. **Decision-making under uncertainty** — Every project includes explicit tradeoffs, alternatives considered, and rationale documented as ADRs
3. **Production readiness** — Not toy demos; each project handles auth, rate limiting, monitoring, graceful degradation
4. **Evaluation rigor** — Every AI component has measurable quality metrics with regression detection
5. **Cost awareness** — Token budgets, compute costs, and ROI framing for every design choice

## How to Present Each Project

Each capstone should be presented with:

### Architecture Document Structure
```
1. Problem Statement & Business Context
2. Requirements (functional, non-functional, constraints)
3. High-Level Architecture (C4 Level 1-2)
4. Component Deep Dives (C4 Level 3)
5. Data Flow Diagrams
6. Key Architecture Decisions (ADRs)
7. Failure Modes & Mitigations
8. Evaluation Strategy & Metrics
9. Cost Model
10. Operational Runbook
11. Future Evolution Path
```

### What Reviewers Look For
- Can you explain WHY, not just WHAT?
- Do you understand the failure modes?
- Can you articulate tradeoffs numerically?
- Do you have evidence (metrics, experiments) backing decisions?
- Can you scope appropriately (MVP vs. full vision)?

---

## Project 1: Enterprise RAG Platform

**Complexity:** High | **Duration:** 4-6 weeks | **Key Skills:** Information retrieval, vector DBs, chunking, evaluation

### Scope
Build a production RAG system that ingests enterprise documents (PDF, DOCX, HTML, Confluence, Slack), chunks intelligently, retrieves via hybrid search, reranks, generates with citations, and respects document-level ACLs.

### Architecture Components
- **Ingestion Pipeline**: Multi-format parser → metadata extractor → chunker → embedder → vector store
- **Chunking Strategies**: Fixed-size, semantic, recursive, document-structure-aware, parent-child
- **Hybrid Retrieval**: Dense (embedding similarity) + Sparse (BM25) with reciprocal rank fusion
- **Reranking**: Cross-encoder reranker with score calibration
- **Citation Builder**: Span-level attribution mapping generated text back to source chunks
- **ACL Filtering**: Pre-retrieval filtering based on user permissions (group membership, document classification)
- **Eval Dashboard**: Retrieval precision/recall, answer faithfulness, latency percentiles, cost per query

### Key Decisions
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Chunk size | 512 tokens with 50-token overlap | Balances context vs. precision; validated via retrieval eval |
| Embedding model | text-embedding-3-large (3072d) | Best quality/cost for enterprise docs; supports matryoshka |
| Vector DB | pgvector (start) → Qdrant (scale) | Operational simplicity first; migration path clear |
| Reranker | Cross-encoder (ms-marco-MiniLM) | 15% MRR improvement justifies 80ms latency addition |
| ACL enforcement | Pre-filter with bitmap index | Post-filter risks empty results; pre-filter is deterministic |

### Evaluation Strategy
- **Retrieval**: MRR@10, Recall@20, NDCG@10 on golden QA pairs
- **Generation**: Faithfulness (claim-level), Answer relevance, Citation precision
- **End-to-End**: Task completion rate, user satisfaction (thumbs up/down)
- **Operational**: P50/P95/P99 latency, cost per query, cache hit rate

---

## Project 2: Agentic RAG Assistant

**Complexity:** Very High | **Duration:** 4-6 weeks | **Key Skills:** Agent orchestration, tool use, confidence estimation

### Scope
Build an AI assistant that decomposes complex questions, iteratively retrieves information, uses SQL and API tools, verifies claims, estimates confidence, and knows when to abstain or escalate to humans.

### Architecture Components
- **Query Decomposition**: Break complex queries into sub-queries with dependency graph
- **Iterative Retrieval**: Retrieve → assess sufficiency → retrieve more or synthesize
- **SQL Tool**: Natural language to SQL with schema awareness and result interpretation
- **API Tool**: Structured API calls with retry, pagination, and result parsing
- **Claim Verification**: Extract claims from generated answer, verify each against sources
- **Confidence Scoring**: Composite score from retrieval quality, source agreement, claim verification
- **Abstention Logic**: Refuse to answer when confidence < threshold; explain what's missing
- **Human Escalation**: Route to human when: low confidence, sensitive topic, conflicting sources, policy violation

### Key Design Patterns
- **ReAct Loop**: Reason → Act → Observe → Reason (with max iterations)
- **Sufficiency Check**: After each retrieval, LLM judges if enough info exists to answer
- **Claim-Level Grounding**: Every sentence maps to source(s) or is flagged as unsupported
- **Graceful Degradation**: Partial answers with explicit gaps > confident wrong answers

---

## Project 3: Evaluation Platform

**Complexity:** High | **Duration:** 3-5 weeks | **Key Skills:** ML evaluation, statistics, CI/CD integration

### Scope
Build a platform that manages golden datasets, computes retrieval/RAG/agent metrics, runs LLM-as-judge evaluations with calibration, integrates with CI/CD as quality gates, and detects regressions.

### Architecture Components
- **Golden Dataset Manager**: CRUD for QA pairs with versioning, tagging, difficulty labels
- **Retrieval Metrics**: Precision@K, Recall@K, MRR, NDCG, MAP
- **RAG Metrics**: Faithfulness, Answer Relevance, Context Relevance, Groundedness
- **Agent Metrics**: Task completion, tool accuracy, trajectory efficiency, cost per task
- **LLM-as-Judge**: Configurable rubrics, calibration against human labels, inter-rater agreement
- **Human Review Queue**: Sample routing for calibration, disagreement resolution
- **CI Gate**: Pass/fail thresholds, regression detection (statistical significance testing)
- **Dashboard**: Time-series metrics, A/B comparisons, drill-down to failure cases

### Statistical Rigor
- Bootstrap confidence intervals for all metrics
- Two-sample hypothesis tests for regression detection
- Cohen's kappa for judge-human agreement
- Stratified sampling for representative evaluation

---

## Project 4: MCP Tool Ecosystem

**Complexity:** Medium-High | **Duration:** 3-4 weeks | **Key Skills:** Protocol design, security, tool orchestration

### Scope
Implement Model Context Protocol (MCP) servers for: knowledge base search, SQL query execution, ticketing system integration. Include permission management, audit logging, and human-in-the-loop approval for sensitive operations.

### Architecture Components
- **MCP Server Framework**: Tool registration, schema validation, execution, result formatting
- **Knowledge Base Tool**: Search, retrieve, summarize documents via MCP
- **SQL Tool**: Schema discovery, query execution, result pagination via MCP
- **Ticketing Tool**: Create, update, search, assign tickets via MCP
- **Permission Layer**: Tool-level and operation-level permissions per agent/user
- **Audit Log**: Every tool invocation logged with input, output, user, timestamp, cost
- **Approval Workflow**: Sensitive operations (write, delete, PII access) require human approval

---

## Project 5: A2A Multi-Agent System

**Complexity:** Very High | **Duration:** 4-6 weeks | **Key Skills:** Distributed systems, agent protocols, orchestration

### Scope
Build a multi-agent system using Agent-to-Agent (A2A) protocol: agent discovery via Agent Cards, supervisor agent for task routing, specialist agents (researcher, coder, reviewer), lifecycle management, and inter-agent authentication.

### Architecture Components
- **Agent Card Registry**: JSON-LD agent capability descriptors, discovery endpoint
- **Supervisor Agent**: Task decomposition, agent selection, result aggregation, conflict resolution
- **Specialist Agents**: Research (RAG), Code (generation + testing), Review (quality + security)
- **Task Lifecycle**: Submitted → Assigned → Working → Review → Complete/Failed
- **Communication**: Structured message passing with schema validation
- **Authentication**: mTLS between agents, capability-based authorization
- **Observability**: Distributed tracing across agent boundaries, cost attribution

---

## Project 6: AI Gateway

**Complexity:** High | **Duration:** 3-5 weeks | **Key Skills:** API design, distributed systems, caching, security

### Scope
Build a unified gateway that abstracts multiple LLM providers, routes intelligently, handles failover, tracks costs, enforces budgets, caches semantically similar requests, and applies guardrails.

### Architecture Components
- **Unified API**: Single API surface supporting OpenAI, Anthropic, Google, Azure formats
- **Router**: Route by model capability, cost, latency, availability
- **Fallback**: Circuit breaker per provider, automatic failover with model mapping
- **Cost Tracker**: Token counting, cost computation, per-tenant attribution
- **Budget Enforcement**: Hard/soft limits, alerts, throttling, quota management
- **Semantic Cache**: Embedding-based similarity cache with TTL and invalidation
- **Guardrails**: PII detection, prompt injection detection, content policy enforcement
- **Observability**: Request/response logging, latency histograms, error rates, cost dashboards

### Key Metrics
| Metric | Target | Rationale |
|--------|--------|-----------|
| P50 overhead | <20ms | Gateway shouldn't noticeably slow requests |
| P99 overhead | <100ms | Even cache misses should be fast |
| Cache hit rate | >30% | Justifies caching infrastructure cost |
| Failover time | <2s | Users shouldn't notice provider outages |
| Budget accuracy | ±5% | Business needs reliable cost tracking |

---

## Project 7: Million-User Simulation

**Complexity:** High | **Duration:** 3-4 weeks | **Key Skills:** Load testing, capacity planning, autoscaling

### Scope
Design and execute load tests simulating 1M concurrent users against an AI system. Implement sharding, queue management, autoscaling policies, SLO dashboards, and operational runbooks.

### Architecture Components
- **Load Generator**: Realistic traffic patterns (burst, ramp, sustained), user behavior models
- **Sharding Strategy**: Request routing by tenant, consistent hashing, rebalancing
- **Queue Management**: Priority queues, backpressure, dead letter queues, replay
- **Autoscaling**: Custom metrics (queue depth, GPU utilization, token throughput), predictive scaling
- **SLO Dashboard**: Real-time SLI tracking, error budget burn rate, alerting
- **Runbooks**: Capacity alerts, degradation procedures, incident response

---

## Project 8: Agent Training Lab

**Complexity:** High | **Duration:** 3-5 weeks | **Key Skills:** Agent evaluation, experimentation, optimization

### Scope
Build a platform for systematically improving agents: collect traces, cluster failures, generate variants (prompts, tools, workflows), compare via evaluation, deploy winners via canary, track cost per task over time.

### Architecture Components
- **Trace Collector**: Structured logging of every agent step (thought, action, observation, result)
- **Failure Clustering**: Embed failure traces, cluster similar failures, prioritize by frequency/impact
- **Variant Generator**: Systematic prompt/tool/workflow variations for A/B testing
- **Eval Comparator**: Side-by-side evaluation with statistical significance testing
- **Canary Deployer**: Gradual rollout of winning variants with automatic rollback
- **Cost Optimizer**: Track cost per task, identify expensive patterns, suggest optimizations

---

## Project 9: AI Architecture Review Board

**Complexity:** Medium | **Duration:** 2-3 weeks | **Key Skills:** Governance, risk management, process design

### Scope
Build tooling for an AI Architecture Review Board: intake forms, automated risk tiering, checklists (privacy, security, UX, vendor), readiness assessments, and ADR generation.

### Architecture Components
- **Intake Form**: Structured project description, AI components, data sources, user impact
- **Risk Tiering**: Automated scoring (PII exposure, decision autonomy, blast radius, reversibility)
- **Checklists**: Privacy (GDPR, data retention), Security (prompt injection, data leakage), UX (transparency, recourse), Vendor (lock-in, SLA, exit strategy)
- **Readiness Assessment**: Evaluation coverage, monitoring, rollback plan, cost model, documentation
- **ADR Generator**: Template-based ADR creation from review findings
- **Dashboard**: Pipeline of reviews, SLA tracking, common findings, trend analysis

---

## Cross-Cutting Concerns (All Projects)

### Security
- Authentication & authorization at every boundary
- Input validation and sanitization
- Secrets management (never in code)
- Audit logging for compliance

### Observability
- Structured logging with correlation IDs
- Distributed tracing (OpenTelemetry)
- Metrics (RED: Rate, Errors, Duration)
- Alerting with runbooks

### Cost Management
- Token counting and attribution
- Budget alerts and enforcement
- Cost per query/task tracking
- Optimization recommendations

### Testing
- Unit tests for business logic
- Integration tests for tool interactions
- End-to-end tests for critical paths
- Evaluation tests for AI quality

---

## Portfolio Presentation Strategy

### For Interviews
1. Pick 2-3 projects most relevant to the role
2. Prepare 5-minute walkthrough of each (problem → design → tradeoffs → results)
3. Have metrics ready (latency improved X%, cost reduced Y%, quality increased Z%)
4. Anticipate "what would you do differently?" questions

### For Internal Promotion
1. Map each project to business impact
2. Show cross-team influence (who adopted your patterns?)
3. Document knowledge sharing (tech talks, design docs, mentoring)
4. Demonstrate scope increase over time

### For Open Source / Blog
1. Extract reusable patterns into libraries
2. Write design decision posts (not just "how I built X")
3. Share evaluation results openly (builds credibility)
4. Contribute to standards (MCP, A2A, OpenTelemetry)
