# Senior / Principal Agentic AI Architect Roadmap and Interview Handbook

**Version:** 2026-05-21  
**Audience:** Senior AI Architect, Generative AI Architect, Agentic AI Architect, Staff AI Engineer, Principal AI Platform Engineer, AI Platform Architect  
**Goal:** Become capable of designing, evaluating, securing, deploying, scaling, governing, and continuously improving production-grade Agentic AI systems.

---

## Table of Contents

1. Target Role and Mindset
2. Complete Agentic AI Reference Architecture
3. Full Learning Roadmap
4. Enterprise Architect Add-On Roadmap
5. RAG, Agentic RAG, and Knowledge Architecture
6. Agents, Tools, MCP, A2A, and Registries
7. Evaluation, Golden Datasets, and Confidence Scoring
8. Security, Guardrails, Authentication, and Authorization
9. Observability, AI Gateway, LLMOps, AgentOps, and SRE
10. Production Deployment and Scaling to Millions of Users
11. Vector Databases and Embedding Models
12. Tuning, Optimization, and Token Reduction
13. Governance, Compliance, and Responsible AI
14. Capstone Portfolio Projects
15. Production Checklists
16. Architecture Templates
17. Top 100 Senior-Level Interview Questions with Answer Blueprints
18. 12-Month Execution Plan
19. Final Interview Preparation Strategy
20. References

---

# 1. Target Role and Mindset

A world-class Agentic AI architect is not just someone who can build a chatbot, connect LangChain to a vector database, or write prompts.

A world-class architect can design the full system:

- business use case and ROI
- model strategy
- RAG and knowledge architecture
- agent orchestration
- tool and protocol architecture
- MCP and A2A ecosystems
- evaluation and golden datasets
- confidence scoring
- guardrails and security
- authentication and authorization
- AI gateway and model routing
- observability and tracing
- production deployment
- scaling and cost optimization
- governance and compliance
- incident response
- continuous improvement

Your target statement:

> I can design, secure, evaluate, deploy, scale, govern, and continuously improve enterprise-grade Agentic AI platforms.

The difference between a normal AI developer and a senior AI architect is this:

| AI Developer | Senior Agentic AI Architect |
|---|---|
| Builds chatbot demos | Builds production AI platforms |
| Focuses on prompts | Focuses on data, evals, security, scale, and cost |
| Uses LangChain blindly | Chooses framework based on architecture tradeoffs |
| Tests manually | Builds golden datasets and automated evals |
| Trusts the model | Builds guardrails, verification, and human review |
| Ignores operations | Designs SLOs, runbooks, rollback, and incident response |
| Thinks vector DB solves everything | Designs full knowledge architecture |

---

# 2. Complete Agentic AI Reference Architecture

```text
Users / Channels
  - Web application
  - Mobile application
  - Enterprise chat
  - Voice interface
  - Internal business applications
        |
        v
API Gateway
  - TLS
  - WAF
  - request validation
  - rate limiting
  - API versioning
        |
        v
Identity and Policy Layer
  - OAuth2 / OIDC / SSO
  - JWT validation
  - RBAC / ABAC / ReBAC
  - tenant isolation
  - policy engine
  - consent and risk policy
        |
        v
AI Gateway
  - model routing
  - provider abstraction
  - fallback
  - retry
  - budgets
  - token tracking
  - prompt cache
  - semantic cache
  - logging
  - guardrail hooks
        |
        v
Agent Orchestration Layer
  - intent classification
  - router agent
  - state machine
  - LangGraph-style workflow
  - planner / executor
  - supervisor / worker
  - memory controller
  - human approval checkpoint
  - max-step and timeout policy
        |
        +------------------------------------+
        |                                    |
        v                                    v
RAG / Knowledge Layer                    Tool / Action Layer
  - query rewriting                        - internal APIs
  - query decomposition                    - SQL tools
  - hybrid retrieval                       - SaaS tools
  - vector database                        - MCP servers
  - keyword search                         - A2A remote agents
  - reranker                               - code execution sandbox
  - metadata filters                       - ticketing systems
  - graph retrieval                        - CRM / ERP / HR systems
  - citation builder                       - approval workflow
  - groundedness verifier
        |                                    |
        +------------------+-----------------+
                           |
                           v
Model Layer
  - frontier LLMs
  - reasoning models
  - small task-specific models
  - embedding models
  - rerankers
  - classifiers
  - safety models
  - multimodal models
                           |
                           v
Evaluation, Observability, Governance
  - golden datasets
  - offline evals
  - online evals
  - RAG evals
  - trajectory evals
  - safety evals
  - OpenTelemetry traces
  - token/cost/latency metrics
  - user feedback
  - human review
  - audit logs
  - risk register
  - incident response
```

Architectural principle:

> Do not build an LLM app. Build an evaluated, observable, secure, governed AI system.

---

# 3. Full Learning Roadmap

## Phase 0: Engineering Foundation

Before advanced AI, become strong in backend and platform engineering.

Master:

- Python
- async/await
- FastAPI
- Pydantic
- REST APIs
- streaming APIs
- WebSockets
- OpenAPI specs
- idempotency
- retries
- circuit breakers
- PostgreSQL
- Redis
- object storage
- document stores
- Docker
- Kubernetes basics
- Helm basics
- CI/CD
- OAuth2
- OIDC
- JWT
- SSO
- API keys
- service accounts
- IAM
- secrets management
- structured logging
- OpenTelemetry
- Prometheus/Grafana basics
- unit tests
- integration tests
- contract tests
- load tests
- security tests

Build:

- authenticated FastAPI backend
- PostgreSQL + Redis service
- Docker Compose deployment
- CI/CD pipeline
- structured logs
- OpenTelemetry traces
- API rate limiting
- basic admin dashboard

Milestone:

> You can build reliable backend systems before adding AI complexity.

---

## Phase 1: LLM and Generative AI Fundamentals

Master:

- tokens and tokenization
- context windows
- input/output token cost
- temperature
- top-p
- deterministic vs creative generation
- system prompts
- developer instructions
- few-shot prompting
- structured outputs
- JSON schema output
- function calling
- tool calling
- streaming responses
- reasoning models
- small vs large models
- multimodal models
- hallucination behavior
- context engineering
- model comparison
- provider differences

Build:

- model comparison harness
- prompt regression test suite
- structured extraction service
- token and cost tracker
- latency benchmark

Milestone:

> You can justify model choice with data: accuracy, latency, safety, and cost.

---

## Phase 2: RAG Mastery

RAG means Retrieval-Augmented Generation. The system retrieves external knowledge and uses it to answer.

Basic RAG flow:

```text
User question
  -> query rewrite / classification
  -> retrieve relevant documents
  -> rerank and filter
  -> assemble context
  -> generate answer
  -> cite sources
  -> evaluate groundedness
```

Master ingestion:

- PDF parsing
- DOCX parsing
- HTML parsing
- email parsing
- Confluence ingestion
- SharePoint ingestion
- Google Drive ingestion
- S3 ingestion
- database ingestion
- scanned document OCR
- table extraction
- chart extraction
- page/section preservation
- duplicate removal
- boilerplate removal
- document versioning
- deletion propagation

Master chunking:

| Strategy | Use Case |
|---|---|
| fixed-size chunks | quick baseline |
| sentence chunks | clean text Q&A |
| section-aware chunks | policies, legal docs, manuals |
| parent-child chunks | retrieve small, show larger context |
| semantic chunks | irregular documents |
| hierarchical chunks | books, standards, long manuals |
| table-aware chunks | finance, legal, compliance |
| layout-aware chunks | scanned PDFs and forms |

Master retrieval:

- keyword search
- BM25
- dense vector search
- sparse vector search
- hybrid search
- metadata filtering
- reranking
- multi-query retrieval
- query decomposition
- HyDE-style retrieval
- self-query retrieval
- graph retrieval
- temporal retrieval
- multimodal retrieval
- access-controlled retrieval

Build:

- enterprise RAG app over real documents
- vector search
- keyword search
- hybrid retrieval
- reranker
- citations
- access control
- retrieval eval dashboard

Milestone:

> Your RAG system can prove it retrieved the right evidence, not just generate a nice answer.

---

## Phase 3: Advanced RAG and Agentic RAG

Agentic RAG allows the agent to plan retrieval, choose tools, retrieve iteratively, verify evidence, and decide whether to answer.

