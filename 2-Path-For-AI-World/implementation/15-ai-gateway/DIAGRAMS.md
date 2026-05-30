# AI Gateway - Architecture Diagrams

## 1. Full AI Gateway Architecture

```mermaid
graph TB
    subgraph Clients
        C1[Web App]
        C2[Mobile App]
        C3[Internal Service]
        C4[Batch Pipeline]
    end

    subgraph "API Gateway Layer"
        AG[API Gateway<br/>Kong/Envoy]
        AUTH[Auth Service]
        TP[Tenant Policy Service]
    end

    subgraph "AI Gateway Core"
        GW[AI Gateway Orchestrator]
        
        subgraph "Pre-Processing"
            RL[Rate Limiter]
            BM[Budget Manager]
            PRG[Pre-Request Guardrails]
            PC[Prompt Cache]
            SC[Semantic Cache]
        end
        
        subgraph "Routing"
            MR[Model Router]
            RE[Rules Engine]
            AB[A/B Test Router]
            LB[Load Balancer]
        end
        
        subgraph "Post-Processing"
            POG[Post-Response Guardrails]
            CT[Cost Tracker]
            LOG[Logger/Tracer]
            EVAL[Eval Sampler]
        end
    end

    subgraph "Provider Layer"
        CB1[Circuit Breaker]
        CB2[Circuit Breaker]
        CB3[Circuit Breaker]
        CB4[Circuit Breaker]
        
        P1[OpenAI API]
        P2[Anthropic API]
        P3[Azure OpenAI]
        P4[Self-Hosted<br/>vLLM/Ollama]
    end

    subgraph "Data Layer"
        REDIS[(Redis<br/>Cache + Rate Limits)]
        PG[(PostgreSQL<br/>Cost Records)]
        PROM[Prometheus<br/>Metrics]
        OT[OpenTelemetry<br/>Traces]
    end

    C1 & C2 & C3 & C4 --> AG
    AG --> AUTH --> TP --> GW
    GW --> RL --> BM --> PRG --> PC --> SC
    SC -->|Miss| MR
    MR --> RE & AB & LB
    LB --> CB1 --> P1
    LB --> CB2 --> P2
    LB --> CB3 --> P3
    LB --> CB4 --> P4
    P1 & P2 & P3 & P4 --> POG --> CT --> LOG --> EVAL
    
    RL --- REDIS
    PC --- REDIS
    CT --- PG
    LOG --- OT
    GW --- PROM
```

## 2. Request Flow Through Gateway

```mermaid
sequenceDiagram
    participant Client
    participant APIGw as API Gateway
    participant Auth
    participant AIGw as AI Gateway
    participant Guard as Guardrails
    participant RL as Rate Limiter
    participant Budget as Budget Mgr
    participant Cache as Cache
    participant Router as Model Router
    participant Provider as Provider
    participant Logger as Logger

    Client->>APIGw: POST /v1/chat/completions
    APIGw->>Auth: Validate token
    Auth-->>APIGw: tenant_id, user_id, policies
    APIGw->>AIGw: Forward with context

    AIGw->>Guard: Pre-request guardrails
    Guard-->>AIGw: Pass (or block)
    
    AIGw->>RL: Check rate limits
    RL-->>AIGw: Allowed (or 429)
    
    AIGw->>Budget: Check budget (estimated cost)
    Budget-->>AIGw: Allowed / Throttle / Reject
    
    AIGw->>Cache: Lookup (exact + semantic)
    
    alt Cache Hit
        Cache-->>AIGw: Cached response
        AIGw-->>Client: Return cached (cost=0)
    else Cache Miss
        Cache-->>AIGw: Miss
        AIGw->>Router: Select model
        Router-->>AIGw: model_id, provider, fallbacks
        
        AIGw->>Provider: Send request
        
        alt Provider Success
            Provider-->>AIGw: Response + usage
        else Provider Failure
            AIGw->>Router: Get fallback
            Router-->>AIGw: fallback model
            AIGw->>Provider: Retry with fallback
            Provider-->>AIGw: Response
        end
        
        AIGw->>Guard: Post-response guardrails
        Guard-->>AIGw: Pass (or filter)
        
        AIGw->>Budget: Record cost
        AIGw->>Cache: Store response
        AIGw->>Logger: Log request
        AIGw-->>Client: Return response
    end
```

