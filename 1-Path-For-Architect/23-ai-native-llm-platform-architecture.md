# AI-Native, LLM, RAG, and Agent Platform Architecture

Architect interviews increasingly include AI-enabled systems even when the role is not titled "AI architect". You do not need to become a research scientist, but you must be able to design production AI systems with the same rigor as any other distributed system.

## Architect-Level Outcome

You should be able to design a secure, observable, cost-aware AI platform that supports RAG, agents, model routing, evaluation, governance, and human oversight.

| Area | Architect-Level Outcome |
| --- | --- |
| RAG | Design ingestion, chunking, embeddings, retrieval, reranking, grounding, citations, and freshness. |
| LLM gateway | Route requests across models, enforce policy, manage quotas, redact sensitive data, and track cost. |
| Vector search | Choose vector index strategy, metadata filtering, hybrid retrieval, recall/latency trade-offs, and reindexing. |
| Evaluation | Define golden datasets, offline metrics, online experiments, regression gates, and human review. |
| Agent systems | Bound tool permissions, manage state, prevent unsafe autonomy, and observe reasoning/tool traces. |
| AI security | Handle prompt injection, indirect prompt injection, data leakage, unsafe tool calls, model abuse, and output risks. |
| AI operations | Monitor quality, latency, cost, drift, token usage, retrieval health, and fallback behavior. |

## AI System Design Template

Use this answer flow in AI architecture interviews:

```text
Clarify use case -> Risk level -> Data sources -> Latency/cost target -> Model choice -> Prompt contract -> Retrieval design -> Tool design -> Evaluation -> Safety controls -> Observability -> Rollout -> Governance -> Failure modes
```

## Core AI Architecture Patterns

### Pattern 1: Basic LLM Gateway

```text
Client -> API Gateway -> Auth/Quota -> LLM Gateway -> Model Provider
                                  -> Policy Engine
                                  -> Audit Log
                                  -> Cost Meter
```

Use this when the product needs controlled access to one or more models.

Key design points:

- Centralize model access instead of letting every service call providers directly.
- Enforce authentication, authorization, tenant quota, rate limits, and data classification.
- Add prompt templates, model versioning, request/response logging, and redaction.
- Add model routing by cost, latency, quality, region, capability, and fallback.
- Track token usage, spend, cache hit ratio, latency, and error rate per tenant and feature.

### Pattern 2: Retrieval-Augmented Generation

```text
Source Systems -> Connectors -> Parser -> Chunker -> Embedding Worker -> Vector DB
                                                          |
User Query -> Query Rewrite -> Retriever -> Reranker -> Context Builder -> LLM -> Response + Citations
```

Use this when answers must be grounded in private, changing, or domain-specific knowledge.

Key design points:

- Ingestion must handle permissions, versioning, deletes, document freshness, retries, and poison documents.
- Chunking must preserve semantic boundaries such as headings, tables, code blocks, tickets, and policies.
- Retrieval usually needs hybrid search: lexical search plus vector search plus metadata filters.
- Reranking improves quality but adds latency and cost.
- The context builder must enforce token budgets, deduplicate chunks, preserve citations, and respect ACLs.
- The answer must expose uncertainty and cite sources when correctness matters.

### Pattern 3: Agentic Workflow

```text
User Goal -> Planner -> Policy Check -> Tool Router -> Tool Execution -> State Store
                         |                                 |
                         -> Human Approval <---------------+
                         -> Trace/Audit Log
```

Use this only when the system needs multi-step tool use or workflow execution.

Key design points:

- Scope tools narrowly. A tool should do one concrete action with typed input/output.
- Use least privilege. The model should never inherit broad user or service permissions by default.
- Add approval gates for irreversible, expensive, sensitive, or external actions.
- Store tool traces, intermediate state, and final decisions for audit and debugging.
- Add max step count, max budget, timeout, recursion guards, and circuit breakers.
- Keep deterministic workflow logic outside the model when possible.

## RAG Deep Dive

### Ingestion Pipeline

- Source discovery: Confluence, Jira, Git, SharePoint, S3, database tables, PDFs, emails, tickets, runbooks.
- Connector model: poll, webhook, CDC, scheduled export, event-driven sync.
- Parsing: HTML, Markdown, PDF, DOCX, CSV, code, images with OCR if required.
- Normalization: title, body, author, timestamps, source URL, document type, tenant, ACLs, classification.
- Chunking: fixed size, semantic chunking, heading-aware chunking, table-aware chunking, code-aware chunking.
- Embedding: batch jobs, streaming workers, backfill, retries, provider fallback.
- Indexing: vector index, keyword index, metadata index, source-of-truth pointer.
- Deletion: tombstone, hard delete, permission revocation, reindex queue.
- Freshness: SLA per source, lag metric, failed-source dashboard.