Agentic RAG flow:

```text
User asks complex question
  -> classify intent and risk
  -> decompose question
  -> choose retrieval tools
  -> retrieve from multiple sources
  -> rerank evidence
  -> check evidence sufficiency
  -> retrieve again if needed
  -> generate cited answer
  -> verify claims
  -> compute confidence
  -> answer, ask clarification, abstain, or escalate
```

Master:

- multi-hop retrieval
- query planning
- iterative retrieval
- tool-augmented retrieval
- source authority ranking
- evidence sufficiency scoring
- claim-level verification
- answer abstention
- human escalation
- memory-aware retrieval
- Graph RAG
- SQL + vector hybrid systems
- source freshness handling

Build:

- Agentic RAG assistant for policy Q&A
- iterative retrieval
- SQL tool
- API tool
- citation verifier
- confidence score
- abstention logic
- human escalation workflow

Milestone:

> Your system plans, retrieves, verifies, cites, and knows when not to answer.

---

## Phase 4: Agent Fundamentals

An AI agent is not just an LLM. A production agent has:

- goal
- instructions
- tools
- state
- memory
- planning policy
- execution loop
- observation handling
- guardrails
- evaluation
- monitoring

Basic agent loop:

```text
Observe -> Plan -> Act -> Observe -> Continue or Stop
```

Types of agents:

| Agent Type | Use Case |
|---|---|
| simple tool-calling agent | chooses one or more tools |
| workflow agent | follows a controlled graph |
| planner-executor agent | plans steps and executes them |
| ReAct agent | reason-act-observe loop |
| reflection agent | critiques and improves output |
| router agent | sends task to specialist/tool |
| supervisor agent | manages sub-agents |
| multi-agent system | specialized agents collaborate |
| autonomous agent | long-running goal-driven work |
| human-in-loop agent | asks approval for risky steps |
| code-execution agent | runs code in sandbox |
| research agent | searches, summarizes, verifies |
| transactional agent | takes business actions |
| voice agent | real-time speech workflows |
| multimodal agent | handles documents, image, audio, video |

Pro rule:

> Use deterministic workflows where possible. Add autonomy only where flexibility is worth the risk.

---

## Phase 5: Agent Frameworks

Know multiple frameworks and their tradeoffs.

| Framework | Strength |
|---|---|
| LangChain | integrations, chains, quick prototypes |
| LangGraph | stateful, durable, graph-based agent orchestration |
| LlamaIndex | RAG, ingestion, data-aware agents |
| OpenAI Agents SDK | tools, handoffs, tracing, guardrails |
| Microsoft Agent Framework | enterprise Microsoft/Azure environments |
| AutoGen-style systems | multi-agent experimentation |
| CrewAI | role-based multi-agent prototypes |
| PydanticAI | typed Python agent apps |
| Haystack | search/RAG pipelines |
| DSPy | eval-driven prompt/program optimization |

Framework selection rule:

- Use LangGraph for state, loops, human approval, and durable workflows.
- Use LlamaIndex for RAG-heavy document/data workflows.
- Use OpenAI Agents SDK for compact tools/handoffs/tracing/guardrails.
- Use Microsoft Agent Framework for Microsoft/Azure enterprise ecosystems.
- Use no framework for simple deterministic flows.

Milestone:

> You can explain why you selected a framework and what tradeoffs it creates.

---

## Phase 6: MCP, A2A, Tool Registries, and Agent Registries

### MCP: Model Context Protocol

MCP standardizes how AI apps connect to tools, resources, and prompts.

Master:

- MCP host
- MCP client
- MCP server
- tools
- resources
- prompts
- transports
- authorization
- server trust
- MCP registry
- tool discovery
- tool permissions
- audit logs
- sandboxing
- supply-chain risk

Build MCP servers for:

- internal knowledge base
- SQL read-only queries
- ticket creation
- CRM lookup
- document retrieval
- safe code execution
- email draft creation
- policy search

### A2A: Agent-to-Agent Protocol

A2A standardizes communication between agents.

Master:

- Agent Card
- agent discovery
- remote agent capability
- task lifecycle
- authentication between agents
- delegated task policy
- human approval for delegated tasks
- task traceability
- agent registry
- cross-framework interoperability

### MCP vs A2A

| MCP | A2A |
|---|---|
| agent/app to tools and context | agent to agent |
| tools/resources/prompts | agents/tasks/messages |
| tool and data access problem | delegation and collaboration problem |
| MCP registry | agent registry |

Security principle:

> Do not trust tools, MCP servers, or remote agents by default. Use identity, scoped permissions, registry approval, policy checks, audit logs, sandboxing, and human approval for risky side effects.

---

## Phase 7: Knowledge Bases and Knowledge Architecture

A production knowledge base is not a folder of PDFs in a vector database.

It needs:

- source connectors
- ingestion pipeline
- parsing
- cleaning
- chunking
- metadata enrichment
- PII classification
- access control
- versioning
- freshness
- deletion propagation
- evaluation
- observability
- governance
- feedback loop

Knowledge architecture:

```text
Source systems
  -> connectors
  -> parser / OCR / table extraction
  -> cleaner / normalizer
  -> chunker
  -> metadata enricher
  -> PII / sensitivity classifier
  -> embedding service
  -> vector DB + keyword index + metadata DB
  -> retriever / reranker / ACL layer
  -> RAG or Agentic RAG application
  -> evaluation + observability + feedback
```

Learn semantic architecture:

- taxonomy
- ontology
- knowledge graph
- entity resolution
- canonical data model
- business glossary
- data catalog
- lineage
- temporal validity

Milestone:

> You understand that enterprise AI quality depends on governed knowledge, not just model power.

---

## Phase 8: Evaluation Mastery

Most AI systems fail because they are not evaluated correctly.

Evaluation layers:

| Layer | What to Evaluate |
|---|---|
| model eval | correctness, reasoning, formatting, refusal |
| prompt eval | instruction following, tone, schema adherence |
| retrieval eval | did we fetch the right docs? |
| RAG eval | groundedness, relevance, completeness |
| agent eval | tool choices, trajectory, task success |
| tool eval | arguments, side effects, API success |
| safety eval | jailbreak, PII leakage, unsafe action |
| business eval | ROI, task completion, CSAT |
| system eval | latency, uptime, throughput, cost |
| human eval | SME review, trust, escalation quality |

Golden dataset fields:

```json
{
  "id": "policy_qa_001",
  "query": "Can I claim hotel reimbursement for a delayed flight?",
  "expected_answer": "Yes, if conditions X and Y are met.",
  "acceptable_criteria": [
    "mentions delayed flight condition",
    "mentions reimbursement cap",
    "mentions receipt requirement"
  ],
  "required_sources": ["travel_policy_v4.pdf#section-7"],
  "forbidden_sources": ["travel_policy_v2.pdf"],
  "expected_tools": ["policy_search"],
  "risk_category": "finance_policy",
  "difficulty": "multi_hop",
  "tenant": "india",
  "language": "english",
  "must_refuse": false
}
```

RAG metrics:

- recall@k
- precision@k
- MRR
- nDCG
- context precision
- context recall
- faithfulness
- groundedness
- answer relevance
- answer correctness
- citation precision
- citation recall
- abstention accuracy

Agent metrics:

- task success rate
- tool selection accuracy
- tool argument accuracy
- trajectory correctness
- unnecessary tool-call rate
- loop rate
- recovery rate
- escalation precision
- side-effect safety
- cost per successful task
- latency per successful task

Milestone:

> You do not ship because the demo looks good. You ship because the system passes measurable quality, safety, latency, and cost gates.

---

## Phase 9: Confidence Scoring

Do not trust the model's self-reported confidence alone.

Create a composite confidence score:

```text
confidence =
  retrieval score
  + reranker score
  + source freshness
  + source authority
  + context coverage
  + groundedness score
  + citation support
  + answer consistency
  + tool success signal
  + risk classifier signal
  + historical performance for this intent
```

Use confidence for behavior:

| Confidence | Behavior |
|---|---|
| high | answer directly |
| medium | answer with caveat and citations |
| low | ask clarification |
| very low | abstain |
| high risk + not high confidence | human review |
| risky action | require approval |

Learn calibration:

- precision-recall curve
- ROC-AUC
- Brier score
- expected calibration error
- threshold tuning
- false positive / false negative tradeoffs

---