## 3. Model Routing Decision Tree

```mermaid
graph TD
    START[Incoming Request] --> EXPLICIT{Explicit<br/>model set?}
    
    EXPLICIT -->|Yes| VALIDATE[Validate model<br/>access permission]
    EXPLICIT -->|No| RULES[Evaluate<br/>routing rules]
    
    VALIDATE -->|Allowed| DIRECT[Use specified model]
    VALIDATE -->|Denied| REJECT[Reject: Access denied]
    
    RULES -->|Rule matched| RULE_MODEL[Use rule target model]
    RULES -->|No match| AB{Active<br/>A/B test?}
    
    AB -->|Yes| AB_ASSIGN[Deterministic<br/>assignment]
    AB -->|No| CANARY{Active<br/>canary?}
    
    AB_ASSIGN --> AB_MODEL[Use test model]
    
    CANARY -->|Yes| CANARY_PCT[Route by %]
    CANARY -->|No| STRATEGY[Apply routing<br/>strategy]
    
    CANARY_PCT --> CANARY_MODEL[Use canary/stable model]
    
    STRATEGY --> COMPLEXITY[Estimate<br/>complexity]
    COMPLEXITY --> RISK{Risk level?}
    
    RISK -->|Critical| QUALITY[Quality-optimized<br/>→ Best model]
    RISK -->|High| BALANCED[Balanced<br/>strategy]
    RISK -->|Medium/Low| COST_CHECK{Max cost<br/>constraint?}
    
    COST_CHECK -->|Strict| COST[Cost-optimized<br/>→ Cheapest viable]
    COST_CHECK -->|None| LATENCY_CHECK{Latency<br/>constraint?}
    
    LATENCY_CHECK -->|Yes| LATENCY[Latency-optimized<br/>→ Fastest]
    LATENCY_CHECK -->|No| BALANCED
    
    QUALITY --> DEGRADED{Provider<br/>healthy?}
    BALANCED --> DEGRADED
    COST --> DEGRADED
    LATENCY --> DEGRADED
    
    DEGRADED -->|Yes| FINAL[Final model selection]
    DEGRADED -->|No| DEGRADE[Apply degraded<br/>mode mapping]
    DEGRADE --> FINAL
```

## 4. Provider Fallback Sequence

```mermaid
sequenceDiagram
    participant GW as AI Gateway
    participant CB1 as Circuit Breaker<br/>(OpenAI)
    participant P1 as OpenAI
    participant CB2 as Circuit Breaker<br/>(Anthropic)
    participant P2 as Anthropic
    participant CB3 as Circuit Breaker<br/>(Self-hosted)
    participant P3 as vLLM
    participant Cache as Response Cache

    GW->>CB1: Can execute?
    CB1-->>GW: Yes (CLOSED)
    GW->>P1: POST /chat/completions
    
    alt OpenAI 429 (Rate Limited)
        P1-->>GW: 429 Too Many Requests
        GW->>CB1: Record failure
        Note over CB1: failure_count++ (3/5)
        
        GW->>GW: Retry with backoff (2s)
        GW->>P1: Retry request
        P1-->>GW: 429 again
        GW->>CB1: Record failure (4/5)
        
        Note over GW: Max retries reached, try fallback
        
        GW->>CB2: Can execute?
        CB2-->>GW: Yes (CLOSED)
        GW->>P2: POST /messages (translated format)
        P2-->>GW: 200 OK (response)
        GW->>CB2: Record success
        Note over GW: Return response<br/>(fallback_used=true)
        
    else OpenAI 500 (Server Error) + Circuit Opens
        P1-->>GW: 500 Internal Error
        GW->>CB1: Record failure (5/5 = threshold)
        Note over CB1: State: CLOSED → OPEN
        
        GW->>CB2: Can execute?
        CB2-->>GW: Yes
        GW->>P2: Request
        P2-->>GW: 529 Overloaded
        GW->>CB2: Record failure
        
        GW->>CB3: Can execute?
        CB3-->>GW: Yes
        GW->>P3: Request (OpenAI-compatible)
        P3-->>GW: 200 OK
        GW->>CB3: Record success
        
    else All Providers Down
        Note over GW: All circuit breakers OPEN
        GW->>Cache: Check for cached response
        
        alt Cache Hit
            Cache-->>GW: Stale cached response
            Note over GW: Return with warning<br/>"stale_cache" flag
        else No Cache
            Note over GW: Return error:<br/>ALL_PROVIDERS_DOWN
        end
    end
```

