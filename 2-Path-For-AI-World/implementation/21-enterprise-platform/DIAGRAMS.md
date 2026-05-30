# Enterprise AI Platform - Architecture Diagrams

## 1. Enterprise AI Platform Architecture

```mermaid
graph TB
    subgraph "Product Teams"
        PT1[Team Alpha<br/>Customer Support Agent]
        PT2[Team Beta<br/>Code Assistant]
        PT3[Team Gamma<br/>Document Q&A]
    end

    subgraph "Developer Experience Layer"
        SDK[Platform SDK<br/>Python / TS / Go]
        CLI[Platform CLI]
        Portal[Self-Service Portal]
        Playground[AI Playground]
        Docs[Documentation]
    end

    subgraph "Platform API Layer"
        API[Platform API<br/>v1 / v2]
        Auth[AuthN/AuthZ<br/>OAuth 2.0]
        RL[Rate Limiter<br/>Per-Tenant]
        BL[Budget Limiter]
    end

    subgraph "Core Platform Services"
        GW[AI Gateway]
        PE[Policy Engine]
        EXP[Experiment Platform]
        EVAL[Eval Engine]
        FB[Feedback System]
        OBS[Observability Platform]
    end

    subgraph "Registry Layer"
        MR[Model Registry]
        PR[Prompt Registry]
        TR[Tool Registry]
        AR[Agent Registry]
        ER[Embedding Registry]
        VR[Vector Index Registry]
        EVR[Eval Registry]
        MCPR[MCP Registry]
    end

    subgraph "Infrastructure Layer"
        DB[(PostgreSQL<br/>Registry Store)]
        Cache[(Redis<br/>Cache + Rate Limits)]
        VDB[(Vector DB<br/>Qdrant/Pinecone)]
        ObjStore[(Object Storage<br/>Logs + Artifacts)]
        Queue[Event Bus<br/>Kafka/EventHub]
    end

    subgraph "Model Providers"
        OAI[OpenAI]
        ANT[Anthropic]
        AZ[Azure OpenAI]
        BED[AWS Bedrock]
        SH[Self-Hosted<br/>vLLM/Ollama]
    end

    PT1 & PT2 & PT3 --> SDK & CLI & Portal
    SDK & CLI & Portal --> API
    API --> Auth --> RL --> BL
    BL --> GW & PE & EXP & EVAL & FB
    GW --> MR & PR
    GW --> OAI & ANT & AZ & BED & SH
    PE --> MR & TR & AR
    EXP --> EVAL
    EVAL --> EVR
    GW & PE & EXP & EVAL --> OBS
    OBS --> Queue --> ObjStore
    MR & PR & TR & AR & ER & VR & EVR & MCPR --> DB
    GW --> Cache
    Playground --> API

    style GW fill:#ff9900,color:#000
    style PE fill:#d63384,color:#fff
    style OBS fill:#0d6efd,color:#fff
    style API fill:#198754,color:#fff
```

## 2. Registry Relationships

```mermaid
erDiagram
    MODEL_REGISTRY ||--o{ AGENT_REGISTRY : "used by"
    MODEL_REGISTRY ||--o{ PROMPT_REGISTRY : "recommended for"
    PROMPT_REGISTRY ||--o{ AGENT_REGISTRY : "configured in"
    TOOL_REGISTRY ||--o{ AGENT_REGISTRY : "available to"
    EMBEDDING_REGISTRY ||--o{ VECTOR_INDEX_REGISTRY : "generates vectors for"
    EVAL_REGISTRY ||--o{ PROMPT_REGISTRY : "evaluates"
    EVAL_REGISTRY ||--o{ AGENT_REGISTRY : "evaluates"
    EVAL_REGISTRY ||--o{ MODEL_REGISTRY : "benchmarks"
    VECTOR_INDEX_REGISTRY ||--o{ AGENT_REGISTRY : "provides context to"
    MCP_REGISTRY ||--o{ TOOL_REGISTRY : "exposes tools via"
    MCP_REGISTRY ||--o{ AGENT_REGISTRY : "connected to"

    MODEL_REGISTRY {
        string id PK
        string name
        string provider
        string risk_tier
        json capabilities
        json cost
        string status
    }

    PROMPT_REGISTRY {
        string id PK
        string name
        string version
        string template
        string model_id FK
        string environment
        json eval_results
    }

    TOOL_REGISTRY {
        string id PK
        string name
        string risk_level
        string endpoint
        json parameters
        json permissions
    }

    AGENT_REGISTRY {
        string id PK
        string name
        string model_id FK
        json prompt_ids
        json tool_ids
        json guardrails
        string status
    }

    EMBEDDING_REGISTRY {
        string id PK
        string name
        int dimensions
        string distance_metric
        json benchmarks
    }

    VECTOR_INDEX_REGISTRY {
        string id PK
        string name
        string embedding_id FK
        string vector_store
        datetime last_updated
        float eval_score
    }

    EVAL_REGISTRY {
        string id PK
        string name
        string eval_type
        json dataset
        json metrics
        bool is_gate
    }

    MCP_REGISTRY {
        string id PK
        string name
        string server_url
        json capabilities
        string auth_type
    }
```

