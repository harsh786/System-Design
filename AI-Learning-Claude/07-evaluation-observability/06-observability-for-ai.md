# Observability for AI Systems

## Beyond Traditional APM

Traditional Application Performance Monitoring (APM) tracks: Is the server up? How fast are requests? Are there errors?

AI observability asks deeper questions:
- Is the AI giving **correct** answers?
- Are responses **faithful** to source data?
- Is quality **degrading** over time?
- Which **types** of queries fail most?
- How much are we **spending** per request?

**Analogy**: Traditional observability is like checking if a restaurant is open and serving food quickly. AI observability also checks if the food tastes good.

## The 3+1 Pillars of AI Observability

```mermaid
graph TD
    subgraph "Traditional 3 Pillars"
        L[Logs<br>What happened]
        M[Metrics<br>How much/fast]
        T[Traces<br>Request flow]
    end

    subgraph "AI Addition"
        E[Evals<br>How good]
    end

    L --> Full[Full AI<br>Observability]
    M --> Full
    T --> Full
    E --> Full

    style E fill:#e8f5e9
```

### Pillar 1: Logs (What Happened)

For AI systems, log:
- **Full prompts** (system + user messages)
- **Full responses** (complete LLM output)
- **Tool calls** (name, arguments, results)
- **Retrieved contexts** (what was fetched from vector DB)
- **Decisions** (routing, model selection, confidence)

⚠️ **PII warning**: Prompts often contain user data. Implement PII scrubbing or secure storage.

### Pillar 2: Metrics (How Much / How Fast)

| Metric | What It Tells You |
|---|---|
| P50/P95/P99 latency | User experience |
| Tokens per request (in/out) | Cost driver |
| Cost per request | Budget tracking |
| Error rate by type | Reliability |
| Retrieval hit rate | RAG health |
| Confidence score distribution | System certainty |
| Hallucination rate | Quality |
| User satisfaction (thumbs up/down) | Real quality |

### Pillar 3: Traces (Request Flow)

An AI request touches many components. A trace shows the full journey:

```
User Question (t=0ms)
├── Query Understanding (t=5ms)
│   └── LLM call: classify intent (t=200ms, 150 tokens)
├── Retrieval (t=210ms)
│   ├── Embed query (t=50ms)
│   └── Vector search (t=80ms, 5 results)
├── Generation (t=350ms)
│   └── LLM call: generate answer (t=1200ms, 800 tokens)
├── Confidence Scoring (t=1550ms)
│   └── Score: 0.87
└── Response returned (t=1600ms)
```

Each span captures: duration, tokens used, model, cost, and any errors.

### Pillar +1: Evals (How Good)

Continuous evaluation metrics tracked over time:
- Daily faithfulness scores on sample
- Weekly golden dataset evaluation
- Trending quality metrics with alerts

## OpenTelemetry for GenAI

OpenTelemetry is the standard for observability. The GenAI semantic conventions define how to instrument LLM calls:

```
Span: "chat openai.chat"
Attributes:
  gen_ai.system: "openai"
  gen_ai.request.model: "gpt-4"
  gen_ai.request.temperature: 0.7
  gen_ai.usage.input_tokens: 1500
  gen_ai.usage.output_tokens: 350
  gen_ai.response.finish_reason: "stop"
```

This creates vendor-neutral traces that work with any observability backend.

## What to Trace

Every step in your AI pipeline should be a span:

| Component | What to Capture |
|---|---|
| Query preprocessing | Original query, transformed query, detected intent |
| Embedding | Model used, dimension, latency |
| Vector search | Query, top-K results with scores, latency |
| Reranking | Input order, output order, scores |
| LLM call | Model, messages, temperature, tokens, latency, cost |
| Tool calls | Tool name, args, result, success/failure |
| Post-processing | Transformations applied, filters |
| Guardrails | Checks run, pass/fail, blocked content |

## Key Metrics Dashboard

### The Essential AI Dashboard

```
┌─────────────────────────────────────────────────────┐
│  AI System Health Dashboard                          │
├──────────────────┬──────────────────────────────────┤
│ Latency          │ Quality                          │
│ P50: 1.2s       │ Faithfulness: 0.94 ✓            │
│ P95: 3.1s       │ Relevance: 0.91 ✓               │
│ P99: 5.8s ⚠️    │ Hallucination: 3.2% ✓           │
├──────────────────┼──────────────────────────────────┤
│ Cost             │ Usage                            │
│ Avg/req: $0.03  │ Requests/hr: 1,240              │
│ Daily: $892     │ Errors: 0.3%                    │
│ Monthly: $24.1k │ Avg tokens: 1,850               │
├──────────────────┴──────────────────────────────────┤
│ Quality Trend (7 days)                              │
│ ████████████████████████████ 0.94                   │
│ ███████████████████████████░ 0.93 ← slight drop    │
│ ████████████████████████████ 0.94                   │
└─────────────────────────────────────────────────────┘
```