## Phase 10: Tuning and Optimization

Tune in the right order.

Do not fine-tune first.

Tuning layers:

| Layer | What to Tune |
|---|---|
| product | task definition, UX, risk boundaries |
| data | source quality, freshness, metadata |
| retrieval | chunking, embedding, top_k, reranker, hybrid weights |
| prompt | instructions, examples, schema, refusal behavior |
| agent | tools, max steps, graph transitions, memory, retries |
| model | model selection, fine-tuning, LoRA, SFT, DPO |
| platform | caching, routing, batching, latency, scale |

Use RAG when:

- knowledge changes often
- private data is needed
- citations are needed
- auditability is required

Use fine-tuning when:

- output style must be consistent
- extraction behavior must be stable
- smaller model must imitate larger model
- repeated task behavior matters

---

## Phase 11: Token Reduction and Cost Optimization

Token optimization improves cost and latency.

Techniques:

- compact prompts
- context budgeting
- retrieve fewer better chunks
- rerank many to few
- contextual compression
- summarize long history
- prompt caching
- semantic caching
- model routing
- output token limits
- batch embeddings
- reduce tool schema size
- use smaller models for simple tasks
- async long-running jobs

Track:

- cost per request
- cost per conversation
- cost per successful task
- cost per tenant
- token burn rate
- cache hit rate
- model cost
- retrieval cost
- eval cost
- human review cost

Architect principle:

> Optimize for cost per successful task, not only cost per request.

---

## Phase 12: Observability

A production agent without observability is a black box.

Trace:

- user input
- rewritten query
- retrieved chunks
- reranked chunks
- prompt/context sent to model
- model name/version
- token usage
- cost
- latency
- tool calls
- tool arguments
- tool outputs
- guardrail decisions
- final answer
- citations
- eval scores
- user feedback
- errors and retries

Dashboard metrics:

- p50/p95/p99 latency
- tokens per request
- cost per successful task
- retrieval recall estimate
- groundedness score
- tool error rate
- loop/timeout rate
- safety block rate
- escalation rate
- feedback score
- fallback rate
- cache hit rate
- per-tenant usage

Milestone:

> You can reconstruct why an agent produced a bad answer.

---

## Phase 13: Guardrails, Safety, and Security

Threats:

- direct prompt injection
- indirect prompt injection
- tool injection
- RAG poisoning
- data exfiltration
- over-permissioned tools
- system prompt leakage
- vector DB poisoning
- unauthorized retrieval
- SSRF/tool abuse
- PII leakage
- jailbreaks
- excessive agency
- MCP supply-chain risk
- A2A remote-agent risk

Guardrail layers:

| Layer | Guardrail |
|---|---|
| input | moderation, jailbreak detection, intent classification |
| retrieval | ACL filters, source trust, injection scanning |
| prompt | context separation, source labeling, instruction hierarchy |
| tool | schema validation, allowlists, least privilege |
| action | human approval for risky operations |
| output | PII redaction, groundedness, policy checks |
| runtime | rate limits, anomaly detection, audit logs |
| platform | AI gateway, secrets isolation, egress controls |
| governance | red-team evals, compliance review, incident response |

Security principle:

> Treat user input, retrieved documents, tool outputs, MCP servers, and remote agents as untrusted unless explicitly verified.

---

## Phase 14: Authentication and Authorization

Authentication:

- OAuth2
- OIDC
- SSO
- JWT
- mTLS
- API keys
- service accounts
- short-lived tokens
- token exchange
- on-behalf-of flow

Authorization:

- RBAC
- ABAC
- ReBAC
- row-level security
- document-level permissions
- tenant isolation
- scoped tool permissions
- policy engines
- approval workflows

Correct pattern:

```text
User logs in
  -> identity and scopes propagated
  -> retriever filters documents by permissions
  -> tools execute with least privilege
  -> actions audited as user + agent
```

Wrong pattern:

```text
Agent uses one super-admin credential for all retrieval and actions.
```

---

## Phase 15: AI Gateway and API Gateway

AI gateway responsibilities:

- model routing
- provider abstraction
- fallback
- retry
- rate limit
- token budget
- cost tracking
- key management
- prompt cache
- semantic cache
- logging
- guardrail hooks
- tenant usage tracking
- policy enforcement

Architecture:

```text
Client apps
  -> API Gateway
  -> Auth + tenant policy
  -> AI Gateway
  -> prompt/security filters
  -> model router
  -> provider A / provider B / self-hosted model
  -> response guardrails
  -> logs/traces/eval sampling
```

---

## Phase 16: Production Deployment

Deployment options:

| Option | Best For |
|---|---|
| serverless | low traffic, simple APIs |
| Kubernetes | enterprise control, multi-service systems |
| managed LLM APIs | fastest start and reliability |
| self-hosted vLLM | control and cost optimization at scale |
| Ray Serve | Python-native scalable serving |
| KServe | Kubernetes-native inference |
| Triton | optimized multi-framework serving |
| hybrid | managed frontier model + self-hosted small models |

Production design includes:

- API gateway
- auth service
- AI gateway
- agent orchestrator
- retrieval service
- vector DB
- metadata DB
- tool service
- MCP servers
- A2A agents
- model providers
- guardrail service
- eval service
- observability pipeline
- feedback system
- human review queue

---

## Phase 17: Scaling to Millions of Users

Every request may involve:

- multiple LLM calls
- retrieval
- reranking
- tool calls
- safety checks
- traces
- eval sampling
- memory updates

Capacity formula:

```text
daily users
x requests per user
x LLM calls per request
x average input tokens
x average output tokens
x retrieval calls
x tool calls
x eval sampling rate
```

Scaling checklist:

- rate limit by user and tenant
- set p95/p99 SLOs
- isolate short chat from long-running agent jobs
- use queues for long tasks
- implement backpressure
- prompt cache
- semantic cache
- retrieval cache
- model routing
- batch embeddings
- shard vector DB
- replicate hot indexes
- incremental ingestion
- separate risky tools
- provider fallback
- model fallback
- degraded mode
- per-tenant dashboards
- cost budgets
- tenant isolation
- canary and rollback
- load test full path

---

## Phase 18: Automated Evaluation Pipeline

```text
Developer changes prompt/tool/retriever/model
  -> unit tests
  -> golden dataset eval
  -> retrieval eval
  -> RAG eval
  -> agent trajectory eval
  -> safety eval
  -> cost/latency eval
  -> regression comparison
  -> fail build if score drops
  -> canary deploy
  -> monitor online metrics
  -> promote or rollback
```

Minimum gates:

| Gate | Example Target |
|---|---|
| retrieval recall@5 | >= 90% |
| groundedness | >= 95% for high-risk domains |
| citation correctness | >= 90% |
| tool argument accuracy | >= 95% |
| schema validity | >= 99% |
| unsafe action rate | zero critical failures |
| p95 latency | under SLO |
| cost per task | under budget |
| regression | no significant drop |

---

## Phase 19: Smart Autonomous Agents

Capabilities:

- goal decomposition
- planning
- tool use
- memory
- reflection
- self-correction
- delegation
- human approval
- state persistence
- auditability
- sandboxing

Autonomy levels:

| Level | Description |
|---|---|
| L0 | LLM answers only |
| L1 | LLM calls read-only tools |
| L2 | write tools with user confirmation |
| L3 | bounded workflows |
| L4 | long-running tasks with checkpoints |
| L5 | fully autonomous high-risk actions |

Enterprise principle:

> Most production enterprise agents should be L2-L4, not fully autonomous L5.

---

## Phase 20: Multi-Agent Systems

Patterns:

- supervisor-worker
- router-specialist
- planner-executor
- critic-refiner
- debate/judge
- blackboard
- market/auction
- human-agent team
- A2A remote-agent collaboration

Failure modes:

- agents talk too much
- cost explodes
- circular delegation
- unclear ownership
- conflicting instructions
- weak evals
- tool permissions too broad
- no termination condition

Rule:

> Use multi-agent systems only when one agent or deterministic workflow is not enough.

---

# 4. Enterprise Architect Add-On Roadmap

## 4.1 Enterprise AI Architecture Thinking

Design from four views:

| View | What to Cover |
|---|---|
| Business view | problem, ROI, users, risk, success metrics |
| Application view | agents, RAG, APIs, workflows, UX |
| Data view | sources, access control, freshness, lineage |
| Platform view | gateway, evals, observability, scaling, security |