## 3. Platform Maturity Levels

```mermaid
graph LR
    subgraph "L0: Ad Hoc"
        L0[No coordination<br/>Individual API keys<br/>No visibility]
    end

    subgraph "L1: Reactive"
        L1[Central key mgmt<br/>Basic dashboards<br/>Manual approvals]
    end

    subgraph "L2: Managed"
        L2[Gateway mandated<br/>Registries operational<br/>Basic policies<br/>SDK available]
    end

    subgraph "L3: Optimized"
        L3[Full 13 components<br/>Self-service 80%+<br/>Eval gates enforced<br/>Golden paths]
    end

    subgraph "L4: Proactive"
        L4[ML-driven optimization<br/>Predictive planning<br/>Auto-remediation<br/>Cross-team sharing]
    end

    subgraph "L5: Adaptive"
        L5[Self-optimizing<br/>Autonomous policies<br/>Self-healing<br/>AI-powered DX]
    end

    L0 -->|"Establish basics"| L1
    L1 -->|"Build platform"| L2
    L2 -->|"Optimize & enforce"| L3
    L3 -->|"Add intelligence"| L4
    L4 -->|"Full autonomy"| L5

    style L0 fill:#dc3545,color:#fff
    style L1 fill:#fd7e14,color:#000
    style L2 fill:#ffc107,color:#000
    style L3 fill:#20c997,color:#000
    style L4 fill:#0dcaf0,color:#000
    style L5 fill:#6f42c1,color:#fff
```

## 4. Self-Service Workflows

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant SDK as Platform SDK
    participant API as Platform API
    participant Auth as Auth Service
    participant RL as Rate Limiter
    participant Policy as Policy Engine
    participant Registry as Registry
    participant GW as AI Gateway
    participant LLM as LLM Provider

    Note over Dev,LLM: Self-Service Model Invocation Flow
    
    Dev->>SDK: client.chat(model="gpt-4o", messages=[...])
    SDK->>API: POST /v1/models/gpt-4o/invoke
    API->>Auth: Validate API key
    Auth-->>API: Tenant context (team, tier, permissions)
    API->>RL: Check rate limit (tenant: alpha, tier: standard)
    RL-->>API: ✓ Allowed (45/60 remaining)
    API->>Policy: Evaluate request policies
    Policy->>Registry: Get model risk tier, tenant permissions
    Registry-->>Policy: Model: T2, Tenant: allowed
    Policy->>Policy: Check PII, content safety, budget
    Policy-->>API: ✓ All policies pass
    API->>GW: Route to provider
    GW->>GW: Check cache (semantic match)
    GW->>LLM: Forward request
    LLM-->>GW: Response (300 tokens)
    GW->>GW: Log, attribute cost, cache response
    GW-->>API: Response + metadata
    API-->>SDK: Typed response with usage info
    SDK-->>Dev: ChatResponse(content="...", cost=0.003)

    Note over Dev,LLM: Self-Service Tool Registration Flow

    Dev->>SDK: registry.register_tool(name="lookup", ...)
    SDK->>API: POST /v1/tools
    API->>Auth: Validate + check permissions
    API->>Policy: Evaluate tool risk level
    Policy-->>API: Risk: read_only_internal → auto-approve
    API->>Registry: Create tool entry
    Registry-->>API: tool_id: "tool-abc123"
    API-->>SDK: ToolRegistration(id="tool-abc123", status="active")
    SDK-->>Dev: ✓ Tool registered and available
```

## 5. Experiment Platform Flow

```mermaid
stateDiagram-v2
    [*] --> Draft: Create Experiment

    Draft --> Scheduled: Schedule start
    Draft --> Running: Start immediately
    Scheduled --> Running: Start time reached

    Running --> Paused: Pause (manual)
    Running --> Stopped: Guardrail violation
    Running --> Completed: Duration elapsed

    Paused --> Running: Resume
    Paused --> Stopped: Cancel

    Completed --> Promoted: Promote winner
    Completed --> [*]: No winner / Archive

    Stopped --> [*]: Archive

    Promoted --> [*]: Winner is new default

    state Running {
        [*] --> AssignTraffic
        AssignTraffic --> CollectMetrics
        CollectMetrics --> CheckGuardrails
        CheckGuardrails --> StatisticalAnalysis
        StatisticalAnalysis --> AssignTraffic: Continue
        StatisticalAnalysis --> [*]: Significant result
    }
