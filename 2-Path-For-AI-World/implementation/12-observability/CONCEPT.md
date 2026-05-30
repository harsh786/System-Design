# Module 12: AI Observability

## Why AI Without Observability Is a Black Box

Traditional software is deterministic: given the same input, you get the same output. AI systems are fundamentally different. An LLM can produce different outputs for identical inputs across calls. A RAG pipeline involves multiple stages—retrieval, reranking, prompt assembly, generation—where failure at any stage is invisible without instrumentation.

Without observability:
- You cannot explain WHY an agent gave a wrong answer
- You cannot identify if the problem was retrieval (wrong chunks), reranking (good chunks dropped), prompting (context too large, instruction buried), or generation (hallucination despite good context)
- You cannot measure cost drift until the bill arrives
- You cannot detect quality degradation until users complain
- You cannot reproduce failures (non-deterministic outputs)
- You cannot attribute cost to tenants, features, or workflows

**The core principle**: Every AI system must be fully reconstructable from its traces. Given a trace ID, you should be able to see exactly what the user asked, what was retrieved, what was sent to the model, what the model returned, and why any guardrail fired.

---

## What to Trace in AI Systems

### Layer 1: User Interaction
| Field | Why It Matters |
|-------|---------------|
| **User input (raw)** | The actual question/command before any processing |
| **Session ID** | Links multi-turn conversations |
| **Tenant ID** | Cost attribution, per-tenant quality tracking |
| **User feedback** | Ground truth signal for quality |
| **Final answer** | What the user actually received |
| **Citations** | Verifiability of the response |

### Layer 2: Query Processing
| Field | Why It Matters |
|-------|---------------|
| **Rewritten query** | Shows if query understanding failed |
| **Query classification** | Intent detection accuracy |
| **Query embedding** | Debugging retrieval misses |

### Layer 3: Retrieval & Context
| Field | Why It Matters |
|-------|---------------|
| **Retrieved chunks** | What the system found |
| **Chunk scores** | Relevance quality |
| **Reranked chunks** | What survived reranking |
| **Rerank scores** | Reranker effectiveness |
| **Prompt/context sent to model** | The actual input the model saw |
| **Context token count** | Context window utilization |

### Layer 4: Model Inference
| Field | Why It Matters |
|-------|---------------|
| **Model name/version** | Reproducibility, A/B testing |
| **Temperature/params** | Configuration debugging |
| **Input tokens** | Cost tracking |
| **Output tokens** | Cost tracking |
| **Total cost** | Budget enforcement |
| **Latency (TTFT + total)** | Performance monitoring |
| **Finish reason** | Detect truncations, content filter hits |

### Layer 5: Tool Use (Agentic)
| Field | Why It Matters |
|-------|---------------|
| **Tool calls** | What tools the agent chose |
| **Tool arguments** | Were arguments correct? |
| **Tool outputs** | Did the tool succeed? |
| **Tool latency** | Performance bottlenecks |
| **Tool errors** | Reliability tracking |
| **Loop count** | Detect infinite loops |

### Layer 6: Safety & Guardrails
| Field | Why It Matters |
|-------|---------------|
| **Guardrail decisions** | What was blocked and why |
| **Block reason** | Debugging false positives |
| **PII detected** | Compliance auditing |
| **Safety scores** | Threshold tuning |

### Layer 7: Quality & Evaluation
| Field | Why It Matters |
|-------|---------------|
| **Eval scores** | Automated quality assessment |
| **Groundedness score** | Hallucination detection |
| **Relevance score** | Answer quality |
| **Errors and retries** | Reliability |
| **Fallback triggered** | Graceful degradation tracking |

---

## Dashboard Metrics

### Latency Metrics
- **p50/p95/p99 end-to-end latency**: Overall system responsiveness
- **p50/p95/p99 per component**: Retrieval, rerank, model, tool execution
- **Time to first token (TTFT)**: Streaming responsiveness
- **Queue wait time**: Capacity planning

### Cost Metrics
- **Tokens per request** (input/output, per model)
- **Cost per task/workflow type**
- **Cost per tenant** (for multi-tenant systems)
- **Daily/weekly cost burn rate**
- **Cost per successful answer vs retry**