Interview phrase:

> I separate business requirements, data requirements, model requirements, risk requirements, and operational requirements before choosing the architecture.

---

## 4.2 Governance and Responsible AI

Master:

- NIST AI RMF
- ISO/IEC 42001
- EU AI Act awareness
- OWASP Top 10 for LLM Applications
- model cards
- system cards
- data cards
- AI risk register
- human oversight process
- incident reporting
- auditability
- data retention
- right to deletion
- vendor risk management

Questions you must answer:

- How do you classify AI risk?
- What human oversight is needed?
- What logs are retained?
- How do you audit a wrong answer?
- How do you prove the system was tested?
- What if the model provider changes behavior?
- How do you handle data residency?
- How do you handle right-to-delete requests?

---

## 4.3 AI Security and Red Teaming Depth

Go beyond basic guardrails.

Master:

- prompt injection
- indirect prompt injection
- tool injection
- RAG poisoning
- MCP server risk
- A2A agent trust
- data exfiltration
- over-permissioned tools
- secrets leakage
- cross-tenant leakage
- jailbreak resilience
- supply-chain risk

Security architecture:

```text
Input security
  -> prompt-injection classifier
  -> context isolation
  -> permission-filtered retrieval
  -> tool allowlist
  -> runtime policy engine
  -> human approval for high-risk actions
  -> output validation
  -> audit log
```

Interview answer:

> I secure AI agents at multiple layers: identity, retrieval permissions, tool permissions, prompt-injection defense, sandboxing, action approval, output filtering, audit logging, and continuous red-team evaluation.

---

## 4.4 Protocol Security: MCP and A2A

MCP architect topics:

- host/client/server model
- tools/resources/prompts
- server trust levels
- auth and authorization
- user-scoped access
- registry approval
- tool risk tiers
- audit logging
- sandboxing
- supply-chain validation

A2A architect topics:

- Agent Cards
- agent identity
- task lifecycle
- task delegation
- authentication
- authorization
- capability discovery
- traceability
- cross-framework interoperability

Interview answer:

> I do not trust tools or agents by default. I require identity, scoped permissions, registry approval, runtime policy checks, audit logs, sandboxing, rate limits, and human approval for risky side effects.

---

## 4.5 AI Platform Engineering

Build a reusable internal AI platform.

Components:

| Component | Purpose |
|---|---|
| AI gateway | model routing, fallback, cost tracking |
| prompt registry | versioned prompts |
| model registry | approved models and risk tiers |
| embedding registry | approved embedding models |
| tool registry | approved tools |
| MCP registry | approved MCP servers |
| agent registry | available agents and capabilities |
| vector index registry | index owners, freshness, embedding version |
| eval registry | golden datasets and benchmarks |
| policy engine | auth, guardrails, risk policies |
| observability platform | traces, metrics, logs, cost |
| feedback system | user feedback and human review |
| experiment platform | A/B tests, canary, model comparison |

---

## 4.6 LLMOps and AgentOps

LLMOps lifecycle:

```text
Dataset creation
  -> prompt/model/retriever development
  -> offline eval
  -> safety eval
  -> regression test
  -> canary release
  -> online monitoring
  -> human feedback
  -> dataset update
  -> continuous improvement
```

AgentOps lifecycle:

```text
Agent design
  -> tool design
  -> permission design
  -> trajectory testing
  -> tool-call eval
  -> safety red-team
  -> deployment
  -> trace monitoring
  -> failure clustering
  -> policy/prompt/tool update
```

Must have:

- prompt versioning
- dataset versioning
- model versioning
- eval versioning
- tool versioning
- rollback strategy
- canary deployments
- online/offline eval comparison
- human review queue
- production feedback mining

---

## 4.7 Evaluation Science

Advanced eval topics:

- eval validity
- eval reliability
- inter-rater agreement
- judge calibration
- statistical significance
- confidence intervals
- slice-based evaluation
- counterfactual evals
- adversarial evals
- longitudinal evals
- production shadow evals
- A/B testing
- canary evals

Senior phrase:

> I do not ship an agent because it looks good. I ship it when it passes golden-set regression, safety tests, retrieval metrics, trajectory checks, cost thresholds, and online monitoring gates.

---

## 4.8 AI SRE

AI SLOs:

| SLO | Example |
|---|---|
| availability | 99.9% successful responses |
| latency | p95 under target per workflow |
| cost | below budget per successful task |
| groundedness | >= target for high-risk answers |
| retrieval recall | >= target recall@k |
| tool success | >= target for tools |
| safety | zero critical unsafe actions |
| escalation quality | high-risk cases escalated correctly |

AI incident types:

- model provider outage
- vector DB outage
- bad prompt deployment
- retrieval index corruption
- embedding version mismatch
- tool API permission bug
- cost spike
- latency spike
- prompt-injection incident
- data leakage
- runaway agent loop

Runbooks:

- disable agent tools
- switch model provider
- rollback prompt
- rollback retriever
- disable MCP server
- block tenant/user
- lower max steps
- force human approval
- pause write actions
- purge poisoned documents
- re-index knowledge base

---

## 4.9 Distributed Inference and GPU Economics

Learn:

- KV cache
- PagedAttention
- continuous batching
- prefix caching
- speculative decoding
- quantization
- tensor parallelism
- pipeline parallelism
- LoRA adapter serving
- GPU utilization
- throughput vs latency
- cold starts
- autoscaling by tokens/sec
- multi-model serving
- fallback serving

Interview answer:

> I reduce inference cost using routing, caching, batching, smaller models, quantization, context reduction, prompt compression, retrieval optimization, max-token controls, async jobs, and canary-based model selection.

---

## 4.10 Memory Architecture for Agents

Memory types:

| Memory Type | Meaning |
|---|---|
| working memory | current task state |
| episodic memory | past events and interactions |
| semantic memory | durable facts |
| procedural memory | learned workflows/preferences |
| tool memory | past tool results |
| project memory | workspace context |
| organization memory | governed enterprise knowledge |
| short-term memory | recent context |
| long-term memory | persisted knowledge |

Memory risks:

- stale memory
- wrong memory
- privacy leakage
- cross-user leakage
- over-personalization
- sensitive data retention
- memory poisoning
- failure to delete memory

Memory design:

```text
Memory write policy
  -> memory classifier
  -> PII/sensitivity check
  -> user consent / tenant policy
  -> memory store
  -> expiration policy
  -> retrieval policy
  -> audit and deletion
```

Senior answer:

> Memory must be intentional, scoped, permissioned, auditable, erasable, and evaluated. I do not let the model freely write arbitrary long-term memory.

---

## 4.11 Data Engineering for AI Knowledge Systems

Learn:

- CDC
- incremental indexing
- document deletion propagation
- schema evolution
- data contracts
- data quality checks
- duplicate detection
- source freshness SLAs
- embedding regeneration strategy
- index migration
- metadata backfill
- multi-region replication
- PII classification
- encryption
- lineage tracking
- access-control sync

Interview answer:

> I keep RAG current using source connectors, incremental sync, change detection, document versioning, deletion propagation, metadata validation, embedding version tracking, freshness monitoring, and retrieval regression tests after every index update.

---

## 4.12 Agent Control Patterns

Control patterns:

| Pattern | Use When |
|---|---|
| deterministic workflow | compliance, finance, healthcare |
| LLM router | choose intent/tool/path |
| bounded agent loop | flexible but controlled tasks |
| state machine | auditable execution |
| human approval checkpoint | high-risk actions |
| plan-then-execute | complex multi-step tasks |
| supervisor-worker | multiple specialists |
| critic-verifier | quality control |
| fallback chain | resilience |
| circuit breaker | stop unsafe/expensive loops |

Senior phrase:

> In production, I prefer bounded, stateful, observable agent workflows over fully open-ended autonomous loops.

---

## 4.13 Financial Architecture and Unit Economics

Cost per request:

```text
LLM input tokens
+ LLM output tokens
+ embedding cost
+ reranker cost
+ vector DB cost
+ tool/API cost
+ observability storage
+ human review cost
+ infrastructure cost
```

Metrics:

- cost per request
- cost per conversation
- cost per successful task
- cost per tenant
- cost per workflow
- token burn rate
- cache hit rate
- eval cost
- human-review cost
- GPU utilization
- provider rate-limit headroom

