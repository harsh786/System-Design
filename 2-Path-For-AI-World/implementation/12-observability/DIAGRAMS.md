# Module 12: Observability Diagrams

## 1. Observability Architecture (Collection → Storage → Visualization)

```mermaid
graph TB
    subgraph "AI Application Layer"
        APP[AI Agent Service]
        SDK[OTel SDK + AI Instrumentation]
        APP --> SDK
    end

    subgraph "Collection Layer"
        OTEL_COL[OpenTelemetry Collector]
        PROM_EXP[Prometheus Exporter :9090]
        LOG_SHIP[Log Shipper Fluent Bit]
        SDK -->|OTLP gRPC| OTEL_COL
        SDK -->|metrics| PROM_EXP
        APP -->|structured logs| LOG_SHIP
    end

    subgraph "Processing Layer"
        TAIL_SAMP[Tail-Based Sampler]
        ENRICHER[Attribute Enricher]
        OTEL_COL --> TAIL_SAMP
        TAIL_SAMP --> ENRICHER
    end

    subgraph "Storage Layer"
        TEMPO[Grafana Tempo / Jaeger]
        PROM[Prometheus / Mimir]
        LOKI[Loki / Elasticsearch]
        BLOB[Blob Storage - Full Payloads]
        ENRICHER -->|traces| TEMPO
        PROM_EXP -->|scrape| PROM
        LOG_SHIP --> LOKI
        ENRICHER -->|large payloads| BLOB
    end

    subgraph "Visualization & Alerting"
        GRAFANA[Grafana Dashboards]
        ALERT[Alertmanager]
        NOTEBOOK[Jupyter / Debug UI]
        TEMPO --> GRAFANA
        PROM --> GRAFANA
        LOKI --> GRAFANA
        PROM --> ALERT
        TEMPO --> NOTEBOOK
    end

    ALERT -->|PagerDuty/Slack| ONCALL[On-Call Engineer]
```

## 2. Distributed Trace Through Agent System

```mermaid
sequenceDiagram
    participant U as User
    participant GW as API Gateway
    participant ORCH as Orchestrator
    participant QS as Query Service
    participant RS as Retrieval Service
    participant RR as Reranker
    participant LLM as LLM Service
    participant TOOL as Tool Service
    participant GR as Guardrail Service

    U->>GW: POST /chat (message)
    Note over GW: Create trace_id, root span

    GW->>ORCH: Forward (traceparent header)
    Note over ORCH: Child span: orchestration

    ORCH->>QS: Rewrite query (traceparent)
    Note over QS: Child span: query_rewrite
    QS-->>ORCH: Rewritten query

    ORCH->>RS: Search (traceparent)
    Note over RS: Child span: retrieval
    Note over RS: Attrs: query, top_k, scores
    RS-->>ORCH: Chunks + scores

    ORCH->>RR: Rerank chunks (traceparent)
    Note over RR: Child span: rerank
    RR-->>ORCH: Reranked top-3

    ORCH->>LLM: Generate (traceparent)
    Note over LLM: Child span: llm_call
    Note over LLM: Attrs: model, tokens, cost
    LLM-->>ORCH: Response + tool_call

    ORCH->>TOOL: Execute tool (traceparent)
    Note over TOOL: Child span: tool_exec
    Note over TOOL: Attrs: tool_name, args, result
    TOOL-->>ORCH: Tool result

    ORCH->>LLM: Generate final (traceparent)
    Note over LLM: Child span: llm_call_2
    LLM-->>ORCH: Final answer

    ORCH->>GR: Check output (traceparent)
    Note over GR: Child span: guardrail
    Note over GR: Attrs: decision, score
    GR-->>ORCH: Allow

    ORCH-->>GW: Response
    GW-->>U: Answer

    Note over GW: Close root span<br/>Record: total_cost, total_tokens, latency
```

## 3. Metrics Pipeline

```mermaid
graph LR
    subgraph "Instrumentation"
        H[Histograms<br/>latency, tokens, scores]
        C[Counters<br/>requests, errors, tokens]
        G[Gauges<br/>active requests, cost/hr]
    end

    subgraph "Collection"
        PE[Prometheus Exporter<br/>:9090/metrics]
        H --> PE
        C --> PE
        G --> PE
    end

    subgraph "Storage & Query"
        PS[Prometheus Server<br/>15s scrape interval]
        PE -->|scrape| PS
        PS --> RR[Recording Rules<br/>pre-compute percentiles]
    end

    subgraph "Consumption"
        DASH[Grafana Dashboards]
        ALERT[Alert Rules]
        API[Metrics API<br/>for custom UIs]
        PS --> DASH
        RR --> ALERT
        PS --> API
    end

    subgraph "Long-term"
        MIMIR[Mimir / Thanos<br/>long-term storage]
        PS -->|remote write| MIMIR
    end
```

## 4. Alert Flow

```mermaid
graph TB
    subgraph "Detection"
        PR[Prometheus Rules Engine]
        PR -->|evaluates every 30s| RULES
        RULES[Alert Rules<br/>- Latency > threshold<br/>- Error rate > 5%<br/>- Cost spike<br/>- Quality drop]
    end

    subgraph "Routing"
        AM[Alertmanager]
        RULES -->|firing| AM
        AM --> DEDUP[Deduplication]
        DEDUP --> GROUP[Grouping<br/>by service, severity]
        GROUP --> SILENCE[Silence Check]
        SILENCE --> INHIBIT[Inhibition Rules<br/>critical suppresses warning]
    end

    subgraph "Notification"
        INHIBIT --> ROUTE{Route by Severity}
        ROUTE -->|critical| PD[PagerDuty]
        ROUTE -->|warning| SLACK[Slack Channel]
        ROUTE -->|info| EMAIL[Email Digest]
    end

    subgraph "Response"
        PD --> ONCALL[On-Call Engineer]
        ONCALL --> RUNBOOK[Runbook]
        RUNBOOK --> TRACE[Find Trace ID]
        TRACE --> DEBUG[Trace Debugger]
        DEBUG --> FIX[Fix & Deploy]
    end
```