### Quality Metrics
- **Retrieval recall estimate**: Fraction of queries with relevant chunks in top-k
- **Groundedness score**: % of claims supported by retrieved context
- **Answer relevance score**: Does the answer address the question?
- **Citation accuracy**: Do citations match claims?
- **Feedback score**: User thumbs up/down ratio

### Reliability Metrics
- **Tool error rate**: By tool type
- **Loop/timeout rate**: Agent getting stuck
- **Safety block rate**: Guardrail triggers (too high = false positives, too low = risk)
- **Escalation rate**: Handoff to human
- **Fallback rate**: Simpler model/response used
- **Cache hit rate**: Efficiency of semantic cache
- **Retry rate**: Model/tool retries

### Capacity Metrics
- **Per-tenant usage**: Request volume, token consumption
- **Concurrent requests**: Load patterns
- **Rate limit proximity**: How close to provider limits

---

## OpenTelemetry for AI

### Core Concepts

**Spans**: A single unit of work. In AI systems:
- `ai.query.process` — query rewriting
- `ai.retrieval` — vector search
- `ai.rerank` — chunk reranking
- `ai.llm.chat` — model inference
- `ai.tool.execute` — tool call
- `ai.guardrail.check` — safety check
- `ai.agent.step` — one reasoning cycle

**Traces**: A tree of spans representing one end-to-end request. An agent call might produce:
```
trace: user-request-abc123
├── span: query_processing (12ms)
├── span: retrieval (89ms)
│   ├── span: embedding (23ms)
│   └── span: vector_search (66ms)
├── span: reranking (34ms)
├── span: llm_call_1 (1200ms)
├── span: tool_execution (450ms)
│   └── span: api_call (430ms)
├── span: llm_call_2 (800ms)
├── span: guardrail_check (15ms)
└── span: response_format (5ms)
```

**Attributes**: Key-value metadata on spans. AI-specific:
```
gen_ai.system = "openai"
gen_ai.request.model = "gpt-4o"
gen_ai.request.temperature = 0.1
gen_ai.usage.input_tokens = 3200
gen_ai.usage.output_tokens = 450
gen_ai.usage.cost_usd = 0.042
gen_ai.response.finish_reason = "stop"
```

### Semantic Conventions for GenAI (OpenTelemetry)

The OpenTelemetry community has emerging semantic conventions:

```
# LLM Call Attributes
gen_ai.system                    # "openai", "anthropic", etc.
gen_ai.request.model             # Model identifier
gen_ai.request.max_tokens        # Max output tokens
gen_ai.request.temperature       # Sampling temperature
gen_ai.request.top_p             # Nucleus sampling
gen_ai.response.id               # Provider response ID
gen_ai.response.model            # Actual model used
gen_ai.response.finish_reasons   # Why generation stopped
gen_ai.usage.input_tokens        # Prompt tokens
gen_ai.usage.output_tokens       # Completion tokens

# RAG-specific (custom conventions)
ai.retrieval.query               # Search query
ai.retrieval.top_k               # Number of results requested
ai.retrieval.chunks_returned     # Actual results
ai.retrieval.max_score           # Best match score
ai.retrieval.min_score           # Worst match score

# Agent-specific (custom conventions)
ai.agent.step_number             # Current step in reasoning
ai.agent.tool_name               # Tool selected
ai.agent.reasoning               # Chain of thought (careful with PII)
```

---

## Tracing Architecture

### Distributed Tracing Across Agent Steps

```
User Request
    │
    ▼
[API Gateway] ─── creates root span, trace_id
    │
    ▼
[Orchestrator] ─── child span: orchestration
    │
    ├──▶ [Query Service] ─── child span: query_rewrite
    │         propagates trace context via headers
    │
    ├──▶ [Retrieval Service] ─── child span: retrieval
    │         propagates trace context
    │
    ├──▶ [LLM Service] ─── child span: llm_inference
    │         propagates trace context
    │
    ├──▶ [Tool Service] ─── child span: tool_execution
    │         propagates trace context
    │
    └──▶ [Guardrail Service] ─── child span: safety_check
              propagates trace context
```

Key implementation details:
1. **Context propagation**: Use W3C TraceContext headers (`traceparent`, `tracestate`)
2. **Async spans**: Tool calls may be async; use span links for fan-out
3. **Long-running agents**: Use span events for intermediate steps within a single span
4. **Multi-turn**: Link traces across turns using `session_id` attribute