### Chunking Rules

| Content | Better Chunking Strategy | Risk |
| --- | --- | --- |
| Policies | Section-aware chunks with headings. | Losing policy scope or exception details. |
| Code | Function/class-level chunks plus repository metadata. | Missing call context. |
| Tables | Preserve headers and row groups. | Detached cells become meaningless. |
| Tickets | Summary, description, comments, resolution as separate fields. | Old comments pollute current answer. |
| Runbooks | Step groups with preconditions and rollback. | Unsafe partial instructions. |

### Retrieval Strategy

- Start with ACL filtering before retrieval when possible.
- Use hybrid retrieval for enterprise knowledge: BM25/keyword catches exact terms, vector catches semantic matches.
- Use metadata filters for tenant, product, region, environment, freshness, owner, and document class.
- Use reranking for top candidates when answer quality matters.
- Use query rewriting for ambiguous user questions.
- Use recency boosts for operational docs, incidents, APIs, and policies.
- Use citation-aware context packing so the final answer can be verified.

### RAG Quality Metrics

| Metric | Meaning |
| --- | --- |
| Retrieval recall | Did the retriever find the document/chunk containing the answer? |
| Context precision | How much retrieved context was actually relevant? |
| Faithfulness | Did the answer stay grounded in retrieved sources? |
| Citation accuracy | Do citations support the claim? |
| Answer correctness | Would a domain expert accept the answer? |
| Freshness lag | How stale is the indexed knowledge? |
| Permission leakage rate | Did retrieval expose unauthorized data? |

## Vector Database and Index Design

Must-know concepts:

- Embedding dimensionality and model compatibility.
- HNSW, IVF, flat search, quantization, and recall/latency trade-offs.
- Metadata filtering before vs after vector search.
- Hybrid search and reranking.
- Index rebuilds after embedding model changes.
- Multi-tenant isolation: namespace, collection, index, or separate deployment.
- Hot tenants and query skew.
- Backup/restore and reproducible reindexing from source data.
- Data deletion and right-to-be-forgotten handling.

Interview answer rule:

```text
Vector DB is not the source of truth. The source system plus ingestion log must allow rebuild, audit, and deletion.
```

## LLM Gateway Design

### Responsibilities

- Provider abstraction: OpenAI, Azure OpenAI, Anthropic, local models, specialized embedding/reranker providers.
- Model routing: capability, latency, cost, region, token window, safety requirement.
- Prompt registry: versioned templates, rollout, rollback, ownership.
- Policy enforcement: allowed models, blocked data classes, tenant restrictions.
- Cost control: quotas, budgets, token accounting, caching, request shaping.
- Reliability: timeouts, retries, fallback, circuit breaker, provider health checks.
- Observability: request ID, trace ID, model, prompt version, token count, latency, quality signal.
- Audit: who asked, what data class, which tools, which outputs, which approval.

### Model Routing Matrix

| Need | Routing Choice |
| --- | --- |
| Low-cost summarization | Smaller/cheaper model with strict output schema. |
| Complex reasoning | Stronger model with higher timeout and budget. |
| Sensitive data | Approved region/provider, redaction, strict logging policy. |
| High-throughput embeddings | Batch-capable embedding model with back-pressure. |
| Outage | Fallback model or graceful degraded response. |
| Regulated workflow | Human approval and immutable audit trail. |

## Prompt and Output Contracts

- Treat prompts as versioned production artifacts.
- Store prompt owner, purpose, model compatibility, input schema, output schema, examples, safety constraints.
- Use structured output where downstream systems consume model responses.
- Validate output before execution or persistence.
- Never directly execute model-generated code, SQL, shell, or policy without validation and approval.
- Separate system instructions, developer instructions, user input, retrieved context, and tool results.
- Add prompt regression tests before changing prompts in critical workflows.

## Agent Safety Architecture

### Safety Controls

| Risk | Control |
| --- | --- |
| Tool overreach | Tool allowlist, scoped credentials, per-tool policy. |
| Irreversible action | Human approval, dry run, confirmation, rollback plan. |
| Infinite loop | Step limit, timeout, budget limit, recursion detection. |
| Prompt injection | Context isolation, instruction hierarchy, retrieved-content labeling. |
| Data exfiltration | DLP, egress policy, output filtering, tenant boundary checks. |
| Unsafe automation | Sandboxed execution, read-only mode first, staged permissions. |
| Poor reasoning trace | Tool call log, state snapshots, replayable execution trace. |

### Human-in-the-Loop Gates

Require approval for:

- Sending external messages.
- Creating, deleting, or modifying production resources.
- Running destructive database or infrastructure commands.
- Spending above budget.
- Accessing restricted data.
- Changing permissions, secrets, or security controls.
- Acting on behalf of another user.

## AI Security Deep Dive