Senior answer:

> To scale to one million users, I first estimate request volume, model calls per task, tokens per request, vector QPS, tool calls, cache hit rate, p95 latency, provider limits, GPU capacity, and monthly cost. Then I design routing, caching, queueing, autoscaling, fallbacks, and budget enforcement.

---

## 4.14 Multimodal and Document Intelligence

Learn:

- scanned PDF understanding
- OCR
- table extraction
- form extraction
- invoice processing
- chart understanding
- image-based search
- audio transcription
- meeting summarization
- video understanding
- multimodal RAG
- vision-language models
- layout-aware chunking
- coordinate-level citations

---

## 4.15 Synthetic Data and Dataset Generation

Use synthetic data for:

- Q&A generation
- paraphrases
- adversarial prompts
- hard negatives
- multi-hop questions
- edge cases
- classifier training
- retrieval benchmark expansion

Rule:

> Synthetic data is useful, but golden datasets must include real-world production failures and human-validated examples.

---

## 4.16 Architecture Documentation Skills

Must-have documents:

- architecture diagram
- sequence diagram
- data flow diagram
- threat model
- ADRs
- eval report
- runbook
- SLO document
- risk register
- cost model
- model card
- agent card
- tool contract
- RAG data sheet

ADR example:

```text
Decision: Use hybrid search + reranking for policy RAG.

Context:
Pure vector search missed exact policy codes and dates.

Options:
1. Dense vector only
2. BM25 only
3. Hybrid retrieval with reranking

Decision:
Use hybrid retrieval with metadata filters and reranking.

Consequences:
Higher latency and cost, but better recall and citation quality.
```

---

# 5. Vector Databases and Embedding Models

## Vector Database Categories

| Category | Examples | Best For |
|---|---|---|
| managed vector DB | Pinecone | fast managed production |
| open-source vector DB | Qdrant, Weaviate, Milvus | control and self-hosting |
| relational vector search | pgvector, AlloyDB | existing relational apps |
| search engine with vectors | Elasticsearch, OpenSearch, Azure AI Search | hybrid enterprise search |
| local/embedded vector stores | FAISS, Chroma, LanceDB | prototypes and local apps |
| lakehouse vector layer | LanceDB-style patterns | large offline corpora |

## Selection Criteria

- latency
- recall
- filtering performance
- hybrid search
- metadata scale
- indexing algorithm
- multi-tenancy
- update/delete speed
- backup/restore
- compliance
- cloud availability
- cost
- operational complexity

## Index Concepts

- HNSW
- IVFFlat
- PQ/product quantization
- scalar quantization
- vector dimensions
- cosine similarity
- dot product
- L2 distance
- recall vs latency
- sharding
- replication
- ef_search
- ef_construction
- probes

## Embedding Model Types

| Type | Use Case |
|---|---|
| general text embeddings | semantic search |
| multilingual embeddings | cross-language search |
| code embeddings | code search |
| domain embeddings | legal, medical, finance |
| multimodal embeddings | text and image retrieval |
| sparse embeddings | hybrid lexical/semantic retrieval |
| late-interaction embeddings | high-recall search |
| small embeddings | fast and cheap |
| large embeddings | higher quality and cost |

## Choosing Embeddings

Evaluate on your own data:

1. Create 200-1000 real queries.
2. Label relevant documents.
3. Test multiple embedding models.
4. Measure recall@k, MRR, nDCG.
5. Test multilingual and domain-specific queries.
6. Test metadata filtering.
7. Test latency and cost.
8. Test adversarial queries.

---

# 6. Production Checklists

## Production Readiness Checklist

- [ ] use case defined
- [ ] non-goals defined
- [ ] risk tier assigned
- [ ] success metrics defined
- [ ] SLOs defined
- [ ] data sources approved
- [ ] access control implemented
- [ ] golden dataset created
- [ ] retrieval eval implemented
- [ ] RAG eval implemented
- [ ] trajectory eval implemented
- [ ] safety eval implemented
- [ ] guardrails implemented
- [ ] tool permissions scoped
- [ ] human approval defined
- [ ] observability implemented
- [ ] cost tracking implemented
- [ ] AI gateway in place
- [ ] fallback defined
- [ ] canary plan ready
- [ ] rollback plan ready
- [ ] incident runbooks ready

## RAG Checklist

- [ ] clean ingestion
- [ ] table-aware parsing
- [ ] OCR where needed
- [ ] chunking benchmarked
- [ ] metadata schema defined
- [ ] ACL filters implemented
- [ ] embedding model benchmarked
- [ ] hybrid retrieval tested
- [ ] reranker tested
- [ ] citations verified
- [ ] stale docs removed
- [ ] deletion propagation works
- [ ] retrieval metrics monitored

## Agent Checklist

- [ ] clear goal
- [ ] clear boundaries
- [ ] minimal tool set
- [ ] strict schemas
- [ ] read/write tools separated
- [ ] max steps
- [ ] timeout
- [ ] token budget
- [ ] state persistence
- [ ] memory policy
- [ ] approval checkpoints
- [ ] trajectory evals
- [ ] full traces

## Security Checklist

- [ ] prompt injection tests
- [ ] indirect injection tests
- [ ] RAG poisoning tests
- [ ] tool injection tests
- [ ] PII leakage tests
- [ ] tenant isolation tests
- [ ] secrets not in context
- [ ] logs redacted
- [ ] MCP servers approved
- [ ] A2A agents authenticated
- [ ] audit logs retained

---

# 7. Capstone Portfolio Projects

## Project 1: Enterprise RAG Platform

Include:

- document ingestion
- chunking experiments
- vector DB
- keyword search
- hybrid retrieval
- reranking
- metadata filters
- citations
- ACLs
- eval dashboard

## Project 2: Agentic RAG Assistant

Include:

- query decomposition
- iterative retrieval
- SQL tool
- API tool
- claim verification
- confidence score
- abstention
- human escalation

## Project 3: Evaluation Platform

Include:

- golden dataset manager
- retrieval metrics
- RAG metrics
- trajectory metrics
- LLM-as-judge
- human review queue
- CI gates
- dashboard

## Project 4: MCP Tool Ecosystem

Include:

- MCP knowledge-base server
- MCP SQL read-only server
- MCP ticket creation server
- scoped tool permissions
- audit logs
- approval workflow

## Project 5: A2A Multi-Agent System

Include:

- Agent Card
- discovery
- supervisor agent
- specialist agent
- task lifecycle
- authentication
- traceability

## Project 6: AI Gateway

Include:

- unified model API
- model routing
- fallback
- token tracking
- budgets
- semantic cache
- guardrails
- logs

## Project 7: Million-User Simulation

Include:

- load testing
- vector DB sharding
- queue-based tasks
- autoscaling plan
- cost model
- SLO dashboard
- runbooks

---

# 8. Architecture Templates

## Tool Contract Template

```yaml
tool_name: create_support_ticket
owner: customer_support_platform
risk_level: medium
side_effects: creates_ticket
requires_human_approval: false
allowed_roles:
  - support_agent
  - customer_success_manager
input_schema:
  type: object
  required:
    - customer_id
    - issue_type
    - description
validation:
  - user_must_have_customer_access
  - description_must_not_contain_secrets
audit:
  log_request: true
  log_response: true
  redact_fields:
    - description
```

## Agent Card Template

```yaml
agent_name: finance_analysis_agent
version: 1.0.0
owner: finance_ai_platform
capabilities:
  - analyze_invoices
  - summarize_financial_variance
  - answer_policy_questions
authentication:
  type: oauth2
permissions:
  read_tools:
    - invoice_search
    - policy_search
  write_tools:
    - draft_approval_request
human_approval_required_for:
  - payment_release
  - vendor_master_update
risk_level: high
observability:
  traces_required: true
  audit_log_required: true
```

## Model Risk Sheet Template

```yaml
model_name: example-model
provider: example-provider
use_case: customer_support_agent
risk_level: medium
data_sent:
  - user_query
  - retrieved_context
data_stored_by_provider: false
evaluation_score:
  groundedness: 0.95
  task_success: 0.88
known_limitations:
  - may fail on ambiguous refund policies
fallback: fallback-model
monitoring:
  - latency
  - cost
  - safety
  - groundedness
owner: ai_platform_team
approval_date: 2026-05-21
review_cycle: quarterly
```

---

# 9. Top 100 Senior-Level Interview Questions with Answer Blueprints