### Model Performance Comparison

Track across models to inform decisions:

| Model | Latency P95 | Quality | Cost/req | Best For |
|---|---|---|---|---|
| GPT-4o | 2.1s | 0.94 | $0.04 | Complex reasoning |
| GPT-4o-mini | 0.8s | 0.88 | $0.005 | Simple Q&A |
| Claude Sonnet | 1.9s | 0.93 | $0.03 | Long context |

## Observability Tools

| Tool | Strengths | Best For |
|---|---|---|
| **LangSmith** | Deep LangChain integration, playground | LangChain-based apps |
| **Phoenix (Arize)** | Open source, great traces, evals | Teams wanting OSS |
| **Langfuse** | Open source, simple, self-hostable | Privacy-conscious teams |
| **OpenLIT** | OpenTelemetry native, lightweight | OTel-based stacks |
| **Weights & Biases** | Experiment tracking, evals | Research-heavy teams |

## Alerting for AI Systems

### What to Alert On

| Alert | Condition | Severity |
|---|---|---|
| Quality drop | Faithfulness < 0.85 for 1 hour | Critical |
| Latency spike | P95 > 5s for 15 min | High |
| Cost spike | Daily cost > 2x average | High |
| Error rate | > 5% for 10 min | Critical |
| Hallucination spike | Rate > 10% for 1 hour | Critical |
| Low confidence | > 30% responses below 0.5 confidence | Medium |
| Model errors | Rate limit or API errors > 1% | High |

### Alert Fatigue Prevention

- Use anomaly detection, not fixed thresholds (seasonal patterns exist)
- Group related alerts (latency spike + cost spike = one root cause)
- Require 15-minute sustained issues before alerting (avoid flapping)

## Observability Architecture

```mermaid
graph TD
    App[AI Application] --> OTel[OpenTelemetry SDK]
    OTel --> Collector[OTel Collector]

    Collector --> Traces[Trace Backend<br>Jaeger/Tempo]
    Collector --> Metrics[Metrics Backend<br>Prometheus]
    Collector --> Logs[Log Backend<br>Loki/ELK]

    App --> EvalSDK[Eval SDK]
    EvalSDK --> EvalStore[Eval Results Store]

    Traces --> Dashboard[Observability Dashboard<br>Grafana]
    Metrics --> Dashboard
    Logs --> Dashboard
    EvalStore --> Dashboard

    Dashboard --> Alerts[Alert Manager]
    Alerts --> PagerDuty[PagerDuty/Slack]

    App --> Prompt[Prompt/Response Logger]
    Prompt --> AITool[AI Observability Tool<br>LangSmith/Phoenix/Langfuse]
    AITool --> Dashboard

    style App fill:#e1f5fe
    style Dashboard fill:#e8f5e9
    style Alerts fill:#ffebee
```

## Key Takeaways

1. **AI observability = traditional observability + quality** — you need evals alongside metrics
2. **Trace every LLM call** — tokens, cost, latency, model per span
3. **Monitor quality continuously** — not just at deploy time
4. **Alert on quality drops** — hallucination spikes are as critical as downtime
5. **Use OpenTelemetry** — vendor-neutral, standard, future-proof
6. **Cost is a first-class metric** — AI systems can silently become expensive
7. **Log prompts and responses** — essential for debugging, but handle PII carefully

---

## Staff-Level: Anti-Patterns, Trade-offs & Tooling Deep Dive

### Anti-Patterns in AI Observability

#### 1. Logging Only Inputs/Outputs (Missing Intermediate Steps)
You log the user question and the final answer. When something goes wrong, you can see WHAT failed but not WHY. Missing:
- Which documents were retrieved (and their scores)
- What the LLM's reasoning chain was
- Which tools were called (and what they returned)
- Where in the pipeline latency accumulated
- What confidence signals indicated before the response shipped

Without intermediate step logging, debugging becomes guesswork. "The answer was wrong" gives you nothing. "The answer was wrong because retrieval returned docs about the wrong product, and the reranker failed to filter them" gives you an actionable fix.

