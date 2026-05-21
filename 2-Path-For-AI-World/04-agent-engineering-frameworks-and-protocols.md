# Advanced Track: Agent Engineering, Frameworks, MCP, A2A, and Multi-Agent Systems

**Learning level:** Advanced agent systems architect  
**Outcome:** You can choose the right agent pattern/framework, design controlled tool use, secure protocol boundaries, and avoid over-autonomous multi-agent designs.

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

## Training and Improving Agents

Do not confuse training a model with improving an agent. An agent is a system made of prompts, tools, memory, graph transitions, policies, models, retrieval, evals, and runtime controls.

| Improvement Lever | What Changes | Use When |
|---|---|---|
| prompt tuning | instructions, examples, response schema | behavior is inconsistent but model can already do the task |
| tool tuning | tool names, descriptions, schemas, examples | agent picks wrong tools or wrong arguments |
| graph tuning | routing, transitions, stop conditions, retries | workflow loops, skips approval, or follows weak paths |
| memory tuning | write policy, retrieval policy, expiration | agent forgets useful state or remembers unsafe data |
| retriever tuning | chunking, top_k, reranker, filters | agent lacks the right evidence |
| model routing | choose model by intent/risk/difficulty | cost is high or simple tasks use oversized models |
| fine-tuning | model weights or adapters | repeated behavior/style/schema is hard to force with prompting |
| distillation | small model learns from stronger model outputs | cost/latency must drop at high volume |
| human feedback loop | SME review becomes training/eval data | production failures reveal missing examples |
| policy tuning | risk thresholds, approval rules, tool permissions | agent is too permissive or too conservative |

Agent improvement loop:

```text
production trace
  -> failure clustering
  -> label root cause
  -> choose one change lever
  -> update prompt/tool/graph/retriever/model/policy
  -> run golden evals
  -> run trajectory and safety evals
  -> canary release
  -> monitor task success, cost, latency, and safety
```

Senior rule:

> Train the agent system before training the model. Most failures are caused by weak tools, weak retrieval, weak state design, weak evals, or weak policies, not by missing model fine-tuning.

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