## Strategy and Architecture

### 1. Design an end-to-end enterprise Agentic AI platform.

Strong answer should cover API gateway, auth, AI gateway, model routing, RAG, agent orchestration, MCP tools, A2A agents, guardrails, observability, evals, human approval, rollback, and cost controls.

Senior signal: mention trust boundaries, tenant isolation, eval gates, and incident response.

### 2. How do you decide between RAG, fine-tuning, long-context prompting, and tool calling?

Use RAG for private or changing knowledge. Use fine-tuning for consistent behavior or format. Use long context for bounded document sets when cost/latency allow. Use tools for live data and actions. Combine when needed.

Senior signal: choose based on freshness, auditability, cost, latency, privacy, and eval results.

### 3. Design a multi-tenant Agentic RAG platform.

Cover tenant identity, tenant namespaces or indexes, ACL sync, metadata filters, cache isolation, tenant budgets, tenant logs, cross-tenant leakage tests, encrypted storage, and per-tenant eval slices.

### 4. Difference between chatbot, tool-calling agent, workflow agent, and autonomous agent?

Chatbot generates responses. Tool-calling agent calls APIs. Workflow agent follows controlled graph/state. Autonomous agent pursues goals over many steps. Use the least autonomous design that meets requirements.

### 5. When would you choose deterministic workflow over autonomous agent?

Use deterministic workflow for compliance-heavy, finance, legal, healthcare, repeatable, auditable processes. Put LLMs inside workflow for routing, extraction, summarization, or drafting.

### 6. How do you design a risk-tiered AI system?

Classify use cases by impact. Apply stricter controls for higher-risk tasks. Require citations, eval thresholds, human approval, audit logs, and lower autonomy for high risk.

### 7. What documents should an AI architect produce before production?

Architecture diagram, sequence diagram, data flow diagram, threat model, ADRs, eval report, model card, data card, tool contracts, agent card, risk register, SLO document, and runbooks.

### 8. How would you build an internal AI platform for many teams?

AI gateway, prompt registry, model registry, embedding registry, tool registry, MCP registry, agent registry, eval registry, observability platform, policy engine, feedback platform, and experiment platform.

### 9. What makes an AI agent production-ready?

Clear goal, boundaries, scoped tools, auth, evals, guardrails, observability, cost controls, rollback, runbooks, human approval, and incident process.

### 10. How do you balance accuracy, latency, cost, safety, and UX?

Define metrics first. Route simple tasks to cheap models, use stronger models for hard/risky tasks, use caching, use async workflows, and measure cost per successful task.

## RAG and Retrieval

### 11. Explain a production-grade RAG pipeline.

Ingestion, parsing, cleaning, chunking, metadata enrichment, sensitivity classification, embedding, indexing, ACL sync, query rewriting, retrieval, reranking, context assembly, generation, citations, groundedness check, logging, and evaluation.

### 12. What is Agentic RAG?

The agent plans retrieval, decomposes queries, selects tools, retrieves iteratively, verifies evidence, checks sufficiency, generates answer, verifies claims, and abstains or escalates when needed.

### 13. How do you choose a chunking strategy?

Analyze document structure and query types. Test fixed, semantic, section, parent-child, hierarchical, and table-aware chunks. Measure recall@k, MRR, groundedness, citation precision, latency, and cost.

### 14. When should you use hybrid retrieval?

Use hybrid retrieval when semantic meaning and exact terms matter, such as policy IDs, product codes, dates, legal clauses, names, and error codes.

### 15. Why use reranking?

Retrieve many candidates cheaply, rerank with a stronger model, improve precision and citation quality, and tune based on eval impact.

### 16. Query rewriting vs query decomposition?

Rewriting improves search phrasing. Decomposition breaks multi-hop questions into subquestions. Both should be logged and evaluated.

### 17. What is Graph RAG?

Graph RAG combines vector search with entities and relationships. Useful for multi-hop connected facts across employees, vendors, accounts, contracts, policies, or dependencies.

### 18. How do you handle scanned PDFs, tables, and charts?

Use OCR, layout-aware parsing, table extraction, coordinate-aware citations, multimodal models, table-aware chunks, and separate eval sets for tables and scans.

### 19. How do you enforce access control in RAG?

Propagate user identity, apply ACL filters before retrieval, sync source permissions, test negative access cases, and never rely on prompt instruction alone.

### 20. How do you keep knowledge fresh?

Use connectors, incremental sync, CDC, versioning, deletion propagation, freshness metadata, reindexing jobs, embedding version tracking, and regression tests.

### 21. How do you evaluate retrieval quality?

Use labeled query-document pairs and measure recall@k, precision@k, MRR, nDCG, context precision, context recall, and slice performance.

### 22. Why can hallucination still happen with RAG?

Wrong docs, stale docs, incomplete context, unsupported inference, poor citations, or model ignoring evidence. Mitigate with evals, reranking, claim verification, and groundedness checks.

### 23. How do you design reliable citations?

Use claim-level citations, page/section references, chunk offsets, source metadata, and citation precision/recall evaluation. Block unsupported claims.

### 24. How do you create confidence scoring for RAG?

Combine retrieval score, reranker score, source freshness, source authority, context coverage, groundedness, citation support, answer consistency, and tool status.

### 25. How do you choose a vector database?

Evaluate latency, recall, filtering, hybrid search, update/delete speed, multi-tenancy, backup/restore, cost, compliance, and operational complexity.

## Embeddings and Vector Databases

### 26. How do you choose an embedding model?

Benchmark on your own data. Compare recall@k, MRR, nDCG, domain terminology, multilingual queries, latency, cost, and dimensionality.

### 27. Explain cosine similarity, dot product, and L2 distance.

Cosine measures angle, dot product measures magnitude and direction, and L2 measures Euclidean distance. Use the metric expected by the embedding model.

### 28. Explain HNSW, IVFFlat, and quantization.

HNSW is graph-based ANN with strong recall and memory overhead. IVFFlat partitions vectors and tunes probes/lists. Quantization reduces memory/cost but can reduce recall.

### 29. Compare pgvector, Pinecone, Weaviate, Qdrant, Milvus, Elasticsearch/OpenSearch, FAISS, Chroma, and LanceDB.

pgvector integrates with relational data. Pinecone is managed. Weaviate/Qdrant/Milvus offer open/self-host options. Elasticsearch/OpenSearch are strong for hybrid enterprise search. FAISS/Chroma are useful for local/prototypes. LanceDB fits embedded/lakehouse workflows.

### 30. When do you need multimodal embeddings?

Use them for image-text search, scanned docs, diagrams, slides, screenshots, product images, videos, and visual RAG.

### 31. How do you manage embedding versioning?

Track model name, version, dimension, preprocessing, chunking version, index version, creation date, and use blue-green reindexing.

### 32. How do you scale vector search?

Shard by tenant/domain, use replicas for reads, namespaces, hot/cold indexes, caching, async ingestion, and monitor recall and p95 latency.

### 33. How do you combine BM25 and vector search?

Run both retrievers, normalize scores, merge candidates, deduplicate, apply metadata filters, rerank, and tune weights on golden set.

### 34. What is semantic caching?

Reusing responses or intermediate results for semantically similar queries. It must be scoped by tenant, permissions, freshness, and sensitivity.

### 35. How do you defend against vector DB poisoning?

Use approved sources, ingestion permissions, scanning, lineage, moderation, source authority weighting, prompt-injection scanning, and audit trails.

## Agents and Tools

### 36. Design a tool-calling agent.

Use a tool registry, strict schemas, tool risk tiers, input validation, authorization, sandboxing, retries, timeouts, approval for side effects, tracing, and tool-call evals.

### 37. How do you design good tool schemas?

Use narrow tools, clear descriptions, strong types, required fields, enums, examples, idempotency keys, explicit side effects, and validation rules.

### 38. How should agent memory be designed?

Separate working, episodic, semantic, procedural, project, and organization memory. Apply retention, deletion, consent, permission, and audit policies.

### 39. Explain planner-executor architecture.

Planner decomposes goal, executor performs steps, verifier checks progress, and system replans on failure. Bound plan length and evaluate trajectories.

### 40. What are limitations of ReAct agents?

Looping, unnecessary tool calls, high cost, prompt sensitivity, weak auditability, and hard evaluation. Mitigate with state machines, max steps, stop conditions, and trajectory evals.

