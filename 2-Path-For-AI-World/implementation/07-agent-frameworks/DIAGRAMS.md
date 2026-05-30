# Agent Frameworks - Diagrams

## 1. Framework Selection Decision Tree

```mermaid
flowchart TD
    START[What are you building?] --> Q1{Single agent<br/>or multi-agent?}
    
    Q1 -->|Single| Q2{Need state<br/>persistence?}
    Q1 -->|Multi| Q3{Deterministic<br/>routing needed?}
    
    Q2 -->|Yes| LG[LangGraph]
    Q2 -->|No| Q4{Need type<br/>safety?}
    
    Q4 -->|Yes| PAI[PydanticAI]
    Q4 -->|No| Q5{Data-heavy<br/>RAG?}
    
    Q5 -->|Yes| LI[LlamaIndex]
    Q5 -->|No| Q6{OpenAI only?}
    
    Q6 -->|Yes| OAI[OpenAI Agents SDK]
    Q6 -->|No| NF[No Framework]
    
    Q3 -->|Yes| LG2[LangGraph]
    Q3 -->|No| Q7{Research /<br/>exploration?}
    
    Q7 -->|Yes| AG[AutoGen]
    Q7 -->|No| Q8{Content<br/>generation?}
    
    Q8 -->|Yes| CR[CrewAI]
    Q8 -->|No| Q9{Specialist<br/>handoff?}
    
    Q9 -->|Yes| OAI2[OpenAI Agents SDK]
    Q9 -->|No| LG3[LangGraph]
    
    style LG fill:#4CAF50,color:white
    style LG2 fill:#4CAF50,color:white
    style LG3 fill:#4CAF50,color:white
    style OAI fill:#FF9800,color:white
    style OAI2 fill:#FF9800,color:white
    style LI fill:#2196F3,color:white
    style PAI fill:#9C27B0,color:white
    style AG fill:#F44336,color:white
    style CR fill:#795548,color:white
    style NF fill:#607D8B,color:white
```

## 2. LangGraph State Machine Example

```mermaid
stateDiagram-v2
    [*] --> Agent: START
    
    Agent --> Tools: has_tool_calls AND no_approval_needed
    Agent --> HumanApproval: has_tool_calls AND requires_approval
    Agent --> [*]: no_tool_calls (done)
    Agent --> ErrorHandler: max_iterations_exceeded
    
    Tools --> Agent: tool_results_ready
    
    HumanApproval --> Tools: approved
    HumanApproval --> Agent: rejected (with feedback)
    
    ErrorHandler --> Agent: retry
    ErrorHandler --> [*]: give_up
    
    state Agent {
        [*] --> ReasonAboutState
        ReasonAboutState --> DecideAction
        DecideAction --> GenerateResponse
        GenerateResponse --> [*]
    }
    
    state Tools {
        [*] --> ParseToolCalls
        ParseToolCalls --> ExecuteTools
        ExecuteTools --> FormatResults
        FormatResults --> [*]
    }
```

## 3. OpenAI Agents SDK - Handoff Pattern

```mermaid
sequenceDiagram
    participant U as User
    participant R as Runner
    participant T as Triage Agent
    participant O as Order Specialist
    participant B as Billing Specialist
    participant Tech as Technical Support
    
    U->>R: "I need a refund for my damaged order"
    R->>T: Execute with input
    
    Note over T: Analyzes intent:<br/>refund + order = Billing
    
    T->>R: handoff(billing_specialist)
    R->>B: Transfer context + conversation
    
    Note over B: Has tools: process_refund,<br/>get_customer_info
    
    B->>R: call tool: get_customer_info("C001")
    R-->>B: {name: "Acme", plan: "Enterprise"}
    
    B->>R: call tool: process_refund("ORD-002", 150, "damaged")
    R-->>B: "Refund processed"
    
    B->>R: Final response
    R->>U: "I've processed your $150 refund..."
    
    Note over R: Tracing captures:<br/>- Agent chain: Triage → Billing<br/>- Tools called: 2<br/>- Total tokens: ~1500
```

## 4. LlamaIndex Data Flow

```mermaid
flowchart TD
    subgraph Input
        Q[User Query]
    end
    
    subgraph Agent["ReAct Agent Loop"]
        R[Reason] --> A[Act]
        A --> O[Observe]
        O --> R
    end
    
    subgraph Tools["Available Tools"]
        VS[Vector Search Tool]
        SS[Summary Tool]
        KW[Keyword Tool]
        FN[Function Tools]
    end
    
    subgraph Indices["Index Layer"]
        VI[VectorStoreIndex]
        SI[SummaryIndex]
        KI[KeywordTableIndex]
    end
    
    subgraph Data["Data Sources"]
        D1[Technical Docs]
        D2[Financial Reports]
        D3[HR Policies]
        D4[Product Info]
    end
    
    Q --> Agent
    A --> VS & SS & KW & FN
    
    VS --> VI
    SS --> SI
    KW --> KI
    
    VI --> D1 & D2 & D3 & D4
    SI --> D1 & D2 & D3 & D4
    KI --> D1 & D2 & D3 & D4
    
    Agent --> Final[Synthesized Answer]
    
    style Agent fill:#E3F2FD,stroke:#1565C0
    style Tools fill:#FFF3E0,stroke:#E65100
    style Indices fill:#E8F5E9,stroke:#2E7D32
    style Data fill:#F3E5F5,stroke:#6A1B9A
```