## 5. Budget Enforcement Flow

```mermaid
flowchart TD
    REQ[Incoming Request] --> EST[Estimate cost:<br/>input_tokens × price +<br/>max_output × price]
    
    EST --> PER_REQ{Per-request<br/>limit exceeded?}
    PER_REQ -->|Yes| REJECT_REQ[REJECT: Request too expensive]
    PER_REQ -->|No| PRIORITY{Priority =<br/>critical?}
    
    PRIORITY -->|Yes + override enabled| ALLOW_CRITICAL[ALLOW: Critical override]
    PRIORITY -->|No| HOURLY{Hourly budget<br/>check}
    
    HOURLY -->|Under limit| DAILY{Daily budget<br/>check}
    HOURLY -->|Over limit| ENFORCE_H[Apply enforcement]
    
    DAILY -->|Under limit| MONTHLY{Monthly budget<br/>check}
    DAILY -->|Over limit| ENFORCE_D[Apply enforcement]
    
    MONTHLY -->|Under limit| TOKEN{Token limit<br/>check}
    MONTHLY -->|Over limit| ENFORCE_M[Apply enforcement]
    
    TOKEN -->|Under limit| ALLOW[ALLOW: All checks passed]
    TOKEN -->|Over limit| REJECT_T[REJECT: Token limit]
    
    ENFORCE_H & ENFORCE_D & ENFORCE_M --> ACTION{Enforcement<br/>action?}
    
    ACTION -->|REJECT| REJECT_B[REJECT: Budget exceeded]
    ACTION -->|THROTTLE| THROTTLE[THROTTLE: Downgrade model<br/>to cheaper alternative]
    ACTION -->|QUEUE| QUEUE[QUEUE: Hold for next period]
    ACTION -->|WARN| WARN[WARN: Allow but alert admin]
    
    ALLOW --> EXECUTE[Execute request]
    THROTTLE --> EXECUTE
    
    EXECUTE --> RECORD[Record actual cost]
    RECORD --> ANOMALY{Cost anomaly<br/>detected?}
    ANOMALY -->|Yes| ALERT[Send anomaly alert]
    ANOMALY -->|No| DONE[Done]
    ALERT --> DONE
    
    subgraph "Alert Thresholds"
        T70["70% → WARNING alert"]
        T90["90% → CRITICAL alert"]
        T100["100% → Enforce action"]
    end
```

## 6. AI Gateway vs API Gateway Comparison

```mermaid
graph LR
    subgraph "Traditional API Gateway"
        direction TB
        A1[TLS Termination]
        A2[Authentication]
        A3[Rate Limiting<br/>req/s]
        A4[Path-based Routing]
        A5[Response Caching<br/>URL+headers]
        A6[Load Balancing<br/>round-robin]
        A7[Request Logging]
        
        A1 --> A2 --> A3 --> A4 --> A5 --> A6 --> A7
    end
    
    subgraph "AI Gateway (additional)"
        direction TB
        B1[Token-aware<br/>Rate Limiting]
        B2[Semantic Caching<br/>embedding similarity]
        B3[Model Routing<br/>cost/quality/latency]
        B4[Provider Abstraction<br/>format translation]
        B5[Budget Enforcement<br/>$/tenant/period]
        B6[Content Guardrails<br/>injection/PII/safety]
        B7[Cost Tracking<br/>per-token pricing]
        B8[Circuit Breakers<br/>per-provider health]
        B9[Streaming Proxy<br/>SSE normalization]
        B10[Eval Sampling<br/>quality monitoring]
        
        B1 --> B2 --> B3 --> B4 --> B5
        B6 --> B7 --> B8 --> B9 --> B10
    end
```

