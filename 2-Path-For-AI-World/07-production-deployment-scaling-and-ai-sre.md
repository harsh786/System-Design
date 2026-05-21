# Production Scale Track: Deployment, Scaling, AI SRE, Inference, and Unit Economics

**Learning level:** Production to enterprise scale  
**Outcome:** You can deploy and operate AI systems at high traffic, with SLOs, incident response, inference economics, cost modeling, fallbacks, queues, and multi-region thinking.

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

Expanded capacity model:

```text
peak_requests_per_second
x agent_steps_per_request
x model_calls_per_step
x average_input_tokens
x average_output_tokens
+ retrieval_qps
+ reranker_qps
+ tool_qps
+ embedding_jobs_per_second
+ trace_write_qps
+ eval_sample_qps
= model, retrieval, tool, storage, observability, and review capacity
```

Million-user architecture patterns:

| Pattern | Why It Matters |
|---|---|
| request classes | separate chat, retrieval, tool action, eval, and long-running jobs |
| cell-based tenancy | isolate large tenants and reduce blast radius |
| queues and workers | absorb spikes and run long tasks asynchronously |
| backpressure | protect model providers, vector DBs, and tools |
| model routing | send simple tasks to cheap/fast models and hard tasks to stronger models |
| streaming responses | reduce perceived latency for interactive flows |
| cache hierarchy | prompt, semantic, retrieval, reranker, embedding, and tool-result caches |
| hot/cold indexes | keep frequently used knowledge fast and archival knowledge cheaper |
| read replicas | scale vector, metadata, and trace reads independently |
| budget enforcement | stop runaway tenants, prompts, agents, or eval sampling |
| degraded modes | answer with limited tools/models when dependencies fail |
| regional failover | survive provider, region, or data-plane incidents |

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

Scale testing must include:

- auth and tenant policy
- API gateway and AI gateway
- model provider rate limits
- vector retrieval and metadata filters
- hybrid merge and reranking
- tool latency and failure behavior
- streaming path
- queue depth and worker saturation
- trace/log write volume
- eval sampling overhead
- cost budget enforcement
- degraded mode and fallback behavior
- cross-tenant isolation under load

Architect rule:

> Scaling an agent is not only scaling model calls. You must scale state, retrieval, tools, queues, evals, observability, memory, approvals, caches, budgets, and incident controls.

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