## 5. Framework Comparison Matrix

```mermaid
quadrantChart
    title Framework Positioning: Simplicity vs Power
    x-axis Simple --> Complex/Powerful
    y-axis Specialized --> General Purpose
    
    quadrant-1 "Power Tools"
    quadrant-2 "Sweet Spot"
    quadrant-3 "Quick Start"
    quadrant-4 "Niche"
    
    "No Framework": [0.15, 0.8]
    "OpenAI SDK": [0.3, 0.6]
    "PydanticAI": [0.35, 0.55]
    "CrewAI": [0.4, 0.4]
    "LlamaIndex": [0.6, 0.3]
    "LangGraph": [0.75, 0.75]
    "AutoGen": [0.7, 0.5]
    "Haystack": [0.65, 0.35]
    "DSPy": [0.85, 0.25]
```

## 6. When to Use Which Framework - Flowchart

```mermaid
flowchart LR
    subgraph Complexity["Task Complexity"]
        direction TB
        S[Simple<br/>Single LLM call]
        M[Medium<br/>Multi-step + tools]
        C[Complex<br/>Multi-agent + state]
    end
    
    subgraph DataNeeds["Data Requirements"]
        direction TB
        ND[No data]
        SD[Some RAG]
        HD[Heavy data<br/>Multi-source]
    end
    
    subgraph Recommendations["Recommended Framework"]
        direction TB
        R1[No Framework<br/>or PydanticAI]
        R2[OpenAI SDK<br/>or LangGraph]
        R3[LangGraph +<br/>Persistence]
        R4[LlamaIndex<br/>or Haystack]
        R5[LlamaIndex Agent<br/>+ Vector Store]
    end
    
    S --> ND --> R1
    S --> SD --> R4
    M --> ND --> R2
    M --> SD --> R5
    C --> R3
    
    style R1 fill:#607D8B,color:white
    style R2 fill:#FF9800,color:white
    style R3 fill:#4CAF50,color:white
    style R4 fill:#2196F3,color:white
    style R5 fill:#9C27B0,color:white
```

## 7. LangGraph Parallel Execution Pattern

```mermaid
flowchart TD
    START([Start]) --> Agent[Agent Node]
    Agent --> Dispatch{Need parallel<br/>research?}
    
    Dispatch -->|Yes| Fan[Fan-Out]
    Dispatch -->|No| Tools[Tool Execution]
    
    Fan --> R1[Research Branch 1<br/>Web Search]
    Fan --> R2[Research Branch 2<br/>DB Query]
    Fan --> R3[Research Branch 3<br/>Doc Retrieval]
    
    R1 --> Join[Fan-In / Synthesize]
    R2 --> Join
    R3 --> Join
    
    Join --> Agent
    Tools --> Agent
    Agent --> Done{Done?}
    Done -->|Yes| END([End])
    Done -->|No| Agent
```

## 8. Production Deployment Architecture

```mermaid
flowchart TD
    subgraph Client["Client Layer"]
        API[REST API / WebSocket]
    end
    
    subgraph Orchestration["Agent Orchestration"]
        GR[Graph Runner<br/>LangGraph]
        CP[Checkpointer<br/>PostgreSQL]
        Q[Task Queue<br/>Redis/Celery]
    end
    
    subgraph Agents["Agent Nodes"]
        A1[Triage Agent]
        A2[Specialist A]
        A3[Specialist B]
        HN[Human Node<br/>Webhook/UI]
    end
    
    subgraph External["External Services"]
        LLM[LLM Provider<br/>OpenAI/Anthropic]
        VDB[Vector DB<br/>Pinecone/Weaviate]
        TOOLS[External APIs<br/>Search/Email/DB]
    end
    
    subgraph Observability["Observability"]
        TR[Tracing<br/>LangSmith/Arize]
        MET[Metrics<br/>Prometheus]
        LOG[Logs<br/>Structured JSON]
    end
    
    API --> Q --> GR
    GR --> CP
    GR --> A1 & A2 & A3 & HN
    A1 & A2 & A3 --> LLM
    A1 & A2 & A3 --> VDB
    A1 & A2 & A3 --> TOOLS
    GR --> TR & MET & LOG
    
    style GR fill:#4CAF50,color:white
    style CP fill:#FF9800,color:white
    style LLM fill:#2196F3,color:white
```