## 7. Provider Abstraction Layer

```mermaid
graph TB
    subgraph "Unified Interface"
        UI[UnifiedRequest / UnifiedResponse]
        SM[Streaming: AsyncGenerator of StreamChunk]
    end
    
    subgraph "Adapter Layer"
        direction LR
        OA[OpenAI Adapter]
        AA[Anthropic Adapter]
        AZ[Azure OpenAI Adapter]
        SH[Self-Hosted Adapter]
    end
    
    subgraph "Translation"
        direction TB
        OA --> OT1[Messages → OpenAI format]
        OA --> OT2[Tools → functions format]
        OA --> OT3[SSE stream parsing]
        
        AA --> AT1[Messages → Anthropic format<br/>system extracted separately]
        AA --> AT2[Tools → input_schema format]
        AA --> AT3[SSE event types parsing]
        
        AZ --> AZT1[Same as OpenAI format]
        AZ --> AZT2[Deployment URL routing]
        AZ --> AZT3[api-key header auth]
        
        SH --> ST1[OpenAI-compatible format]
        SH --> ST2[Health: /health or /v1/models]
    end
    
    subgraph "Error Mapping"
        EM[Unified Error Types]
        EM --> E1[RATE_LIMITED ← 429]
        EM --> E2[TIMEOUT ← connection error]
        EM --> E3[CONTEXT_LENGTH ← specific msg]
        EM --> E4[AUTH_ERROR ← 401/403]
        EM --> E5[SERVER_ERROR ← 5xx]
    end
    
    subgraph "Provider Manager"
        PM[ProviderManager]
        PM --> HC[Health Check Loop<br/>every 30s]
        PM --> FO[Failover Logic]
        PM --> MET[Error Rate Tracking]
    end
    
    UI --> OA & AA & AZ & SH
    SM --> OA & AA & AZ & SH
    OA & AA & AZ & SH --> PM
```

## 8. Cost Tracking Pipeline

```mermaid
graph LR
    subgraph "Request Phase"
        R1[Incoming Request]
        R2[Estimate Tokens<br/>~4 chars = 1 token]
        R3[Lookup Model Pricing]
        R4[Pre-compute Max Cost<br/>input×price + max_output×price]
        R5[Budget Pre-check]
    end
    
    subgraph "Execution Phase"
        E1[Send to Provider]
        E2[Provider Response<br/>with actual usage]
        E3[Extract Token Counts<br/>prompt_tokens + completion_tokens]
    end
    
    subgraph "Cost Computation"
        C1[Actual Cost Calculation]
        C2[Apply Cache Discounts]
        C3[Input Cost = input_tokens/1K × input_price]
        C4[Output Cost = output_tokens/1K × output_price]
        C5[Total = Input + Output]
    end
    
    subgraph "Recording & Analytics"
        A1[Record to Cost Store]
        A2[Update Tenant Spend<br/>hourly/daily/monthly]
        A3[Anomaly Detection<br/>z-score check]
        A4[Emit Metrics<br/>Prometheus counters]
        A5[Attribution<br/>tenant/user/project/feature]
    end
    
    subgraph "Reporting"
        RP1[Real-time Dashboard]
        RP2[Cost Allocation Report]
        RP3[Forecast & Projections]
        RP4[Optimization Recommendations]
    end
    
    R1 --> R2 --> R3 --> R4 --> R5
    R5 -->|Allowed| E1 --> E2 --> E3
    E3 --> C1 --> C2 --> C3 & C4 --> C5
    C5 --> A1 --> A2 --> A3 --> A4 --> A5
    A5 --> RP1 & RP2 & RP3 & RP4
```