#### 2. No Trace IDs Across Components
A typical AI request touches: API gateway → query preprocessor → embedding service → vector DB → reranker → LLM → post-processor → guardrails → response. Without a single trace ID propagated through ALL these components:
- You can't correlate a bad answer to a specific retrieval failure
- You can't measure end-to-end latency breakdown
- When the vector DB is slow, you can't tell which user requests were affected
- Debugging requires manual timestamp correlation (hours of work per incident)

#### 3. Too Much Logging (Cost and Noise)
The opposite extreme: logging every token probability, every embedding vector, every intermediate computation. Problems:
- Storage costs exceed the AI compute costs themselves
- Signal-to-noise ratio drops (can't find real issues in the flood)
- PII exposure increases (more data = more risk)
- Query performance of observability tools degrades

**Right-sizing**: Log full details for a 5-10% sample. Log metadata (latency, token count, confidence, error codes) for 100%. Log full details for ALL errors and low-confidence responses.

#### 4. No Alerting on Quality Degradation
Teams monitor uptime and latency religiously but have zero alerts on:
- Faithfulness score trending downward
- Confidence distribution shifting (more low-confidence responses)
- Retrieval hit rate dropping
- User feedback (thumbs down) increasing

Quality can degrade 20% over a month with no alert firing. By the time users complain loudly enough to trigger investigation, trust is already damaged.

### Trade-offs in Observability Design

| Trade-off | Lightweight | Comprehensive | Guidance |
|---|---|---|---|
| Detail vs cost | Metadata only ($50/mo) | Full prompt/response logging ($2000/mo) | Full logging for 10% sample + all errors |
| Real-time vs batch | Batch daily analysis (cheap, delayed) | Real-time dashboards (expensive, instant) | Real-time for latency/errors, batch for quality |
| Self-hosted vs SaaS | Full control, maintenance burden | Easy setup, data leaves your infra | SaaS unless you have PII/compliance constraints |
| Custom vs standard | Fits your exact needs | Interoperable, community support | Use OTel standard, customize at dashboard layer |

### Tools Comparison: When to Use What

**LangSmith** (by LangChain):
- Best if: You're using LangChain/LangGraph
- Strengths: Deep framework integration, prompt playground, dataset management
- Weakness: Vendor lock-in to LangChain ecosystem, SaaS only
- Cost: Free tier (5k traces/mo), paid starts ~$400/mo

**Braintrust**:
- Best if: You want eval + observability unified
- Strengths: Eval-first design, good scoring UI, experiment tracking
- Weakness: Newer, smaller community
- Cost: Free tier available, usage-based pricing

**Phoenix (Arize)**:
- Best if: You want open-source, self-hosted
- Strengths: OSS, great trace visualization, OpenTelemetry native, supports evals
- Weakness: Self-hosting operational burden
- Cost: Free (self-hosted), Arize cloud for managed

**Langfuse**:
- Best if: Privacy matters (self-hostable), framework-agnostic
- Strengths: Simple API, self-hostable, good traces, prompt management
- Weakness: Less mature eval features
- Cost: Free (self-hosted), cloud starts ~$50/mo

**OpenTelemetry for AI (OpenLIT, Traceloop)**:
- Best if: You already have an OTel stack (Grafana, Datadog, etc.)
- Strengths: Vendor-neutral, integrates with existing infra, no new tools
- Weakness: Requires more setup, no AI-specific UI out of the box
- Cost: Depends on backend (Grafana Cloud, Datadog, etc.)

### The Observability Stack Decision Framework

```
Do you use LangChain? → LangSmith (path of least resistance)
                   ↓ No
Need self-hosting? → Langfuse or Phoenix
                   ↓ No
Already have OTel? → OpenLIT + your existing backend
                   ↓ No
Want eval + obs unified? → Braintrust
                   ↓ No
Start with → Langfuse Cloud (simple, cheap, framework-agnostic)
```

### Production Observability Checklist

Every AI system in production should have:
- [ ] Trace IDs propagated through all components
- [ ] Latency breakdown by pipeline stage
- [ ] Token usage and cost per request
- [ ] Quality score sampling (daily, 5-10% of traffic)
- [ ] Error categorization (retrieval miss, LLM error, guardrail block, timeout)
- [ ] Confidence score distribution monitoring
- [ ] User feedback correlation (thumbs up/down → quality metrics)
- [ ] Alerting on quality degradation (not just uptime)
- [ ] PII handling policy for logged prompts/responses
- [ ] Retention policy (how long to keep traces — 30 days typical)

---

*Next: [07-eval-in-ci-cd.md](./07-eval-in-ci-cd.md) — Integrating evaluation into your deployment pipeline*
