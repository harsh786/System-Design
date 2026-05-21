# Senior AI Architect Interview Bank

**Learning level:** Senior/principal interview readiness  
**Outcome:** You can answer senior-level system design, RAG, agent, security, evaluation, operations, and leadership questions with architecture-level tradeoffs.

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