### 41. Why use LangGraph?

For stateful workflows, graph orchestration, controlled loops, human-in-the-loop, persistence, durable execution, and explicit transitions.

### 42. Compare LangChain, LangGraph, and LlamaIndex.

LangChain has integrations and chains. LangGraph provides stateful agent orchestration. LlamaIndex is strong for data/RAG workflows.

### 43. Where does OpenAI Agents SDK fit?

It is useful for code-first agents, tools, handoffs, tracing, and guardrails, especially in OpenAI-centric stacks.

### 44. When should you use multi-agent systems?

Use them for specialization, separated tools/data, independent roles, cross-domain collaboration, and A2A scenarios. Do not use them when one workflow is enough.

### 45. What can go wrong with supervisor-worker agents?

Poor delegation, duplicate work, circular loops, cost explosion, unclear ownership, conflicting outputs, and weak evals.

### 46. How do you prevent runaway loops?

Max steps, max tool calls, timeouts, token budgets, repeated-state detection, circuit breakers, and escalation triggers.

### 47. How do you design human-in-the-loop?

Classify risk, auto-approve low risk, require approval for high risk, show evidence, show proposed action, allow edit/reject, and capture review outcome for evals.

### 48. How do you persist long-running agent state?

Use task IDs, checkpoints, durable state, stored tool results, idempotency, retry policy, approval state, and recovery after failure.

### 49. How do you tune an agent?

Tune tool list, tool descriptions, system prompt, graph transitions, max steps, memory policy, retry logic, model choice, approval points, and trajectory evals.

### 50. How do you design safe autonomous agents?

Define autonomy level, allowed tools, risk boundaries, budgets, max duration, sandboxing, approvals, audit logs, and rollback/recovery.

## Evaluation

### 51. Design an evaluation strategy for Agentic RAG.

Include retrieval eval, generation eval, citation eval, groundedness, tool selection, tool arguments, trajectory correctness, safety, latency, cost, and online feedback.

### 52. How do you build a golden dataset?

Collect real queries, SME-authored questions, production failures, adversarial cases, no-answer cases, multilingual cases, and permission-sensitive cases. Label expected answer, required sources, tools, risk, and refusal behavior.

### 53. What RAG metrics do you track?

Recall@k, precision@k, MRR, nDCG, context precision, context recall, faithfulness, groundedness, answer relevance, answer correctness, citation precision, citation recall, and abstention accuracy.

### 54. How do you evaluate agent trajectories?

Check correct tool choice, correct arguments, correct order, minimal steps, error handling, no loops, permission compliance, and final task success.

### 55. How do you use LLM-as-judge safely?

Use fixed judge model, deterministic settings, clear rubric, examples, pairwise comparisons, human calibration, disagreement tracking, and never trust it blindly for high-risk decisions.

### 56. How do you compare two prompts/models/retrievers statistically?

Use same dataset, paired comparison, confidence intervals, slice analysis, practical significance, and regression thresholds.

### 57. How do evals fit into CI/CD?

Run unit tests, golden-set eval, safety eval, regression comparison, latency/cost checks, release gate, canary, and rollback trigger.

### 58. Offline vs online eval?

Offline eval is controlled and reproducible before release. Online eval captures real-world feedback, drift, latency, cost, and user behavior. Both are required.

### 59. How do production failures improve evals?

Sample logs, redact PII, cluster failures, get SME labels, add to golden set, and rerun regressions.

### 60. How do you evaluate safety?

Use jailbreak tests, prompt injection tests, data exfiltration tests, PII tests, unsafe tool-use tests, bias/toxicity tests, and policy-violation tests.

### 61. How do you calibrate confidence?

Compare confidence buckets to actual correctness. Use calibration curves, Brier score, expected calibration error, and risk-specific thresholds.

### 62. How do you ensure label quality?

Use labeling guidelines, examples, multiple reviewers, inter-rater agreement, SME adjudication, and label audits.

### 63. When is synthetic data useful?

For rare cases, paraphrases, adversarial prompts, multi-hop questions, hard negatives, and classifier training. Important golden examples need human validation.

### 64. What should an eval dashboard show?

Quality, retrieval, trajectory, safety, latency, cost, drift, failure clusters, judge disagreement, user feedback, and version comparison.

### 65. How do you make an agent improve automatically but safely?

Automate failure mining, generate candidate improvements, run evals, require approval gates, canary deploy, rollback, and avoid uncontrolled self-modification.

## Security, Auth, and Governance

### 66. How do you defend against prompt injection?

Use instruction hierarchy, input filtering, context separation, retrieved content labeling, tool allowlists, output validation, adversarial evals, and never rely only on system prompt.

### 67. What is indirect prompt injection?

Malicious instructions hidden in retrieved documents, webpages, emails, or tool outputs. Mitigate by treating external content as untrusted.

### 68. How do you secure tools?

Least privilege, scoped tokens, schema validation, allowlists, sandboxing, egress controls, approval for side effects, and audit logs.

### 69. How should auth work in AI systems?

Use SSO/OIDC, JWT validation, user-to-tenant mapping, permission propagation, scoped retrieval, scoped tools, and audit actions as user plus agent.

### 70. RBAC vs ABAC vs ReBAC?

RBAC uses roles. ABAC uses attributes. ReBAC uses relationships. Enterprise AI often needs all three.

### 71. How do you prevent cross-tenant leakage?

Tenant isolation in storage, vector namespaces, cache scoping, log scoping, metadata filters, memory isolation, and negative access tests.

### 72. How do you prevent PII leakage?

Data minimization, PII detection, redaction, encryption, access control, safe logging, output scanning, and retention policy.

### 73. How do you manage secrets?

Use secrets manager, no secrets in prompts, short-lived credentials, service identities, key rotation, and audit access.

### 74. How do you secure MCP servers?

Registry approval, identity, scoped auth, schema validation, sandboxing, audit logs, rate limits, and approval for side effects.

### 75. How do you secure A2A?

Trusted Agent Cards, authentication, authorization, scoped delegation, task audit logs, capability validation, and policy enforcement.

### 76. What does an AI gateway do for security?

Provider allowlists, rate limits, budget controls, prompt filters, response filters, logging policy, and centralized guardrails.

### 77. Design layered guardrails.

Input guardrails, retrieval guardrails, prompt/context isolation, tool guardrails, action approval, output guardrails, runtime monitoring, and audit logging.

### 78. How do you run red-team testing?

Threat model, adversarial datasets, prompt injection, tool abuse, exfiltration, jailbreaks, RAG poisoning, cross-tenant tests, and regression tests.

### 79. What is model risk management?

Model inventory, owner, use case, risk tier, data sent, eval results, limitations, fallback, monitoring, approval, and review cycle.

### 80. How do NIST, ISO 42001, EU AI Act, and OWASP affect architecture?

They influence risk management, governance processes, documentation, security testing, monitoring, auditability, human oversight, and incident response.

## Observability, Operations, and Scale

### 81. What should AI observability capture?

Prompts/context, model versions, tokens, cost, latency, retrieval queries, chunks, tool calls, guardrails, eval scores, final output, and user feedback.

### 82. How would you use OpenTelemetry for GenAI?

Create spans for model calls, retrieval, reranking, tool calls, guardrails, and agent steps. Track token usage, latency, errors, and avoid unsafe logging of sensitive data.

### 83. Define useful SLOs.

Availability, p95 latency, cost per successful task, tool success rate, retrieval recall, groundedness, citation correctness, safety violation rate, and escalation accuracy.

### 84. How do you handle AI incidents?

Triage, disable risky tools, rollback prompt/model/retriever, switch provider, force human approval, preserve audit logs, write postmortem, and add regression tests.

### 85. How do you reduce token usage and cost?

Context budgeting, smaller prompts, reranking, compression, model routing, prompt cache, semantic cache, output limits, batching, and budgets.

### 86. How do you design model routing and fallback?

Classify by difficulty/risk, use cheap model for simple tasks, strong model for hard/high-risk tasks, provider fallback, degraded mode, and canary tests.

### 87. What caching layers are useful?

Prompt cache, semantic response cache, retrieval cache, embedding cache, tool-result cache, and permission-aware cache keys.

### 88. How do you scale to millions of users?

Estimate traffic, model calls/request, tokens/request, vector QPS, and tool calls. Use gateways, queues, caching, routing, sharding, autoscaling, budgets, and multi-region design.