```

```mermaid
flowchart TB
    subgraph "Experiment Lifecycle"
        direction TB
        Define[Define Experiment<br/>Hypothesis, Variants, Metrics]
        Config[Configure<br/>Strategy, Guardrails, Duration]
        Start[Start Experiment]
        Monitor[Monitor & Collect]
        Analyze[Statistical Analysis]
        Decide{Significant<br/>Result?}
        Promote[Promote Winner]
        Archive[Archive Results]
    end

    subgraph "Traffic Splitting Strategies"
        Pct[Percentage Split<br/>50/50, 70/30]
        Canary[Canary<br/>5% → 10% → 25% → 50%]
        Bandit[Multi-Armed Bandit<br/>Thompson Sampling]
        User[User-Based<br/>Consistent per user]
    end

    subgraph "Guardrails"
        Safety[Safety Floor<br/>Accuracy > 70%]
        Cost[Cost Ceiling<br/>< $0.05/request]
        Latency[Latency Cap<br/>p99 < 3s]
        Volume[Volume Check<br/>Min samples reached]
    end

    Define --> Config --> Start --> Monitor
    Monitor --> Analyze --> Decide
    Decide -->|Yes| Promote
    Decide -->|No / Need more data| Monitor
    Decide -->|No winner| Archive
    Promote --> Archive

    Start --> Pct & Canary & Bandit & User
    Monitor --> Safety & Cost & Latency & Volume
```

## 6. Platform Team vs Product Team Boundary

```mermaid
graph TB
    subgraph "Platform Team Responsibility"
        direction TB
        PlatInfra[Infrastructure<br/>Gateway, Compute, Storage]
        PlatReg[Registry Services<br/>All 13 registries]
        PlatPolicy[Policy Engine<br/>Security, Cost, Compliance]
        PlatObs[Observability<br/>Metrics, Traces, Alerts]
        PlatSDK[Developer Tools<br/>SDK, CLI, Portal, Docs]
        PlatEval[Eval Infrastructure<br/>Execution engine, CI gates]
        PlatExp[Experiment Platform<br/>A/B testing, canary infra]
        PlatGP[Golden Paths<br/>Templates, examples]
    end

    subgraph "Shared Responsibility"
        direction TB
        SharedSec[Security Posture<br/>Platform: guardrails<br/>Product: compliance]
        SharedCost[Cost Management<br/>Platform: visibility<br/>Product: optimization]
        SharedQual[Quality Standards<br/>Platform: infra<br/>Product: definitions]
        SharedIncident[Incident Response<br/>Platform: infra issues<br/>Product: logic issues]
    end

    subgraph "Product Team Responsibility"
        direction TB
        ProdPrompt[Prompt Content<br/>Writing, testing, iteration]
        ProdAgent[Agent Logic<br/>Orchestration, workflows]
        ProdEval[Eval Datasets<br/>Golden sets, benchmarks]
        ProdTools[Tool Implementation<br/>Business logic, APIs]
        ProdFeat[Feature Ownership<br/>UX, requirements]
        ProdFeedback[User Feedback<br/>Collection, action]
        ProdDomain[Domain Expertise<br/>Business rules, data]
    end

    PlatInfra ~~~ SharedSec
    SharedSec ~~~ ProdPrompt

    style PlatInfra fill:#0d6efd,color:#fff
    style PlatReg fill:#0d6efd,color:#fff
    style PlatPolicy fill:#0d6efd,color:#fff
    style PlatObs fill:#0d6efd,color:#fff
    style PlatSDK fill:#0d6efd,color:#fff
    style PlatEval fill:#0d6efd,color:#fff
    style PlatExp fill:#0d6efd,color:#fff
    style PlatGP fill:#0d6efd,color:#fff

    style SharedSec fill:#ffc107,color:#000
    style SharedCost fill:#ffc107,color:#000
    style SharedQual fill:#ffc107,color:#000
    style SharedIncident fill:#ffc107,color:#000

    style ProdPrompt fill:#198754,color:#fff
    style ProdAgent fill:#198754,color:#fff
    style ProdEval fill:#198754,color:#fff
    style ProdTools fill:#198754,color:#fff
    style ProdFeat fill:#198754,color:#fff
    style ProdFeedback fill:#198754,color:#fff
    style ProdDomain fill:#198754,color:#fff
