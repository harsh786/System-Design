# AI Gateway - Comprehensive Deep Dive

## What is an AI Gateway?

An AI Gateway is a specialized infrastructure layer that sits between your application and AI/LLM providers, acting as a unified control plane for all AI model interactions. Unlike a traditional API Gateway that handles generic HTTP traffic (auth, rate limiting, routing), an AI Gateway understands the **semantics of AI workloads**: tokens, prompts, model capabilities, generation costs, content safety, and provider-specific nuances.

### AI Gateway vs API Gateway

| Dimension | API Gateway | AI Gateway |
|-----------|-------------|------------|
| **Unit of work** | HTTP request/response | Prompt → Completion (tokens) |
| **Cost model** | Flat per-request or bandwidth | Per-token, per-model, variable pricing |
| **Rate limiting** | Requests/second | Tokens/minute + requests/minute + concurrent |
| **Routing intelligence** | Path/header-based | Model capability, cost, latency, risk-based |
| **Caching** | URL + headers (exact match) | Semantic similarity cache |
| **Health checking** | HTTP 200 | Model availability + quality degradation |
| **Retry logic** | Simple retry | Token-aware retry (don't retry 128K prompt blindly) |
| **Observability** | Latency, status codes | Token usage, cost, quality scores, hallucination rate |
| **Security** | Auth, WAF, IP filtering | Prompt injection detection, PII filtering, content safety |
| **Budget** | Not applicable | Per-tenant token/dollar budgets |
| **Failover** | Backend switching | Cross-provider model equivalence mapping |

### Why Not Just Use an API Gateway?

1. **Token economics** - A single request can cost $0.001 or $5.00 depending on context length and model
2. **Non-deterministic responses** - Same input produces different outputs; caching needs semantic understanding
3. **Provider diversity** - Each provider has different APIs, auth, streaming protocols, and error codes
4. **Content safety** - Prompts and responses need content-specific guardrails
5. **Model routing** - Choosing the right model for a task requires understanding task characteristics

---

## AI Gateway Responsibilities

### 1. Model Routing
- Route requests to the optimal model based on intent, complexity, cost constraints, and latency requirements
- Support explicit model selection AND intelligent auto-routing
- Maintain model capability registry (context window, function calling, vision, etc.)

### 2. Provider Abstraction
- Unified API across OpenAI, Anthropic, Azure OpenAI, Google, Cohere, self-hosted (vLLM, Ollama, TGI)
- Translate between provider-specific formats transparently
- Handle provider-specific streaming protocols (SSE vs WebSocket)

### 3. Fallback and Retry
- Automatic failover when a provider returns 5xx, timeout, or rate limit
- Model equivalence mapping (GPT-4o → Claude 3.5 Sonnet → Gemini 1.5 Pro)
- Exponential backoff with jitter per provider
- Circuit breaker to avoid cascading failures

### 4. Rate Limiting
- Per-user, per-tenant, per-model, per-provider rate limits
- Token-based rate limiting (not just request count)
- Sliding window and token bucket algorithms
- Priority queuing for different tiers

### 5. Token Budget Enforcement
- Real-time token counting before sending to provider
- Hard and soft budget limits per tenant/user/project
- Budget period management (daily, weekly, monthly)
- Alert thresholds (80%, 90%, 100%)

### 6. Cost Tracking
- Real-time cost computation per request (input tokens × input price + output tokens × output price)
- Cost attribution to tenant, user, project, feature
- Cost anomaly detection
- Historical cost analytics and forecasting

### 7. Key Management
- Secure storage and rotation of provider API keys
- Per-tenant key isolation
- Key usage tracking and quota management
- Automatic key rotation on compromise detection

### 8. Prompt Cache
- Exact-match caching for deterministic prompts (temperature=0)
- Prefix caching for shared system prompts
- TTL-based cache invalidation
- Cache hit rate monitoring

### 9. Semantic Cache
- Embedding-based similarity matching for cache lookups
- Configurable similarity threshold
- Cache warming for common queries
- Per-tenant cache isolation

### 10. Logging and Observability
- Full request/response logging (with PII masking)
- Token usage metrics per dimension
- Latency percentiles per provider/model
- Error rate tracking and alerting
- Distributed tracing integration

### 11. Guardrail Hooks
- **Pre-request**: Prompt injection detection, PII filtering, topic restriction, input validation
- **Post-response**: Content safety filtering, hallucination detection, PII redaction, format validation
- Pluggable guardrail pipeline
- Async guardrail evaluation for non-blocking flows

### 12. Tenant Usage Tracking
- Per-tenant usage dashboards
- Quota management and enforcement
- Usage-based billing data generation
- SLA monitoring per tenant

### 13. Policy Enforcement
- Model access control (which tenants can use which models)
- Data residency enforcement (route EU tenant data to EU endpoints)
- Content policy enforcement
- Compliance logging for regulated industries

---

## Architecture

```
Client Application
       │
       ▼
┌─────────────────┐
│   API Gateway   │  ← Standard auth, TLS, general rate limiting
│  (Kong/Envoy)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Auth + Tenant  │  ← Identify tenant, load policies, check permissions
│    Policy       │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│                    AI GATEWAY                             │
│                                                          │
│  ┌──────────────┐   ┌───────────────┐   ┌───────────┐  │
│  │   Pre-flight │   │  Budget Check │   │   Cache    │  │
│  │  Guardrails  │──▶│  & Rate Limit │──▶│   Lookup   │  │
│  └──────────────┘   └───────────────┘   └─────┬─────┘  │
│                                                │         │
│                              Cache Miss ────────┘        │
│                                                │         │
│  ┌──────────────────────────────────────────────┐       │
│  │              MODEL ROUTER                     │       │
│  │                                               │       │
│  │  Rules Engine + Cost/Latency/Quality Scorer   │       │
│  └─────────┬──────────────┬──────────────┬──────┘       │
│            │              │              │                │
│            ▼              ▼              ▼                │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────┐    │
│  │  Provider A │ │  Provider B  │ │  Self-Hosted   │    │
│  │  (OpenAI)   │ │ (Anthropic)  │ │  (vLLM/Ollama)│    │
│  └──────┬──────┘ └──────┬───────┘ └───────┬───────┘    │
│         │                │                 │             │
│         └────────────────┴─────────────────┘             │
│                          │                               │
│                          ▼                               │
│  ┌──────────────────────────────────────────────┐       │
│  │          Post-Response Pipeline               │       │
│  │                                               │       │
│  │  Guardrails → Cost Compute → Cache Store →    │       │
│  │  Log/Trace → Eval Sampling → Response         │       │
│  └──────────────────────────────────────────────┘       │
│                                                          │
└──────────────────────────────────────────────────────────┘
         │
         ▼
   ┌─────────────┐
   │  Telemetry  │  ← Prometheus, OpenTelemetry, Cost DB
   │   Pipeline  │
   └─────────────┘
```

---

## Commercial vs Open-Source AI Gateways

### Commercial
| Product | Strengths | Weaknesses |
|---------|-----------|------------|
| **Portkey** | Feature-rich, good UI, semantic cache | Vendor lock-in, pricing at scale |
| **Helicone** | Great observability, easy integration | Less routing intelligence |
| **LiteLLM (hosted)** | Best provider coverage | Limited guardrails |
| **Cloudflare AI Gateway** | Edge deployment, DDoS protection | Limited routing logic |
| **AWS Bedrock** | Native AWS integration | Only AWS models + limited external |

### Open-Source
| Product | Strengths | Weaknesses |
|---------|-----------|------------|
| **LiteLLM** | 100+ providers, drop-in proxy | Limited routing intelligence |
| **MLflow AI Gateway** | ML ecosystem integration | Less production-ready |
| **Kong AI Gateway** | Plugin ecosystem, mature infra | AI features are newer |
| **Envoy AI Gateway** | High performance, extensible | Complex configuration |
| **OpenRouter** | Model marketplace, automatic routing | Less enterprise control |

---

## Build vs Buy Decision

### Build When:
- You need deep integration with internal systems (custom auth, billing, compliance)
- Your routing logic is highly domain-specific
- You have strict data residency requirements
- You need custom guardrails that don't fit plugin models
- You're operating at scale where commercial pricing becomes prohibitive
- You need full control over the data plane (no external data transmission)

### Buy When:
- Time to market is critical
- Your team lacks AI infrastructure expertise
- Standard routing and observability is sufficient
- You need broad provider support quickly
- Compliance requirements are met by the vendor

### Hybrid Approach (Recommended):
- Use open-source (LiteLLM) as the provider abstraction layer
- Build custom routing logic on top
- Build custom guardrails and budget enforcement
- Use commercial observability (Helicone/Langfuse) alongside

---

## Gateway Deployment Patterns

### 1. Centralized Gateway
```
All services → Central AI Gateway → Providers
```
- **Pros**: Single point of control, unified observability, easier key management
- **Cons**: Single point of failure, potential bottleneck, cross-region latency
- **Best for**: Most organizations, especially early stage

### 2. Sidecar Pattern
```
Each service has its own AI Gateway sidecar (like Envoy in service mesh)
```
- **Pros**: No network hop, service-local rate limiting, resilient to gateway failure
- **Cons**: Harder to enforce global budgets, distributed config management
- **Best for**: Microservices architectures with strict latency requirements

### 3. Edge Gateway
```
AI Gateway deployed at CDN edge locations
```
- **Pros**: Low latency for global users, edge caching, DDoS protection
- **Cons**: Complex deployment, eventual consistency for budgets
- **Best for**: Consumer-facing AI products with global users

### 4. Layered Pattern
```
Edge (cache + guardrails) → Central (routing + budget) → Provider
```
- **Pros**: Best of both worlds, defense in depth
- **Cons**: Complexity, multiple hops
- **Best for**: Large enterprises with complex requirements

---

## Model Routing Strategies

### Cost-Optimized Routing
- Route simple tasks (classification, extraction) to cheap models (GPT-4o-mini, Haiku)
- Route complex tasks (reasoning, code generation) to expensive models (GPT-4o, Opus)
- Use complexity estimation (prompt length, task type, required quality) to decide
- Continuously optimize based on quality feedback

### Latency-Optimized Routing
- Maintain real-time latency percentiles per provider/model
- Route time-sensitive requests to fastest available model
- Consider TTFT (time to first token) for streaming use cases
- Geo-aware routing to closest provider endpoint

### Quality-Optimized Routing
- Route high-risk/high-value requests to best model regardless of cost
- Use task-specific quality benchmarks to select model
- A/B test models on same traffic to measure quality
- Continuous evaluation sampling to detect quality degradation

### Risk-Based Routing
- Route customer-facing content through highest-quality + safety guardrails
- Route internal/dev workloads through cheaper models
- Route regulated content (medical, financial) through approved models only
- Apply different guardrail strictness based on risk tier

---

## Fallback and Degraded Mode Design

### Fallback Chain
```
Primary (GPT-4o) → Secondary (Claude 3.5 Sonnet) → Tertiary (Gemini 1.5 Pro) → Self-hosted (Llama 3) → Cached response → Graceful error
```

### Degraded Mode Levels
1. **Full service** - Primary model available, all features active
2. **Degraded quality** - Fallback model active, slightly lower quality
3. **Degraded features** - Only essential features, non-critical AI disabled
4. **Cache-only** - Serve cached responses only, no new generations
5. **Graceful failure** - Clear error message, queue for retry

### Circuit Breaker States
- **Closed** - Normal operation, requests flow through
- **Open** - Provider is down, immediately route to fallback
- **Half-open** - Probe with single request to check recovery

---

## Budget Enforcement and Cost Controls

### Budget Hierarchy
```
Organization Budget ($10,000/month)
├── Team A Budget ($5,000/month)
│   ├── Project X ($3,000/month)
│   │   ├── User 1 ($500/month)
│   │   └── User 2 ($500/month)
│   └── Project Y ($2,000/month)
└── Team B Budget ($5,000/month)
```

### Enforcement Modes
- **Soft limit** - Log warning, allow request, alert admin
- **Hard limit** - Reject request with budget exceeded error
- **Throttle** - Allow but downgrade to cheaper model
- **Queue** - Queue request for next budget period

### Cost Control Mechanisms
1. Max tokens per request cap
2. Max cost per request cap
3. Daily/hourly spend velocity checks
4. Anomaly detection (sudden 10x spend spike)
5. Automatic model downgrade when approaching budget
6. Pre-request cost estimation and rejection

---

## Provider Abstraction Layer Design

### Unified Schema
```python
# Input (provider-agnostic)
{
    "messages": [...],
    "model": "gpt-4o",  # or abstract model tier
    "max_tokens": 1000,
    "temperature": 0.7,
    "tools": [...],
    "stream": True
}

# Output (provider-agnostic)
{
    "content": "...",
    "model": "gpt-4o-2024-08-06",
    "usage": {"input_tokens": 150, "output_tokens": 80},
    "cost": {"input": 0.000375, "output": 0.0008, "total": 0.001175},
    "latency_ms": 1200,
    "provider": "openai",
    "cached": False
}
```

### Adapter Pattern
Each provider adapter translates between the unified schema and provider-specific format:
- Request transformation (message format, tool format, parameter naming)
- Response normalization (token counting, finish reason mapping)
- Error code mapping to unified error types
- Streaming protocol adaptation (OpenAI SSE vs Anthropic SSE vs gRPC)

### Capability Registry
```python
MODEL_CAPABILITIES = {
    "gpt-4o": {
        "provider": "openai",
        "context_window": 128000,
        "max_output": 16384,
        "supports_vision": True,
        "supports_tools": True,
        "supports_streaming": True,
        "input_cost_per_1k": 0.0025,
        "output_cost_per_1k": 0.01,
        "avg_latency_ms": 800,
        "quality_tier": "high"
    }
}
```