Use OWASP LLM security risks as a checklist. At architect depth, focus on threat paths and mitigations:

- Prompt injection: malicious user or document attempts to override instructions.
- Sensitive information disclosure: model reveals secrets, PII, internal data, or retrieved unauthorized context.
- Supply chain risk: unsafe models, plugins, datasets, dependencies, or prompt packages.
- Data and model poisoning: compromised source documents or training/evaluation data.
- Improper output handling: model output flows into SQL, HTML, shell, code, policies, or tickets without validation.
- Excessive agency: agent has too much permission, autonomy, budget, or tool reach.
- System prompt leakage: hidden policy or sensitive instructions appear in output.
- Model denial of service: huge prompts, expensive loops, unbounded tool calls, adversarial inputs.
- Overreliance: users trust model output without verification in high-stakes decisions.

Mitigation stack:

- Treat retrieved documents as untrusted input.
- Use least-privilege tools and scoped credentials.
- Validate all structured outputs against schema.
- Add content filters, DLP, and policy engine checks.
- Separate read, propose, and execute modes.
- Add approval gates and audit logs.
- Test with red-team prompts and poisoned documents.

## Evaluation and Release Gates

### Offline Evaluation

- Golden question-answer set.
- Retrieval-only eval: expected document in top K.
- Answer eval: correctness, faithfulness, citation support, completeness.
- Safety eval: prompt injection, PII leakage, toxic output, unsafe tool use.
- Regression eval per prompt/model/retriever change.
- Domain expert review for high-value workflows.

### Online Evaluation

- Thumbs up/down plus reason codes.
- Human escalation rate.
- Correction/edit distance.
- Search retry rate.
- Task completion rate.
- Latency and cost per successful answer.
- Complaint/incidence rate.
- A/B tests for prompt, retriever, reranker, and model changes.

### Release Gate

```text
No AI workflow is production-ready until quality, safety, latency, cost, and rollback are measured.
```

## AI Observability

Track these dimensions:

- Request volume by tenant, feature, model, prompt version.
- Latency: gateway, retrieval, reranking, model, tool execution, total.
- Token usage: input, output, retrieved context, tool results.
- Cost: per request, per tenant, per feature, per model.
- Quality: answer rating, eval score, citation accuracy, escalation.
- Safety: blocked prompts, injection attempts, DLP hits, policy denials.
- Retrieval: top-K hit rate, empty retrieval, stale documents, index lag.
- Agent: tool calls per task, approval rate, failure reason, loop prevention.

## Failure Modes

| Failure | Symptom | Mitigation |
| --- | --- | --- |
| Stale index | Answers cite old policies. | Source freshness SLA, reindex alert, answer timestamp. |
| Permission leak | User sees unauthorized document. | ACL filter, tenant isolation tests, audit replay. |
| Provider outage | High LLM gateway errors. | Circuit breaker, fallback model, degraded mode. |
| Cost spike | Token spend jumps after prompt change. | Budget alert, prompt diff review, max token limits. |
| Prompt injection | Model follows document instruction. | Context labeling, injection evals, output policy check. |
| Hallucination | Unsupported answer. | Citation requirement, abstain behavior, human escalation. |
| Tool misuse | Agent modifies wrong resource. | Scoped tool permissions, dry run, approval, rollback. |

## Capstone Build

Build an internal engineering assistant:

1. Ingest docs from Markdown, Git, Jira, and Confluence.
2. Preserve ACLs and source URLs.
3. Implement chunking, embeddings, vector search, lexical search, and reranking.
4. Add RAG answer generation with citations.
5. Add LLM gateway with model routing, cost tracking, and prompt versioning.
6. Add tool use for read-only repo search and ticket lookup.
7. Add human approval before write actions.
8. Add prompt-injection tests with malicious documents.
9. Add eval dataset and regression gate.
10. Add dashboards for latency, cost, retrieval quality, safety, and feedback.

## Interview Questions

1. Design an enterprise RAG system for 50,000 employees with document-level permissions.
2. How do you prevent prompt injection from retrieved documents?
3. How would you design an LLM gateway for multiple teams and providers?
4. How do you measure whether a RAG system is getting better?
5. Design an agent that can create Jira tickets and pull requests safely.
6. How do you handle embedding model migration without losing search quality?
7. How do you control AI cost in a multi-tenant SaaS product?
8. How do you design auditability for AI-generated decisions?
9. What fails when vector DB is treated as a source of truth?
10. How do you design fallback behavior when the model provider is down?

## Official Reference Anchors

- NIST AI Risk Management Framework: https://www.nist.gov/itl/ai-risk-management-framework
- NIST Generative AI Profile: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
- OWASP Top 10 for LLM Applications: https://owasp.org/www-project-top-10-for-large-language-model-applications/

