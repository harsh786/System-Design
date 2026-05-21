# Enterprise Architect Track: AI Platform, LLMOps, AgentOps, Memory, Data, and Documentation

**Learning level:** Enterprise architect  
**Outcome:** You can design reusable internal AI platforms and produce the architecture, data, memory, operations, and documentation artifacts expected of a senior/principal architect.

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