## 5. Dashboard Layout Design

```mermaid
graph TB
    subgraph "Row 1: Key Stats (stat panels)"
        S1[Request Rate<br/>req/s]
        S2[Error Rate<br/>%]
        S3[Hourly Cost<br/>$]
        S4[Avg Feedback<br/>score]
        S5[Cache Hit Rate<br/>%]
        S6[Active Requests]
    end

    subgraph "Row 2: Latency"
        L1[Request Latency p50/p95/p99<br/>time series]
        L2[Component Breakdown<br/>stacked bar: retrieval, rerank, LLM, tool]
    end

    subgraph "Row 3: Cost & Tokens"
        C1[Cost Over Time by Model<br/>time series]
        C2[Tokens Per Request<br/>histogram]
    end

    subgraph "Row 4: Quality"
        Q1[Quality Scores<br/>groundedness, relevance]
        Q2[Error Rate by Type<br/>model, tool, guardrail, timeout]
    end

    subgraph "Row 5: Tools & Safety"
        T1[Tool Calls & Errors<br/>by tool name]
        T2[Guardrail Decisions<br/>allow/block/warn]
    end

    subgraph "Row 6: Per-Tenant"
        P1[Cost by Tenant<br/>stacked area]
        P2[Request Rate by Tenant<br/>time series]
    end
```

## 6. Trace Debugging Workflow

```mermaid
flowchart TD
    START[User reports bad answer<br/>or alert fires] --> GET_ID[Get Trace ID<br/>from logs/session/alert]

    GET_ID --> RECONSTRUCT[Reconstruct Trace<br/>Full narrative view]

    RECONSTRUCT --> DECISIONS[Analyze Decision Points<br/>Retrieval, Rerank, LLM, Tool, Guardrail]

    DECISIONS --> CHECK{Any BAD<br/>decisions?}

    CHECK -->|Yes| ROOT[Root Cause Analysis]
    CHECK -->|No| COMPARE[Compare with Good Trace<br/>Same query, different outcome]

    ROOT --> IDENTIFY[Identify Failed Component]
    COMPARE --> DIFF[Show Differences<br/>Scores, tokens, steps]

    IDENTIFY --> CATEGORY{Failure Category}
    DIFF --> CATEGORY

    CATEGORY -->|Retrieval| FIX_RET[Check index freshness<br/>Review embeddings<br/>Fix query rewriting]
    CATEGORY -->|LLM| FIX_LLM[Check context size<br/>Review prompt template<br/>Verify model version]
    CATEGORY -->|Tool| FIX_TOOL[Check tool availability<br/>Validate inputs<br/>Add retries]
    CATEGORY -->|Guardrail| FIX_GUARD[Review thresholds<br/>Check false positive rate<br/>Update rules]

    FIX_RET --> VERIFY[Replay Trace<br/>Verify fix would help]
    FIX_LLM --> VERIFY
    FIX_TOOL --> VERIFY
    FIX_GUARD --> VERIFY

    VERIFY --> DEPLOY[Deploy Fix<br/>Monitor metrics]
```

## 7. AI Observability Stack

```mermaid
graph TB
    subgraph "Application"
        direction TB
        AI_APP[AI Agent Application]
        OTEL_SDK[OpenTelemetry SDK]
        AI_INST[AI Instrumentation Layer<br/>LLM spans, retrieval spans, tool spans]
        AI_APP --> OTEL_SDK
        OTEL_SDK --> AI_INST
    end

    subgraph "Signals"
        TRACES[Traces<br/>Distributed traces across<br/>all agent steps]
        METRICS[Metrics<br/>Counters, histograms, gauges<br/>for cost, latency, quality]
        LOGS[Logs<br/>Structured events<br/>with trace correlation]
        AI_INST --> TRACES
        AI_INST --> METRICS
        AI_INST --> LOGS
    end

    subgraph "Platform"
        direction TB
        COLLECTOR[OTel Collector<br/>Receive, process, export]
        TRACES --> COLLECTOR
        METRICS --> COLLECTOR
        LOGS --> COLLECTOR

        TRACE_BE[Trace Backend<br/>Tempo / Jaeger]
        METRIC_BE[Metric Backend<br/>Prometheus / Mimir]
        LOG_BE[Log Backend<br/>Loki / Elastic]

        COLLECTOR --> TRACE_BE
        COLLECTOR --> METRIC_BE
        COLLECTOR --> LOG_BE
    end

    subgraph "Intelligence"
        DASH[Dashboards<br/>Grafana]
        ALERTS[Alerts<br/>Alertmanager]
        DEBUG[Trace Debugger<br/>Root Cause Analysis]
        EVAL[Eval Pipeline<br/>Quality Scoring]

        TRACE_BE --> DASH
        METRIC_BE --> DASH
        METRIC_BE --> ALERTS
        TRACE_BE --> DEBUG
        TRACE_BE --> EVAL
        EVAL -->|scores as metrics| METRIC_BE
    end

    subgraph "Action"
        ONCALL[On-Call Response]
        AUTO[Auto-Remediation<br/>Circuit breakers, fallbacks]
        IMPROVE[Continuous Improvement<br/>Fine-tune, re-index, update prompts]

        ALERTS --> ONCALL
        ALERTS --> AUTO
        DEBUG --> IMPROVE
    end
```