---

## Observability vs Monitoring vs Logging

| Aspect | Logging | Monitoring | Observability |
|--------|---------|------------|---------------|
| **Purpose** | Record events | Track known metrics | Understand unknown unknowns |
| **Approach** | Write structured events | Define metrics + thresholds | Instrument everything, query ad-hoc |
| **Question** | "What happened?" | "Is it healthy?" | "Why did this specific request fail?" |
| **AI Example** | "Model returned 500" | "Error rate > 5%" | "This answer hallucinated because reranker dropped the relevant chunk at step 3" |
| **Cardinality** | High (every event) | Low (aggregated) | High (traces + attributes) |
| **Cost** | Storage-heavy | Cheap | Moderate (sampling helps) |

For AI systems, you need ALL THREE:
- **Logging**: Structured logs for audit trails, compliance
- **Monitoring**: Dashboards, alerts on known failure modes
- **Observability**: Distributed traces to debug novel failures

---

## AI-Specific Observability Challenges

### 1. Non-Deterministic Outputs
The same input can produce different outputs. You cannot rely on "expected output" testing alone. You need:
- Trace every response with full context
- Score outputs on quality dimensions
- Track output distribution over time

### 2. Multi-Step Agent Loops
Agents may take 2-20 steps. Each step depends on previous steps. Challenges:
- Trace depth varies per request
- A bad decision at step 2 cascades to step 10
- You need to identify the FIRST point of failure

### 3. Large Payloads
Full prompts can be 100K+ tokens. You cannot store everything in span attributes. Strategy:
- Store summaries in spans (token count, first/last 200 chars)
- Store full payloads in blob storage, link via span attribute
- Apply PII redaction before storage

### 4. Cost Attribution
A single user request may invoke multiple models, tools, and retries. You need:
- Hierarchical cost rollup (span → trace → session → tenant)
- Real-time cost tracking (not just monthly bills)

### 5. Quality Is Subjective
Unlike HTTP status codes, "good" AI output is nuanced. You need:
- Multiple quality dimensions (relevance, groundedness, safety, helpfulness)
- Automated eval scores as span attributes
- Human feedback collection and linkage to traces

### 6. Delayed Feedback
Users may not provide feedback immediately. You need:
- Ability to retroactively annotate traces
- Correlation of feedback with trace data days later

---

## Alerting Strategies for AI Systems

### Threshold-Based Alerts
| Metric | Warning | Critical |
|--------|---------|----------|
| p95 latency | > 5s | > 15s |
| Error rate | > 2% | > 10% |
| Cost per hour | > 1.5x baseline | > 3x baseline |
| Groundedness score (avg) | < 0.7 | < 0.5 |
| Tool error rate | > 5% | > 20% |
| Safety block rate | > 10% | > 25% |
| Loop/timeout rate | > 3% | > 10% |

### Anomaly-Based Alerts
- Sudden shift in token usage distribution
- Unexpected model version change
- Retrieval score distribution shift (index degradation)
- Cost spike per tenant

### Composite Alerts
- High latency + high retry rate = provider degradation
- Low groundedness + high retrieval score = generation hallucination
- Low groundedness + low retrieval score = retrieval failure
- High safety block rate + low user complaints = false positive guardrails

### Alert Response Playbooks
1. **Cost spike**: Check per-tenant usage, look for loops, verify caching
2. **Quality drop**: Check retrieval scores, verify index freshness, check model version
3. **Latency spike**: Check provider status, queue depth, concurrent requests
4. **Error spike**: Check tool availability, rate limits, auth tokens

---

## Milestone

> **"You can reconstruct why an agent produced a bad answer."**

Given a trace ID, you should be able to answer:
1. What did the user actually ask?
2. How was the query interpreted/rewritten?
3. What was retrieved? Were relevant documents in the index?
4. Did reranking drop relevant chunks?
5. What was the full prompt sent to the model?
6. What model/parameters were used?
7. What did the model output? Did it hallucinate?
8. Were any tools called? Did they succeed?
9. Did any guardrail fire? Was it correct?
10. What was the final answer delivered to the user?

If you can answer all 10 from your observability data, you have achieved AI observability.