### 89. When would you self-host models?

For cost at scale, data control, private deployment, customization, latency, or open-model strategy. Requires GPU operations, serving stack, monitoring, patches, and model lifecycle.

### 90. How do you load test an AI agent platform?

Test the full path: auth, gateway, retrieval, reranking, LLM calls, tools, guardrails, tracing, queues, and storage. Measure p95/p99, cost, errors, limits, and quality degradation.

## Leadership and Case Studies

### 91. Design a customer-support AI agent.

Use help docs RAG, customer identity, entitlement checks, CRM/order tools, escalation, refund/cancel rules, audit logs, and CSAT/resolution evals.

### 92. Design a financial analyst agent.

Use governed financial data, SQL tools, document RAG, calculation tools, citations, freshness, approval for external reports, and numeric accuracy evals.

### 93. Design an AI coding assistant.

Use repo indexing, code embeddings, dependency graph, sandbox, secrets scanning, permissioned repo access, test generation, security checks, and PR workflow.

### 94. Design an HR policy Agentic RAG assistant.

Use policy docs, region metadata, employment-type filters, source citations, HR escalation, sensitive-topic handling, multilingual support, and strict access control.

### 95. Design secure MCP and A2A enterprise platform.

Use MCP registry, agent registry, tool registry, identity, authorization, approval workflow, trusted metadata, sandboxing, audit logs, and policy engine.

### 96. How would you migrate a prototype RAG chatbot to production?

Add auth, ACLs, better ingestion, metadata, evals, citations, guardrails, observability, cost controls, canary, and rollback.

### 97. How do you choose between AI frameworks?

Evaluate data complexity, statefulness, human-in-loop, durability, observability, language ecosystem, vendor constraints, team skill, and deployment needs.

### 98. What if a model provider changes behavior and quality drops?

Detect via eval drift, fallback model, rollback config, run regression, notify stakeholders, update golden set, and avoid single-provider dependency.

### 99. How do you measure ROI?

Measure task completion, handle-time reduction, deflection rate, revenue impact, error reduction, productivity, CSAT, compliance improvement, and cost per successful task.

### 100. What would your first 90 days look like as senior Agentic AI architect?

First 30 days: audit use cases, data, risks, stakeholders, and current systems.  
Next 30 days: define reference architecture, AI platform standards, eval strategy, security controls, and pilot.  
Final 30 days: ship measured pilot, implement golden set, observability, guardrails, and publish roadmap.

---

# 10. 12-Month Execution Plan

## Months 1-2: Core Engineering and LLM Basics

Focus:

- Python/FastAPI
- async APIs
- Docker
- Postgres/Redis
- OAuth/JWT
- LLM APIs
- prompt engineering
- structured outputs
- function calling
- token/cost basics

Build:

- model comparison harness
- authenticated chat API
- prompt regression tests

Output:

- GitHub repo with tests, tracing, Docker deployment

## Months 3-4: RAG Mastery

Focus:

- document ingestion
- chunking
- embeddings
- vector DBs
- hybrid retrieval
- reranking
- metadata filters
- citations
- RAG evals

Build:

- production RAG app over real documents
- vector DB benchmark
- embedding model benchmark
- golden retrieval dataset

Output:

- dashboard showing recall@k, groundedness, latency, and cost

## Months 5-6: Agentic RAG and Tool Use

Focus:

- tool calling
- planner-executor
- query decomposition
- iterative retrieval
- claim verification
- confidence scoring
- abstention
- human approval

Build:

- agentic RAG assistant using vector search + SQL + API tools
- bounded LangGraph workflow
- source-grounded answer verifier

Output:

- agent that answers, verifies, cites, and escalates

## Months 7-8: Evals, Observability, and Tuning

Focus:

- golden datasets
- LLM-as-judge
- RAG metrics
- trajectory metrics
- OpenTelemetry
- LangSmith/Phoenix-style tracing
- regression evals
- prompt/retrieval/model tuning

Build:

- automated eval CI pipeline
- production-style trace dashboard
- nightly regression job

Output:

- every change has score comparison

## Months 9-10: Security, Guardrails, MCP, and A2A

Focus:

- OWASP LLM risks
- prompt injection
- indirect prompt injection
- RBAC/ABAC/ReBAC
- MCP servers
- MCP registries
- A2A Agent Cards
- AI gateway
- tool sandboxing
- human approval

Build:

- MCP server for internal KB
- A2A-compatible agent card
- AI gateway with rate limits, logging, budgets
- prompt-injection test suite

Output:

- secure, auditable, tool-using agent platform

## Months 11-12: Production Scaling and Architecture

Focus:

- Kubernetes
- model serving
- vLLM/Ray Serve/KServe/Triton concepts
- multi-region design
- queues
- autoscaling
- latency/cost optimization
- SLOs
- incident response
- canary deployment
- load testing

Build:

- load-tested production architecture
- multi-tenant RAG/agent platform
- cost and token optimization dashboard
- disaster recovery plan

Output:

- architecture document suitable for enterprise review

---

# 11. Final Interview Preparation Strategy

Use this answer framework in every senior design interview:

```text
1. Clarify use case and business goal.
2. Define users and risk level.
3. Define success metrics and SLOs.
4. Design data and knowledge architecture.
5. Design retrieval and RAG.
6. Design agent and tool architecture.
7. Design auth and authorization.
8. Design guardrails and safety.
9. Design evaluation strategy.
10. Design observability.
11. Design scaling and cost strategy.
12. Explain tradeoffs, rollout, and future improvements.
```

World-class phrases:

- I would not ship based on a demo; I would require golden-set regression, safety evals, and online monitoring.
- I would propagate user identity into retrieval and tool execution.
- The agent should not use super-admin credentials.
- I would choose the least autonomous architecture that meets the requirement.
- Retrieved content and tool outputs must be treated as untrusted input.
- I would measure cost per successful task, not only token volume.
- I would separate model quality, retrieval quality, tool correctness, and system reliability.
- I would use canary deployment and rollback for prompts, retrievers, models, and tools.
- I would build platform controls once: AI gateway, registries, evals, observability, and policy engine.

Final goal:

> Do not position yourself as someone who knows RAG and LangChain. Position yourself as someone who can build an enterprise AI operating system.

---

# 12. References

Re-check these before interviews because the field changes quickly.

## Protocols and Agents

- Model Context Protocol: https://modelcontextprotocol.io/docs/getting-started/intro
- MCP Authorization: https://modelcontextprotocol.io/specification/draft/basic/authorization
- MCP Registry: https://registry.modelcontextprotocol.io/
- Agent2Agent Protocol: https://a2a-protocol.org/latest/
- OpenAI Agents SDK: https://developers.openai.com/api/docs/guides/agents
- OpenAI Agents SDK Tracing: https://openai.github.io/openai-agents-python/tracing/
- LangGraph: https://docs.langchain.com/oss/python/langgraph/overview
- LlamaIndex: https://developers.llamaindex.ai/

## Evaluation and Observability

- OpenAI Evals: https://developers.openai.com/api/docs/guides/evals
- Ragas Metrics: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/
- DeepEval: https://deepeval.com/docs/metrics-contextual-precision
- OpenTelemetry GenAI: https://opentelemetry.io/docs/specs/semconv/gen-ai/

## Embeddings and Serving

- MTEB Leaderboard: https://huggingface.co/spaces/mteb/leaderboard
- vLLM: https://docs.vllm.ai/
- Ray Serve LLM: https://docs.ray.io/en/latest/serve/llm/index.html
- KServe: https://kserve.github.io/website/

## Governance and Security

- NIST AI RMF: https://www.nist.gov/itl/ai-risk-management-framework
- ISO/IEC 42001: https://www.iso.org/standard/81230.html
- EU AI Act: https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai
- OWASP Top 10 for LLM Applications: https://owasp.org/www-project-top-10-for-large-language-model-applications/

---

# Closing Principle

The strongest AI architects do not merely connect an LLM to tools.

They design an operating system for intelligence:

- secure data access
- controlled autonomy
- measurable quality
- continuous evaluation
- observability
- governance
- cost control
- scalable production operations

Your goal is not:

> I know RAG and LangChain.

Your goal is:

> I can design, secure, evaluate, deploy, scale, govern, and continuously improve enterprise-grade Agentic AI platforms.