```

## 7. Golden Path Architecture

```mermaid
flowchart LR
    subgraph "Golden Path: RAG Application"
        direction TB
        GP1[1. Register Data Source] --> GP2[2. Platform Embedding Service]
        GP2 --> GP3[3. Platform Retrieval API]
        GP3 --> GP4[4. Prompt from Registry]
        GP4 --> GP5[5. AI Gateway Call]
        GP5 --> GP6[6. Eval Suite Deployed]
        GP6 --> GP7[7. Pre-built Dashboard]
    end

    subgraph "What You Get for Free"
        direction TB
        Free1[✓ PII Detection]
        Free2[✓ Cost Tracking]
        Free3[✓ Distributed Tracing]
        Free4[✓ Caching]
        Free5[✓ Failover]
        Free6[✓ Audit Trail]
        Free7[✓ Rate Limiting]
        Free8[✓ Alerting]
    end

    subgraph "Off-Ramp (DIY)"
        direction TB
        DIY1[✗ Own embedding pipeline]
        DIY2[✗ Own vector management]
        DIY3[✗ Direct API calls]
        DIY4[✗ Own monitoring]
        DIY5[✗ Own security controls]
        DIY6[More effort, same standards required]
    end

    GP7 --> Free1
    GP7 -.->|"opt out"| DIY1

    style GP1 fill:#198754,color:#fff
    style GP2 fill:#198754,color:#fff
    style GP3 fill:#198754,color:#fff
    style GP4 fill:#198754,color:#fff
    style GP5 fill:#198754,color:#fff
    style GP6 fill:#198754,color:#fff
    style GP7 fill:#198754,color:#fff

    style Free1 fill:#0dcaf0,color:#000
    style Free2 fill:#0dcaf0,color:#000
    style Free3 fill:#0dcaf0,color:#000
    style Free4 fill:#0dcaf0,color:#000
    style Free5 fill:#0dcaf0,color:#000
    style Free6 fill:#0dcaf0,color:#000
    style Free7 fill:#0dcaf0,color:#000
    style Free8 fill:#0dcaf0,color:#000

    style DIY1 fill:#dc3545,color:#fff
    style DIY2 fill:#dc3545,color:#fff
    style DIY3 fill:#dc3545,color:#fff
    style DIY4 fill:#dc3545,color:#fff
    style DIY5 fill:#dc3545,color:#fff
    style DIY6 fill:#dc3545,color:#fff
```

## 8. Platform API Topology

```mermaid
graph TB
    subgraph "External Clients"
        SDK_PY[Python SDK]
        SDK_TS[TypeScript SDK]
        CLI_T[CLI Tool]
        PORTAL_T[Web Portal]
        CI[CI/CD Pipelines]
    end

    subgraph "API Gateway Layer"
        LB[Load Balancer<br/>TLS Termination]
        APIGW[API Gateway<br/>Authentication, Routing]
    end

    subgraph "Platform API Services"
        direction TB
        AgentAPI[Agent API<br/>/agents/*]
        PromptAPI[Prompt API<br/>/prompts/*]
        ModelAPI[Model API<br/>/models/*]
        ToolAPI[Tool API<br/>/tools/*]
        EvalAPI[Eval API<br/>/evals/*]
        UsageAPI[Usage API<br/>/usage/*]
        HealthAPI[Health API<br/>/health, /status]
        ExperimentAPI[Experiment API<br/>/experiments/*]
    end

    subgraph "Internal Services"
        RegistrySvc[Registry Service]
        PolicySvc[Policy Service]
        GatewaySvc[AI Gateway Service]
        EvalSvc[Eval Execution Service]
        ExperimentSvc[Experiment Service]
        BillingSvc[Billing/Usage Service]
    end

    subgraph "Data Stores"
        PG[(PostgreSQL)]
        RD[(Redis)]
        S3[(Object Storage)]
        ES[(Elasticsearch<br/>Search)]
    end

    SDK_PY & SDK_TS & CLI_T & PORTAL_T & CI --> LB
    LB --> APIGW
    APIGW --> AgentAPI & PromptAPI & ModelAPI & ToolAPI & EvalAPI & UsageAPI & HealthAPI & ExperimentAPI

    AgentAPI & PromptAPI & ToolAPI --> RegistrySvc
    ModelAPI --> RegistrySvc & GatewaySvc
    EvalAPI --> EvalSvc
    ExperimentAPI --> ExperimentSvc
    UsageAPI --> BillingSvc
    AgentAPI & ModelAPI & ToolAPI --> PolicySvc

    RegistrySvc --> PG & ES
    PolicySvc --> RD
    GatewaySvc --> RD
    BillingSvc --> PG
    EvalSvc --> S3 & PG
    ExperimentSvc --> PG & RD

    style APIGW fill:#ff9900,color:#000
    style LB fill:#6c757d,color:#fff
```
